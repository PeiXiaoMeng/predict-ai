"""竞品快照工具 —— 优先调用 ProductHunt GraphQL API，降级到 Mock

使用方式：
  在项目根目录创建 .env 文件，写入：
    PRODUCT_HUNT_TOKEN=your_developer_token_here

  免费 Token 申请地址：
    https://www.producthunt.com/v2/oauth/applications
    （选择 Developer Token，免登录授权，200次/天）

两种调用模式（由 workflow 内部决定）：
  mode="search"  ─ 按关键词搜索，返回多个竞品列表（workflow 主要用这个）
  mode="lookup"  ─ 按产品名查一个，返回单条快照（降级 mock 保持兼容）
"""
from __future__ import annotations

import logging
import math
import os
import random
import re
from collections import Counter
from typing import Any

from .base import BaseTool, register_tool
from .. import api_log

logger = logging.getLogger("predict-app.tools.competitor_snapshot")

# ── ProductHunt GraphQL ──────────────────────────────────────────────────────
_PH_ENDPOINT = "https://api.producthunt.com/v2/api/graphql"

# 语义重排阈值（topic 过滤后候选已相关，可适当放宽）
_SEMANTIC_MIN = 0.06
_OVERLAP_MIN = 0.05

# posts 字段模板（topic 为可选字符串参数）
_POSTS_FIELDS = """
    edges {
      node {
        name
        tagline
        website
        votesCount
        reviewsRating
        reviewsCount
        topics(first: 5) {
          edges { node { name } }
        }
      }
    }
"""

_SEARCH_QUERY_WITH_TOPIC = """
query SearchPostsTopic($first: Int!, $topic: String!) {
  posts(first: $first, topic: $topic) {""" + _POSTS_FIELDS + """  }
}
"""

_SEARCH_QUERY_NO_TOPIC = """
query SearchPosts($first: Int!) {
  posts(first: $first) {""" + _POSTS_FIELDS + """  }
}
"""

# ── 查询词 → PH topic 名映射 ─────────────────────────────────────────────────
# value 是有效的 PH topic 参数字符串，可多个，按顺序尝试
_TOPIC_MAP: dict[str, list[str]] = {
    # 体育/运动
    "sports":       ["sports", "fitness"],
    "sport":        ["sports", "fitness"],
    "体育":          ["sports", "fitness"],
    "运动":          ["sports", "fitness"],
    "体育赛事":      ["sports"],
    "赛事":          ["sports"],
    "健身":          ["fitness"],
    "fitness":      ["fitness"],
    # 娱乐/影视
    "entertainment": ["entertainment", "video"],
    "short drama":  ["entertainment", "video"],
    "drama":        ["entertainment", "video"],
    "series":       ["entertainment", "video"],
    "短剧":          ["entertainment", "video"],
    "微短剧":        ["entertainment", "video"],
    "剧":            ["entertainment", "video"],
    "影视":          ["entertainment", "video"],
    "视频":          ["video"],
    "video":        ["video"],
    # 阅读/书籍
    "novel":        ["books"],
    "fiction":      ["books"],
    "reading":      ["books"],
    "book":         ["books"],
    "books":        ["books"],
    "小说":          ["books"],
    "网文":          ["books"],
    "阅读":          ["books"],
    # 音乐
    "music":        ["music"],
    "音乐":          ["music"],
    # 旅行
    "travel":       ["travel"],
    "旅行":          ["travel"],
    "旅游":          ["travel"],
    # 教育
    "education":    ["education"],
    "learning":     ["education"],
    "教育":          ["education"],
    "学习":          ["education"],
    # 电商
    "ecommerce":    ["e-commerce"],
    "e-commerce":   ["e-commerce"],
    "shopping":     ["e-commerce"],
    "电商":          ["e-commerce"],
    "购物":          ["e-commerce"],
    # 金融/记账
    "finance":      ["finance"],
    "fintech":      ["finance"],
    "accounting":   ["finance"],
    "budgeting":    ["finance"],
    "记账":          ["finance"],
    "金融":          ["finance"],
    "理财":          ["finance"],
    # 健康/医疗
    "health":       ["health"],
    "healthcare":   ["health"],
    "medical":      ["health"],
    "医疗":          ["health"],
    "健康":          ["health"],
    # 游戏
    "game":         ["games"],
    "games":        ["games"],
    "gaming":       ["games"],
    "游戏":          ["games"],
    # 新闻/资讯
    "news":         ["news"],
    "新闻":          ["news"],
    "资讯":          ["news"],
}


def _get_token() -> str:
    """读取 PH Token：先查环境变量，再尝试读 .env 文件"""
    token = os.getenv("PRODUCT_HUNT_TOKEN", "")
    if not token:
        # 尝试从项目根 .env 加载（不强依赖 python-dotenv）
        try:
            env_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", ".env")
            with open(os.path.normpath(env_path), encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("PRODUCT_HUNT_TOKEN="):
                        token = line.split("=", 1)[1].strip().strip('"').strip("'")
                        break
        except FileNotFoundError:
            pass
    return token


def _resolve_ph_topics(query: str) -> list[str]:
    """将查询词映射到 PH topic 字符串列表（顺序尝试，找到即用）。"""
    q = (query or "").lower().strip()
    # 精确匹配
    for key, topics in _TOPIC_MAP.items():
        if key in q:
            return topics
    return []


def _fetch_nodes(token: str, count: int, topic: str | None = None, _query_hint: str = "") -> list[dict]:
    """向 PH API 拉取帖子节点，支持 topic 过滤。"""
    import httpx, time as _time
    if topic:
        payload = {
            "query": _SEARCH_QUERY_WITH_TOPIC,
            "variables": {"first": count, "topic": topic},
        }
    else:
        payload = {
            "query": _SEARCH_QUERY_NO_TOPIC,
            "variables": {"first": count},
        }
    log_params = {"topic": topic, "first": count}
    t0 = _time.perf_counter()
    error: str | None = None
    nodes: list[dict] = []
    raw_response: dict = {}
    try:
        resp = httpx.post(
            _PH_ENDPOINT,
            json=payload,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        raw_response = data
        if "errors" in data:
            logger.warning("[ph_fetch] API errors: %s", data["errors"])
        else:
            nodes = [e["node"] for e in data.get("data", {}).get("posts", {}).get("edges", [])]
    except Exception as exc:
        error = str(exc)
        logger.warning("[ph_fetch] request failed: %s", exc)
    finally:
        elapsed = round((_time.perf_counter() - t0) * 1000)
        api_log.push(
            source="producthunt",
            query=_query_hint or (topic or "(no topic)"),
            params=log_params,
            response={
                "nodes_count": len(nodes),
                "sample": [
                    {"name": n.get("name"), "tagline": n.get("tagline"), "votes": n.get("votesCount"),
                     "topics": [e["node"]["name"] for e in n.get("topics", {}).get("edges", [])]}
                    for n in nodes[:8]
                ],
                "raw_errors": raw_response.get("errors"),
            },
            elapsed_ms=elapsed,
            error=error,
        )
    return nodes


def _rerank(nodes: list[dict], query_text: str, count: int) -> list[dict]:
    """对候选帖子按语义 + 关键词重叠 + 热度综合打分并截取 TopN。"""
    scored: list[dict] = []
    for n in nodes:
        name = n.get("name") or ""
        tagline = n.get("tagline") or ""
        topics = " ".join(
            e.get("node", {}).get("name", "")
            for e in n.get("topics", {}).get("edges", [])
        )
        doc_text = f"{name} {tagline} {topics}".strip()

        semantic = _semantic_similarity(query_text, doc_text)
        overlap = _keyword_overlap(query_text, doc_text)
        popularity = _popularity_score(int(n.get("votesCount") or 0))
        final_score = 0.65 * semantic + 0.20 * overlap + 0.15 * popularity

        # 低阈值拒答（topic 已过滤候选，主要防止完全不相关）
        if semantic >= _SEMANTIC_MIN or overlap >= _OVERLAP_MIN:
            node = dict(n)
            node["_semantic_score"] = round(semantic, 4)
            node["_overlap_score"] = round(overlap, 4)
            node["_popularity_score"] = round(popularity, 4)
            node["_rank_score"] = round(final_score, 4)
            scored.append(node)

    ranked = sorted(scored, key=lambda x: x.get("_rank_score", 0.0), reverse=True)
    return ranked[:count]


def _ph_search(query: str, count: int, token: str) -> list[dict]:
    """按 query 从 ProductHunt 检索相关竞品并重排，失败返回空列表。"""
    try:
        # 1. 解析 topic：优先 topic 过滤，获得更相关候选池
        ph_topics = _resolve_ph_topics(query)
        query_text = _build_query_text(query)
        fetch_per_topic = max(count * 4, 20)

        nodes: list[dict] = []
        seen_names: set[str] = set()

        if ph_topics:
            # 按 topic 拉取，多 topic 时合并去重
            for topic in ph_topics:
                topic_nodes = _fetch_nodes(token, fetch_per_topic, topic, _query_hint=query)
                logger.info("[ph_search] topic=%r fetched=%d", topic, len(topic_nodes))
                for n in topic_nodes:
                    nm = n.get("name", "")
                    if nm not in seen_names:
                        seen_names.add(nm)
                        nodes.append(n)
        else:
            # 无法映射 topic，降级到最新帖子（覆盖面小，结果质量低）
            nodes = _fetch_nodes(token, max(count * 8, 40), _query_hint=query)
            logger.info("[ph_search] no topic mapping | fetched=%d", len(nodes))

        # 2. 语义重排 + 阈值拒答
        picked = _rerank(nodes, query_text, count)

        # 3. topic 已过滤但语义阈值全拒绝时，返回 topic 内热门项兜底，避免空结果
        if not picked and ph_topics and nodes:
            logger.info("[ph_search] no rerank hit under topic mode, fallback to top-voted")
            fallback_nodes = sorted(nodes, key=lambda x: int(x.get("votesCount") or 0), reverse=True)
            picked = fallback_nodes[:count]

        logger.info(
            "[ph_search] query=%r topics=%s fetched=%d picked=%d",
            query, ph_topics, len(nodes), len(picked),
        )
        return picked
    except Exception as exc:
        logger.warning("[ph_search] failed: %s", exc)
        return []


def _node_to_snapshot(node: dict) -> dict:
    """将 ProductHunt post node 映射为 snapshot schema"""
    topics = [e["node"]["name"] for e in node.get("topics", {}).get("edges", [])]
    votes = node.get("votesCount") or 0

    # 用 votesCount 粗略推断产品规模 → 定价 & 团队规模
    if votes > 2000:
        pricing = random.choice(["freemium", "$29/mo", "$99/mo", "enterprise"])
        team = random.choice(["51-200", "200+"])
    elif votes > 500:
        pricing = random.choice(["freemium", "$9/mo", "$29/mo"])
        team = random.choice(["11-50", "51-200"])
    else:
        pricing = random.choice(["free", "freemium", "$9/mo"])
        team = random.choice(["1-10", "11-50"])

    # 用 topics 填充 core_features，不足 4 个时用通用标签补齐
    fallback_features = ["API", "integrations", "dashboard", "analytics", "collaboration", "mobile app"]
    features = (topics + fallback_features)[:4]

    return {
        "product_name": node.get("name") or "Unknown",
        "pricing": pricing,
        "core_features": features,
        "target_user": topics[0] if topics else "SMBs",
        "positioning": node.get("tagline") or "—",
        "founded_year": None,           # PH 不提供创立年份
        "estimated_team_size": team,
        "website": node.get("website") or "",
        "votes": votes,
        "rating": node.get("reviewsRating"),
        "retrieval_score": node.get("_rank_score"),
        "semantic_score": node.get("_semantic_score"),
        "source": "producthunt",
    }


# ── Mock fallback ────────────────────────────────────────────────────────────
_PRICING_OPTIONS = ["free", "freemium", "$9/mo", "$29/mo", "$99/mo", "enterprise"]
_FEATURES_POOL = [
    "AI generation", "analytics dashboard", "collaboration",
    "integrations", "custom workflows", "API", "mobile app",
    "white-label", "multi-language", "offline mode",
]
_USER_POOL = ["SMBs", "enterprises", "developers", "creators", "students", "marketers"]
_POSITIONING_POOL = [
    "all-in-one platform", "developer-first tool",
    "AI-native solution", "budget-friendly alternative",
    "enterprise-grade platform",
]


def _mock_snapshot(product_name: str) -> dict:
    return {
        "product_name": product_name,
        "pricing": random.choice(_PRICING_OPTIONS),
        "core_features": random.sample(_FEATURES_POOL, k=4),
        "target_user": random.choice(_USER_POOL),
        "positioning": random.choice(_POSITIONING_POOL),
        "founded_year": random.randint(2018, 2025),
        "estimated_team_size": random.choice(["1-10", "11-50", "51-200", "200+"]),
        "source": "mock",
    }


def _contains_cjk(text: str) -> bool:
    return any("\u4e00" <= ch <= "\u9fff" for ch in text)


def _build_query_tokens(query: str) -> list[str]:
    """构建可匹配 token：
    - 英文词法切分
    - 中文场景词扩展（短剧/微短剧等 -> 英文同义词）
    """
    q = (query or "").strip().lower()
    if not q:
        return []

    tokens = set(re.findall(r"[a-z0-9]+", q))

    # 中文直传 token（用于同文匹配）
    if _contains_cjk(q):
        tokens.add(q)

    # 行业关键词扩展：提升中文输入在英文 PH 数据中的召回率
    expansions = {
        "短剧": ["short drama", "micro drama", "vertical drama", "drama app", "series app"],
        "微短剧": ["micro drama", "short drama", "vertical drama"],
        "短视频": ["short video", "reels", "clips", "video app"],
        "追剧": ["watch series", "streaming", "drama app"],
        "剧": ["drama", "series", "streaming"],
        "小说": ["novel", "fiction", "reading app", "web novel", "story app"],
        "网文": ["web novel", "fiction", "reading app"],
        "阅读": ["reading app", "reader", "ebook", "novel"],
        "旅行": ["travel", "trip planner", "itinerary", "booking", "vacation"],
        "旅游": ["travel", "trip planner", "itinerary", "booking", "vacation"],
        "出行": ["travel", "transportation", "trip", "journey planner"],
        "web端": ["web", "web app", "browser"],
        "定时提醒": ["reminder app", "recurring reminder", "scheduled notification", "alarm", "timer", "calendar reminder", "task reminder"],
        "提醒": ["reminder", "notification", "alert", "alarm"],
        "闹钟": ["alarm clock", "alarm app", "wake up alarm", "timer"],
        "日程": ["schedule", "calendar", "agenda", "planner"],
        "待办": ["todo", "task manager", "to-do list", "checklist"],
        "番茄钟": ["pomodoro timer", "focus timer", "productivity timer"],
        "习惯打卡": ["habit tracker", "daily streak", "routine reminder"],
    }

    for zh_kw, en_list in expansions.items():
        if zh_kw in q:
            for phrase in en_list:
                tokens.update(re.findall(r"[a-z0-9]+", phrase.lower()))

    return [t for t in tokens if t]


def _build_query_text(query: str) -> str:
    """自动将中文查询归一成英文可检索表达（含原词 + 英文语义提示）。"""
    q = (query or "").strip()
    tokens = _build_query_tokens(q)

    # 常见中文赛道 -> 英文语义提示
    ql = q.lower()
    hints: list[str] = []
    hint_map = {
        "短剧": "short drama vertical drama app",
        "微短剧": "micro drama short drama app",
        "体育": "sports app live score fan community",
        "小说": "novel fiction reading app web novel story app",
        "网文": "web novel fiction reading app",
        "阅读": "reading app reader ebook novel",
        "记账": "finance budgeting expense tracker app",
        "电商": "ecommerce shopping seller app",
        "招聘": "hiring recruiting jobs app",
        "教育": "education learning app",
        "医疗": "healthcare medical app",
        "旅行": "travel trip planner itinerary booking web app",
        "旅游": "travel trip planner itinerary booking web app",
        "出行": "travel transportation route planner web app",
        "web端": "web app browser platform",
        "定时提醒": "reminder app recurring reminder scheduled notification alarm calendar todo habit tracker",
        "提醒": "reminder notification alert app",
        "闹钟": "alarm clock wake up alarm timer app",
        "日程": "calendar schedule planner agenda app",
        "待办": "todo task manager checklist productivity app",
        "番茄钟": "pomodoro timer focus timer productivity app",
        "习惯打卡": "habit tracker daily streak routine reminder app",
    }
    for k, v in hint_map.items():
        if k in ql:
            hints.append(v)

    # 把原始 query、token 和 hint 合并，保证中文和英文语义都参与评分
    parts = [q] + tokens + hints
    return " ".join(p for p in parts if p).strip()


def _required_domain_tokens(query: str) -> set[str]:
    """对某些中文行业词增加领域约束，避免返回泛热门产品。"""
    q = (query or "").lower()
    if "短剧" in q or "微短剧" in q:
        return {"drama", "series", "video", "streaming", "short", "vertical"}
    if "体育" in q:
        return {"sports", "score", "league", "football", "basketball", "fan"}
    if "小说" in q or "网文" in q or "阅读" in q:
        return {"novel", "fiction", "story", "reading", "reader", "ebook", "book", "literature"}
    return set()


def _tokenize_multilingual(text: str) -> list[str]:
    text = (text or "").lower().strip()
    if not text:
        return []

    tokens = re.findall(r"[a-z0-9]+", text)
    zh_chunks = re.findall(r"[\u4e00-\u9fff]+", text)
    for chunk in zh_chunks:
        tokens.append(chunk)
        if len(chunk) >= 2:
            tokens.extend(chunk[i:i + 2] for i in range(len(chunk) - 1))

    return tokens


def _tf_vector(tokens: list[str]) -> Counter:
    return Counter(tokens)


def _cosine_similarity(a: Counter, b: Counter) -> float:
    if not a or not b:
        return 0.0
    common = set(a.keys()) & set(b.keys())
    dot = sum(a[k] * b[k] for k in common)
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _char_ngrams(text: str, n: int = 3) -> set[str]:
    t = re.sub(r"\s+", "", (text or "").lower())
    if len(t) < n:
        return {t} if t else set()
    return {t[i:i + n] for i in range(len(t) - n + 1)}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def _semantic_similarity(query: str, doc: str) -> float:
    q_tokens = _tokenize_multilingual(query)
    d_tokens = _tokenize_multilingual(doc)
    tf_cos = _cosine_similarity(_tf_vector(q_tokens), _tf_vector(d_tokens))
    char_sim = _jaccard(_char_ngrams(query, 3), _char_ngrams(doc, 3))
    return 0.7 * tf_cos + 0.3 * char_sim


def _keyword_overlap(query: str, doc: str) -> float:
    q = set(_tokenize_multilingual(query))
    d = set(_tokenize_multilingual(doc))
    if not q:
        return 0.0
    return len(q & d) / len(q)


def _popularity_score(votes: int) -> float:
    return min(1.0, math.log1p(max(votes, 0)) / math.log1p(5000))


# ── Tool ─────────────────────────────────────────────────────────────────────
class CompetitorSnapshotTool(BaseTool):
    name = "competitor_snapshot"
    description = "获取竞品基本信息：定价、核心功能、目标用户、定位（ProductHunt API 优先，降级 Mock）"

    def run(self, params: dict[str, Any]) -> dict[str, Any]:
        mode: str = params.get("mode", "lookup")

        # ── search 模式：按关键词搜索多个竞品，返回 {products: [...], source: ...} ──
        if mode == "search":
            search_query: str = params.get("search_query", "")
            count: int = params.get("count", 6)
            token = _get_token()

            if token:
                nodes = _ph_search(search_query, count, token)
                if nodes:
                    products = [_node_to_snapshot(n) for n in nodes]
                    logger.info("[snapshot] search done | source=producthunt | count=%d", len(products))
                    return {"products": products, "source": "producthunt"}
                logger.warning("[snapshot] PH no relevant matches | query=%r", search_query)
                return {
                    "products": [],
                    "source": "producthunt_no_match",
                    "reason": "no relevant ProductHunt matches for query",
                }
            else:
                logger.info("[snapshot] no PRODUCT_HUNT_TOKEN found, using mock")

            # mock fallback for search mode
            seed_count = count if count else 6
            products = [
                _mock_snapshot(f"Competitor-{chr(65 + i)}")
                for i in range(seed_count)
            ]
            return {"products": products, "source": "mock"}

        # ── lookup 模式（默认）：返回单条产品快照 ──
        product_name: str = params.get("product_name", "unknown")
        token = _get_token()
        if token:
            nodes = _ph_search(product_name, 1, token)
            if nodes:
                return _node_to_snapshot(nodes[0])
        return _mock_snapshot(product_name)


register_tool(CompetitorSnapshotTool())
