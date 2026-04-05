"""搜索趋势工具 —— Google Trends 优先，SerpAPI 兜底，失败回退 mock。"""
from __future__ import annotations

import logging
import os
import random
import time
import importlib
from typing import Any

import httpx

from .base import BaseTool, register_tool
from .. import api_log

logger = logging.getLogger("predict-app.tools.search_trends")

_CACHE_TTL_SEC = 60 * 60 * 24  # 24h
_CACHE: dict[tuple[str, str, str], tuple[float, dict[str, Any]]] = {}


def _normalize_region(region: str) -> str:
    """将业务 region 映射为 pytrends geo。"""
    region = (region or "global").strip().lower()
    mapping = {
        "global": "",
        "world": "",
        "cn": "CN",
        "china": "CN",
        "us": "US",
        "usa": "US",
        "uk": "GB",
        "jp": "JP",
        "in": "IN",
    }
    return mapping.get(region, "")


def _normalize_time_range(time_range: str) -> str:
    """将 time_range 映射为 pytrends timeframe。"""
    tr = (time_range or "12m").strip().lower()
    mapping = {
        "1m": "today 1-m",
        "3m": "today 3-m",
        "6m": "today 6-m",
        "12m": "today 12-m",
        "1y": "today 12-m",
        "5y": "today 5-y",
        "all": "all",
    }
    return mapping.get(tr, "today 12-m")


def _to_direction(last: float, prev: float) -> str:
    if last >= prev + 3:
        return "rising"
    if last <= prev - 3:
        return "declining"
    return "stable"


def _infer_seasonality(avg_std: float) -> str:
    if avg_std >= 22:
        return "strong_seasonal"
    if avg_std >= 10:
        return "mild_q4_peak"
    return "none"


def _mock_data(keywords: list[str], region: str, time_range: str) -> dict[str, Any]:
    trend_data = []
    for kw in keywords:
        trend_data.append({
            "keyword": kw,
            "trend_index": random.randint(30, 95),
            "trend_direction": random.choice(["rising", "stable", "declining"]),
            "related_queries": [f"{kw} alternative", f"{kw} vs X", f"best {kw}"],
        })
    return {
        "region": region,
        "time_range": time_range,
        "trends": trend_data,
        "seasonality": random.choice(["none", "mild_q4_peak", "strong_seasonal"]),
        "source": "mock",
    }


def _google_trends_data(keywords: list[str], region: str, time_range: str) -> dict[str, Any] | None:
    """使用 pytrends 拉取趋势（失败返回 None）。"""
    try:
        TrendReq = importlib.import_module("pytrends.request").TrendReq
    except Exception:
        logger.info("[search_trends] pytrends not available")
        return None

    if not keywords:
        return {
            "region": region,
            "time_range": time_range,
            "trends": [],
            "seasonality": "none",
            "source": "google_trends",
        }

    try:
        geo = _normalize_region(region)
        timeframe = _normalize_time_range(time_range)
        pytrends = TrendReq(hl="en-US", tz=0)

        trend_data: list[dict[str, Any]] = []
        std_values: list[float] = []

        for kw in keywords[:5]:
            pytrends.build_payload([kw], cat=0, timeframe=timeframe, geo=geo)
            df = pytrends.interest_over_time()
            if df.empty or kw not in df.columns:
                continue

            values = [float(v) for v in df[kw].tolist()]
            if not values:
                continue

            last = values[-1]
            prev = sum(values[-4:-1]) / max(len(values[-4:-1]), 1)
            trend_index = int(round(sum(values) / len(values)))
            direction = _to_direction(last, prev)

            # 相关查询（失败也不影响主流程）
            related: list[str] = []
            try:
                rq = pytrends.related_queries()
                top_df = rq.get(kw, {}).get("top") if rq else None
                if top_df is not None and not top_df.empty and "query" in top_df.columns:
                    related = [str(x) for x in top_df["query"].head(5).tolist()]
            except Exception:
                related = []

            mean = sum(values) / len(values)
            variance = sum((x - mean) ** 2 for x in values) / len(values)
            std_values.append(variance ** 0.5)

            trend_data.append({
                "keyword": kw,
                "trend_index": trend_index,
                "trend_direction": direction,
                "related_queries": related or [f"{kw} alternative", f"best {kw}"],
            })

        if not trend_data:
            api_log.push(
                source="google_trends",
                query=",".join(keywords),
                params={"geo": geo, "timeframe": timeframe},
                response=None,
                elapsed_ms=0,
                error="no data returned for any keyword",
            )
            return None

        avg_std = (sum(std_values) / len(std_values)) if std_values else 0.0
        result = {
            "region": region,
            "time_range": time_range,
            "trends": trend_data,
            "seasonality": _infer_seasonality(avg_std),
            "source": "google_trends",
        }
        api_log.push(
            source="google_trends",
            query=",".join(keywords),
            params={"geo": geo, "timeframe": timeframe, "keywords": keywords},
            response=result,
            elapsed_ms=0,
        )
        return result
    except Exception as exc:
        logger.warning("[search_trends] google trends failed: %s", exc)
        api_log.push(
            source="google_trends",
            query=",".join(keywords),
            params={"region": region, "time_range": time_range},
            response=None,
            elapsed_ms=0,
            error=str(exc),
        )
        return None


def _serpapi_data(keywords: list[str], region: str, time_range: str) -> dict[str, Any] | None:
    """使用 SerpAPI 的 Google Trends 引擎拉取趋势（失败返回 None）。"""
    api_key = os.getenv("SERPAPI_KEY", "").strip()
    if not api_key:
        return None

    try:
        trend_data: list[dict[str, Any]] = []
        std_values: list[float] = []
        for kw in keywords[:5]:
            params = {
                "engine": "google_trends",
                "q": kw,
                "api_key": api_key,
                "data_type": "TIMESERIES",
                "geo": _normalize_region(region) or "US",
                "date": (time_range or "today 12-m"),
            }
            resp = httpx.get("https://serpapi.com/search.json", params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()

            # 尽量宽松解析，字段兼容不同响应形态
            timeline = (
                data.get("interest_over_time", {}).get("timeline_data")
                or data.get("timeline_data")
                or []
            )
            values: list[float] = []
            for item in timeline:
                vals = item.get("values") or []
                if vals and isinstance(vals, list):
                    raw = vals[0].get("extracted_value") if isinstance(vals[0], dict) else vals[0]
                    try:
                        values.append(float(raw))
                    except Exception:
                        pass

            if not values:
                continue

            last = values[-1]
            prev = sum(values[-4:-1]) / max(len(values[-4:-1]), 1)
            trend_index = int(round(sum(values) / len(values)))
            direction = _to_direction(last, prev)

            mean = sum(values) / len(values)
            variance = sum((x - mean) ** 2 for x in values) / len(values)
            std_values.append(variance ** 0.5)

            related = [f"{kw} alternative", f"{kw} vs competitors", f"best {kw}"]
            trend_data.append({
                "keyword": kw,
                "trend_index": trend_index,
                "trend_direction": direction,
                "related_queries": related,
            })

        if not trend_data:
            api_log.push(
                source="serpapi",
                query=",".join(keywords),
                params={"region": region, "time_range": time_range},
                response=None,
                elapsed_ms=0,
                error="no timeline data returned",
            )
            return None

        avg_std = (sum(std_values) / len(std_values)) if std_values else 0.0
        result = {
            "region": region,
            "time_range": time_range,
            "trends": trend_data,
            "seasonality": _infer_seasonality(avg_std),
            "source": "serpapi",
        }
        api_log.push(
            source="serpapi",
            query=",".join(keywords),
            params={"region": region, "time_range": time_range, "keywords": keywords},
            response=result,
            elapsed_ms=0,
        )
        return result
    except Exception as exc:
        logger.warning("[search_trends] serpapi failed: %s", exc)
        api_log.push(
            source="serpapi",
            query=",".join(keywords),
            params={"region": region, "time_range": time_range},
            response=None,
            elapsed_ms=0,
            error=str(exc),
        )
        return None


class SearchTrendsTool(BaseTool):
    name = "search_trends"
    description = "获取关键词搜索趋势、相关查询、季节性"

    def run(self, params: dict[str, Any]) -> dict[str, Any]:
        keywords: list[str] = params.get("keywords", [])
        region: str = params.get("region", "global")
        time_range: str = params.get("time_range", "12m")
        provider: str = str(params.get("provider", os.getenv("SEARCH_TRENDS_PROVIDER", "hybrid"))).lower().strip()

        cache_key = (
            "|".join([k.strip().lower() for k in keywords]),
            region.lower(),
            time_range.lower(),
            provider,
        )
        now = time.time()
        cached = _CACHE.get(cache_key)
        if cached and now - cached[0] < _CACHE_TTL_SEC:
            return dict(cached[1])

        result: dict[str, Any] | None = None

        # hybrid: Google Trends -> SerpAPI -> Mock
        if provider in {"google", "google_trends", "hybrid"}:
            result = _google_trends_data(keywords, region, time_range)

        if result is None and provider in {"serpapi", "hybrid"}:
            result = _serpapi_data(keywords, region, time_range)

        if result is None:
            result = _mock_data(keywords, region, time_range)

        _CACHE[cache_key] = (now, result)
        return result


# 自注册
register_tool(SearchTrendsTool())
