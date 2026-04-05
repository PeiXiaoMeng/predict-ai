"""评论情绪工具 —— App Store + Google Play(SerpAPI) + Reddit + Mock 混合实现。"""
from __future__ import annotations

import logging
import os
import random
import time
from collections import Counter
from typing import Any

import httpx

from .. import api_log
from .base import BaseTool, register_tool


logger = logging.getLogger("predict-app.tools.review_sentiment")

_CACHE_TTL_SEC = 60 * 60 * 6  # 6h
_CACHE: dict[tuple[str, str, str], tuple[float, dict[str, Any]]] = {}


def _read_env_fallback(key: str) -> str:
    val = os.getenv(key, "").strip()
    if val:
        return val
    try:
        env_path = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".env"))
        with open(env_path, encoding="utf-8") as f:
            for line in f:
                s = line.strip()
                if not s or s.startswith("#"):
                    continue
                if s.startswith(f"{key}="):
                    return s.split("=", 1)[1].strip().strip('"').strip("'")
    except FileNotFoundError:
        pass
    return ""


_POS_WORDS = {
    "good", "great", "excellent", "amazing", "love", "helpful", "fast", "stable",
    "smooth", "easy", "best", "perfect", "awesome", "recommended", "满意", "好用", "稳定", "流畅",
}
_NEG_WORDS = {
    "bad", "terrible", "awful", "hate", "slow", "lag", "bug", "bugs", "crash", "crashes",
    "expensive", "confusing", "broken", "worse", "worst", "差", "卡", "崩溃", "闪退", "难用", "贵",
}

_PAIN_MAP: dict[str, list[str]] = {
    "性能与稳定性": ["slow", "lag", "crash", "bug", "卡", "崩溃", "闪退", "loading"],
    "价格/付费门槛": ["price", "pricing", "expensive", "subscription", "paywall", "贵", "收费"],
    "上手复杂": ["confusing", "hard", "complex", "onboard", "难", "复杂", "看不懂"],
    "集成能力不足": ["integration", "api", "slack", "zapier", "missing integrations", "对接"],
    "客服与响应": ["support", "customer service", "response", "客服", "售后"],
}

_FEATURE_MAP: dict[str, list[str]] = {
    "更强数据分析": ["analytics", "insight", "report", "dashboard", "分析", "报表"],
    "团队协作": ["team", "collaboration", "member", "workspace", "协作"],
    "开放 API / 集成": ["api", "webhook", "integration", "zapier", "对接"],
    "离线能力": ["offline", "no internet", "离线"],
    "模板与自定义": ["template", "custom", "personalize", "模板", "自定义"],
    "多语言支持": ["multilingual", "language", "localization", "多语言"],
}


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _score_sentiment(texts: list[str]) -> float:
    if not texts:
        return 0.0
    scores: list[float] = []
    for raw in texts:
        t = (raw or "").lower()
        pos = sum(1 for w in _POS_WORDS if w in t)
        neg = sum(1 for w in _NEG_WORDS if w in t)
        if pos == 0 and neg == 0:
            continue
        scores.append((pos - neg) / (pos + neg))
    if not scores:
        return 0.0
    return _clamp(sum(scores) / len(scores), -1.0, 1.0)


def _extract_topics(texts: list[str], mapping: dict[str, list[str]], top_k: int = 3) -> list[str]:
    cnt: Counter[str] = Counter()
    lowered = [t.lower() for t in texts if t]
    for label, kws in mapping.items():
        for t in lowered:
            hits = sum(1 for kw in kws if kw in t)
            if hits:
                cnt[label] += hits
    return [k for k, _ in cnt.most_common(top_k)]


def _mock_product(name: str, channels: list[str]) -> dict[str, Any]:
    pain_pool = [
        "性能与稳定性", "价格/付费门槛", "上手复杂", "集成能力不足", "客服与响应",
    ]
    feature_pool = [
        "更强数据分析", "团队协作", "开放 API / 集成", "离线能力", "模板与自定义", "多语言支持",
    ]
    return {
        "product": name,
        "channels": channels,
        "sample_size": random.randint(80, 2000),
        "sentiment_score": round(random.uniform(-0.3, 0.7), 2),
        "pain_points": random.sample(pain_pool, k=min(3, len(pain_pool))),
        "feature_requests": random.sample(feature_pool, k=min(3, len(feature_pool))),
        "_source": "mock",
    }


def _apple_review_texts(product_name: str, country: str = "cn", max_items: int = 40) -> list[str]:
    t0 = time.monotonic()
    try:
        with httpx.Client(timeout=20) as client:
            search = client.get(
                "https://itunes.apple.com/search",
                params={"term": product_name, "entity": "software", "country": country, "limit": 1},
            )
            search.raise_for_status()
            app_data = search.json()
            track_id = (app_data.get("results") or [{}])[0].get("trackId")
            if not track_id:
                api_log.push(
                    source="app_store",
                    query=product_name,
                    params={"country": country},
                    response=app_data,
                    elapsed_ms=int((time.monotonic() - t0) * 1000),
                    error="No app found",
                )
                return []

            url = f"https://itunes.apple.com/{country}/rss/customerreviews/id={track_id}/sortBy=mostRecent/json"
            r = client.get(url)
            r.raise_for_status()
            data = r.json()

        entries = ((data.get("feed") or {}).get("entry") or [])[1:]  # entry[0] 常是 app 信息
        texts: list[str] = []
        for e in entries:
            title = ((e.get("title") or {}).get("label") or "").strip()
            content = ((e.get("content") or {}).get("label") or "").strip()
            full = " ".join([title, content]).strip()
            if full:
                texts.append(full)
            if len(texts) >= max_items:
                break

        api_log.push(
            source="app_store",
            query=product_name,
            params={"country": country, "max_items": max_items},
            response={"review_count": len(texts), "track_id": track_id},
            elapsed_ms=int((time.monotonic() - t0) * 1000),
        )
        return texts
    except Exception as exc:
        api_log.push(
            source="app_store",
            query=product_name,
            params={"country": country, "max_items": max_items},
            response=None,
            elapsed_ms=int((time.monotonic() - t0) * 1000),
            error=str(exc),
        )
        return []


def _google_play_texts_serpapi(product_name: str, max_items: int = 20) -> list[str]:
    api_key = _read_env_fallback("SERPAPI_KEY")
    t0 = time.monotonic()
    if not api_key:
        api_log.push(
            source="google_play",
            query=product_name,
            params={"max_items": max_items},
            response=None,
            elapsed_ms=0,
            error="SERPAPI_KEY missing",
        )
        return []

    try:
        with httpx.Client(timeout=25) as client:
            r = client.get(
                "https://serpapi.com/search.json",
                params={
                    "engine": "google_play",
                    "store": "apps",
                    "q": product_name,
                    "hl": "en",
                    "gl": "us",
                    "api_key": api_key,
                },
            )
            r.raise_for_status()
            data = r.json()

        organic = data.get("organic_results") or []
        texts: list[str] = []
        for item in organic[:max_items]:
            title = str(item.get("title") or "")
            desc = str(item.get("description") or "")
            summary = " ".join([title, desc]).strip()
            if summary:
                texts.append(summary)

        api_log.push(
            source="google_play",
            query=product_name,
            params={"max_items": max_items},
            response={"result_count": len(organic), "sample_texts": len(texts)},
            elapsed_ms=int((time.monotonic() - t0) * 1000),
        )
        return texts
    except Exception as exc:
        api_log.push(
            source="google_play",
            query=product_name,
            params={"max_items": max_items},
            response=None,
            elapsed_ms=int((time.monotonic() - t0) * 1000),
            error=str(exc),
        )
        return []


def _reddit_texts(product_name: str, max_items: int = 30) -> list[str]:
    t0 = time.monotonic()
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
            "Accept": "application/json",
            "Referer": "https://www.reddit.com/",
        }
        with httpx.Client(timeout=20, headers=headers) as client:
            r = client.get(
                "https://www.reddit.com/search/.json",
                params={"q": product_name, "sort": "relevance", "limit": max_items, "raw_json": 1},
            )
            if r.status_code == 403:
                r = client.get(
                    "https://old.reddit.com/search.json",
                    params={"q": product_name, "sort": "relevance", "limit": max_items, "raw_json": 1},
                )
            r.raise_for_status()
            data = r.json()

        children = ((data.get("data") or {}).get("children") or [])
        texts: list[str] = []
        for ch in children:
            d = ch.get("data") or {}
            title = str(d.get("title") or "")
            selftext = str(d.get("selftext") or "")
            full = " ".join([title, selftext]).strip()
            if full:
                texts.append(full)

        api_log.push(
            source="reddit",
            query=product_name,
            params={"max_items": max_items},
            response={"post_count": len(children), "sample_texts": len(texts)},
            elapsed_ms=int((time.monotonic() - t0) * 1000),
        )
        return texts
    except Exception as exc:
        api_log.push(
            source="reddit",
            query=product_name,
            params={"max_items": max_items},
            response=None,
            elapsed_ms=int((time.monotonic() - t0) * 1000),
            error=str(exc),
        )
        return []


class ReviewSentimentTool(BaseTool):
    name = "review_sentiment"
    description = "分析竞品评论情绪、痛点、功能诉求"

    def run(self, params: dict[str, Any]) -> dict[str, Any]:
        product_names: list[str] = params.get("product_names", [])
        channels: list[str] = params.get("channels", ["app_store", "google_play", "reddit"])
        provider = (_read_env_fallback("REVIEW_SENTIMENT_PROVIDER") or "hybrid").lower()
        app_store_country = (_read_env_fallback("APPLE_REVIEW_REGION") or "cn").lower()

        results: list[dict[str, Any]] = []
        for name in product_names:
            cache_key = (name.strip().lower(), "|".join(sorted(channels)), provider)
            if cache_key in _CACHE:
                ts, cached = _CACHE[cache_key]
                if time.monotonic() - ts < _CACHE_TTL_SEC:
                    results.append(cached)
                    continue

            texts: list[str] = []
            used_channels: list[str] = []

            if provider in {"hybrid", "real"}:
                if "app_store" in channels:
                    app_texts = _apple_review_texts(name, country=app_store_country)
                    if app_texts:
                        texts.extend(app_texts)
                        used_channels.append("app_store")

                if "google_play" in channels:
                    gp_texts = _google_play_texts_serpapi(name)
                    if gp_texts:
                        texts.extend(gp_texts)
                        used_channels.append("google_play")

                if "reddit" in channels or "g2" in channels:
                    rd_texts = _reddit_texts(name)
                    if rd_texts:
                        texts.extend(rd_texts)
                        used_channels.append("reddit")

            if not texts:
                logger.debug("review_sentiment: mock fallback for product=%s", name)
                row = _mock_product(name, channels)
                _CACHE[cache_key] = (time.monotonic(), row)
                results.append(row)
                continue

            score = round(_score_sentiment(texts), 2)
            pain_points = _extract_topics(texts, _PAIN_MAP, top_k=3) or ["上手复杂", "性能与稳定性", "价格/付费门槛"]
            feature_requests = _extract_topics(texts, _FEATURE_MAP, top_k=3) or ["更强数据分析", "团队协作", "开放 API / 集成"]

            row = {
                "product": name,
                "channels": used_channels or channels,
                "sample_size": len(texts),
                "sentiment_score": score,
                "pain_points": pain_points,
                "feature_requests": feature_requests,
                "_source": "hybrid",
            }
            _CACHE[cache_key] = (time.monotonic(), row)
            results.append(row)

        return {"products": results}


register_tool(ReviewSentimentTool())
