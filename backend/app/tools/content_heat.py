"""内容热度工具 —— YouTube + Reddit + Mock 混合实现。"""
from __future__ import annotations

import logging
import math
import os
import random
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from .. import api_log
from .base import BaseTool, register_tool


logger = logging.getLogger("predict-app.tools.content_heat")

_CACHE_TTL_SEC = 60 * 60 * 6  # 6h
_CACHE: dict[tuple[str, str, str], tuple[float, dict[str, Any]]] = {}


def _read_env_fallback(key: str) -> str:
    """Read env var from process env first, then from project .env file."""
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


def _mock_breakdown(topics: list[str], platforms: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for topic in topics:
        for platform in platforms:
            rows.append({
                "topic": topic,
                "platform": platform,
                "post_volume": random.randint(200, 20_000),
                "interaction_rate": round(random.uniform(0.5, 8.0), 2),
                "creator_count": random.randint(50, 3_000),
            })
    return rows


def _time_range_to_reddit(time_range: str) -> str:
    tr = (time_range or "30d").lower().strip()
    if tr in {"1d", "7d"}:
        return "week"
    if tr in {"30d", "1m"}:
        return "month"
    if tr in {"90d", "3m", "6m", "12m", "1y", "all"}:
        return "year"
    return "month"


def _time_range_to_published_after(time_range: str) -> str:
    tr = (time_range or "30d").lower().strip()
    days = 30
    if tr.endswith("d"):
        try:
            days = max(1, int(tr[:-1]))
        except Exception:
            days = 30
    elif tr in {"1m"}:
        days = 30
    elif tr in {"3m"}:
        days = 90
    elif tr in {"6m"}:
        days = 180
    elif tr in {"12m", "1y"}:
        days = 365
    elif tr == "all":
        days = 3650
    dt = datetime.now(timezone.utc) - timedelta(days=days)
    return dt.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _estimate_heat_score(rows: list[dict[str, Any]]) -> int:
    if not rows:
        return random.randint(40, 92)

    values = []
    for r in rows:
        post_volume = max(0, int(r.get("post_volume") or 0))
        interaction = max(0.0, float(r.get("interaction_rate") or 0.0))
        creators = max(0, int(r.get("creator_count") or 0))

        volume_norm = min(100.0, (math.log1p(post_volume) / math.log1p(1_000_000)) * 100)
        interaction_norm = min(100.0, interaction * 12.5)  # 8% -> 100
        creator_norm = min(100.0, creators / 5000 * 100)
        values.append(0.45 * volume_norm + 0.25 * interaction_norm + 0.30 * creator_norm)
    return int(round(sum(values) / len(values)))


def _youtube_rows(topics: list[str], time_range: str) -> list[dict[str, Any]]:
    api_key = _read_env_fallback("YOUTUBE_API_KEY")
    if not api_key:
        api_log.push(
            source="youtube",
            query=",".join(topics[:5]) or "(no topic)",
            params={"time_range": time_range},
            response=None,
            elapsed_ms=0,
            error="YOUTUBE_API_KEY missing",
        )
        return []

    rows: list[dict[str, Any]] = []
    published_after = _time_range_to_published_after(time_range)
    headers = {"Accept": "application/json"}

    for topic in topics[:5]:
        t0 = time.perf_counter()
        error: str | None = None
        response_payload: dict[str, Any] | None = None
        try:
            search_params = {
                "key": api_key,
                "part": "snippet",
                "q": topic,
                "type": "video",
                "order": "viewCount",
                "maxResults": 20,
                "publishedAfter": published_after,
            }
            search_resp = httpx.get("https://www.googleapis.com/youtube/v3/search", params=search_params, headers=headers, timeout=10)
            search_resp.raise_for_status()
            search_data = search_resp.json()

            items = search_data.get("items", [])
            video_ids = [it.get("id", {}).get("videoId") for it in items if it.get("id", {}).get("videoId")]
            channel_ids = [it.get("snippet", {}).get("channelId") for it in items if it.get("snippet", {}).get("channelId")]

            post_volume = int(search_data.get("pageInfo", {}).get("totalResults") or len(items))
            creator_count = len(set(channel_ids))

            interaction_rate = 0.0
            if video_ids:
                stats_params = {
                    "key": api_key,
                    "part": "statistics",
                    "id": ",".join(video_ids[:50]),
                    "maxResults": 50,
                }
                stats_resp = httpx.get("https://www.googleapis.com/youtube/v3/videos", params=stats_params, headers=headers, timeout=10)
                stats_resp.raise_for_status()
                stats_data = stats_resp.json()
                rates = []
                for it in stats_data.get("items", []):
                    st = it.get("statistics", {})
                    view = float(st.get("viewCount") or 0)
                    like = float(st.get("likeCount") or 0)
                    cmt = float(st.get("commentCount") or 0)
                    if view > 0:
                        rates.append((like + cmt) / view * 100)
                if rates:
                    interaction_rate = round(sum(rates) / len(rates), 2)

            row = {
                "topic": topic,
                "platform": "youtube",
                "post_volume": post_volume,
                "interaction_rate": interaction_rate,
                "creator_count": creator_count,
            }
            if post_volume > 0 or creator_count > 0 or interaction_rate > 0:
                rows.append(row)

            response_payload = {
                "topic": topic,
                "post_volume": post_volume,
                "creator_count": creator_count,
                "interaction_rate": interaction_rate,
                "sample_titles": [it.get("snippet", {}).get("title", "") for it in items[:5]],
            }
        except Exception as exc:
            error = str(exc)
            logger.warning("[content_heat] youtube failed | topic=%r | %s", topic, exc)
        finally:
            api_log.push(
                source="youtube",
                query=topic,
                params={"publishedAfter": published_after, "maxResults": 20},
                response=response_payload,
                elapsed_ms=round((time.perf_counter() - t0) * 1000),
                error=error,
            )
    return rows


def _reddit_rows(topics: list[str], time_range: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    t_filter = _time_range_to_reddit(time_range)
    serpapi_key = _read_env_fallback("SERPAPI_KEY")

    for topic in topics[:5]:
        t0 = time.perf_counter()
        error: str | None = None
        response_payload: dict[str, Any] | None = None
        try:
            params = {
                "q": topic,
                "sort": "new",
                "limit": 100,
                "t": t_filter,
                "type": "link",
                "raw_json": 1,
            }
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
                "Accept": "application/json",
                "Referer": "https://www.reddit.com/",
            }
            data: dict[str, Any] | None = None

            # 1) 主端点：/search/.json
            resp = httpx.get("https://www.reddit.com/search/.json", params=params, headers=headers, timeout=10)
            if resp.status_code == 403:
                # 2) 备用端点：old.reddit.com
                resp = httpx.get("https://old.reddit.com/search.json", params=params, headers=headers, timeout=10)

            if resp.status_code == 403 and serpapi_key:
                # 3) 二级回退：SerpAPI（site:reddit.com）
                r2 = httpx.get(
                    "https://serpapi.com/search.json",
                    params={
                        "engine": "google",
                        "q": f"site:reddit.com {topic}",
                        "num": 30,
                        "hl": "en",
                        "gl": "us",
                        "api_key": serpapi_key,
                    },
                    timeout=12,
                )
                r2.raise_for_status()
                d2 = r2.json()
                organic = d2.get("organic_results") or []

                post_volume = len(organic)
                creator_count = len({o.get("source") for o in organic if o.get("source")})
                interaction_rate = round(min(100.0, post_volume * 1.8), 2)

                row = {
                    "topic": topic,
                    "platform": "reddit",
                    "post_volume": post_volume,
                    "interaction_rate": interaction_rate,
                    "creator_count": creator_count,
                }
                if post_volume > 0 or creator_count > 0 or interaction_rate > 0:
                    rows.append(row)

                response_payload = {
                    "topic": topic,
                    "post_volume": post_volume,
                    "creator_count": creator_count,
                    "interaction_rate": interaction_rate,
                    "sample_titles": [o.get("title", "") for o in organic[:5]],
                    "fallback": "serpapi_site_reddit",
                }

                api_log.push(
                    source="serpapi",
                    query=f"site:reddit.com {topic}",
                    params={"engine": "google", "num": 30},
                    response={"organic_count": len(organic), "fallback_for": "reddit"},
                    elapsed_ms=round((time.perf_counter() - t0) * 1000),
                    error=None,
                )
                error = None
                continue

            resp.raise_for_status()
            data = resp.json()

            children = data.get("data", {}).get("children", [])
            posts = [c.get("data", {}) for c in children]
            post_volume = int(data.get("data", {}).get("dist") or len(posts))

            authors = {p.get("author") for p in posts if p.get("author") and p.get("author") != "[deleted]"}
            creator_count = len(authors)

            interactions = [(int(p.get("score") or 0) + int(p.get("num_comments") or 0)) for p in posts]
            avg_interactions = (sum(interactions) / len(interactions)) if interactions else 0.0
            interaction_rate = round(min(100.0, avg_interactions / 20), 2)

            row = {
                "topic": topic,
                "platform": "reddit",
                "post_volume": post_volume,
                "interaction_rate": interaction_rate,
                "creator_count": creator_count,
            }
            if post_volume > 0 or creator_count > 0 or interaction_rate > 0:
                rows.append(row)

            response_payload = {
                "topic": topic,
                "post_volume": post_volume,
                "creator_count": creator_count,
                "interaction_rate": interaction_rate,
                "sample_titles": [p.get("title", "") for p in posts[:5]],
                "fallback": "none",
            }
        except Exception as exc:
            error = str(exc)
            logger.warning("[content_heat] reddit failed | topic=%r | %s", topic, exc)
        finally:
            api_log.push(
                source="reddit",
                query=topic,
                params={"t": t_filter, "limit": 100},
                response=response_payload,
                elapsed_ms=round((time.perf_counter() - t0) * 1000),
                error=error,
            )
    return rows


class ContentHeatTool(BaseTool):
    name = "content_heat"
    description = "衡量特定话题在内容平台上的发布量、互动率、创作者数"

    def run(self, params: dict[str, Any]) -> dict[str, Any]:
        topics: list[str] = params.get("topics", [])
        platforms: list[str] = params.get("platforms", ["youtube", "reddit"])
        time_range: str = params.get("time_range", "30d")
        provider: str = str(params.get("provider", os.getenv("CONTENT_HEAT_PROVIDER", "hybrid"))).lower().strip()

        cache_key = (
            "|".join(sorted([t.strip().lower() for t in topics if t.strip()])),
            "|".join(sorted([p.strip().lower() for p in platforms if p.strip()])),
            f"{time_range.lower()}|{provider}",
        )
        now = time.time()
        cached = _CACHE.get(cache_key)
        if cached and now - cached[0] < _CACHE_TTL_SEC:
            return dict(cached[1])

        breakdown: list[dict[str, Any]] = []

        want_youtube = "youtube" in {p.lower() for p in platforms}
        want_reddit = "reddit" in {p.lower() for p in platforms}

        if provider in {"youtube", "hybrid"} and want_youtube:
            breakdown.extend(_youtube_rows(topics, time_range))

        if provider in {"reddit", "hybrid"} and want_reddit:
            breakdown.extend(_reddit_rows(topics, time_range))

        source = "hybrid"
        valid_signal = any(
            (int(r.get("post_volume") or 0) > 0)
            or (int(r.get("creator_count") or 0) > 0)
            or (float(r.get("interaction_rate") or 0) > 0)
            for r in breakdown
        )

        if not breakdown or not valid_signal:
            source = "mock"
            breakdown = _mock_breakdown(topics, platforms)

        result = {
            "time_range": time_range,
            "breakdown": breakdown,
            "overall_heat_score": _estimate_heat_score(breakdown),
            "source": source,
        }
        _CACHE[cache_key] = (now, result)
        return result


register_tool(ContentHeatTool())
