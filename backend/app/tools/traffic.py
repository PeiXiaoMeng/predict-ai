"""流量估算工具 —— DataForSEO SimilarWeb + Mock 混合实现。

环境变量:
  TRAFFIC_PROVIDER=hybrid|dataforseo|mock  (默认 hybrid)
  DATAFORSEO_LOGIN=your_email
  DATAFORSEO_PASSWORD=your_password

DataForSEO 注册（免费额度）:
  https://app.dataforseo.com/register
费用约 $0.002/域名，首次注册赠送约 $1 额度（可查约 500 个域名）。
"""
from __future__ import annotations

import logging
import os
import random
import time
from typing import Any

import httpx

from .. import api_log
from .base import BaseTool, register_tool

logger = logging.getLogger("predict-app.tools.traffic")

_CACHE_TTL_SEC = 60 * 60 * 6  # 6h
_CACHE: dict[tuple[str, str], tuple[float, dict[str, Any]]] = {}

# DataForSEO SimilarWeb Overview (Live) endpoint
_DFS_URL = "https://api.dataforseo.com/v3/similarweb/overview/live"


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _read_env_fallback(key: str) -> str:
    """进程环境变量优先，找不到再读 .env 文件。"""
    val = os.getenv(key, "").strip()
    if val:
        return val
    try:
        env_path = os.path.normpath(
            os.path.join(os.path.dirname(__file__), "..", "..", "..", ".env")
        )
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


def _region_to_country(region: str) -> str:
    mapping = {
        "cn": "CN", "china": "CN",
        "us": "US", "usa": "US",
        "uk": "GB", "gb": "GB",
        "jp": "JP", "de": "DE", "kr": "KR",
        "sg": "SG", "in": "IN",
        "global": "US",
    }
    return mapping.get((region or "global").lower(), "US")


def _norm_sources(raw: dict) -> dict[str, float]:
    """把 DataForSEO 返回的 traffic_sources 规范化为 0-1 小数。"""
    keys = ("organic_search", "paid_search", "social", "direct", "referral")
    result = {}
    total = 0.0
    for k in keys:
        v = float(raw.get(k) or 0)
        result[k] = v
        total += v
    # 如果数据是百分比（0-100）就换算成小数
    if total > 2.0:
        result = {k: round(v / 100, 4) for k, v in result.items()}
    else:
        result = {k: round(v, 4) for k, v in result.items()}
    return result


def _mock_site(domain: str) -> dict[str, Any]:
    """单域名的 mock 数据（备用）。"""
    return {
        "domain": domain,
        "monthly_visits": random.randint(50_000, 5_000_000),
        "traffic_sources": {
            "organic_search": round(random.uniform(0.15, 0.50), 2),
            "paid_search": round(random.uniform(0.05, 0.25), 2),
            "social": round(random.uniform(0.05, 0.20), 2),
            "direct": round(random.uniform(0.15, 0.40), 2),
            "referral": round(random.uniform(0.02, 0.15), 2),
        },
        "engagement": {
            "avg_visit_duration_sec": random.randint(60, 480),
            "pages_per_visit": round(random.uniform(1.5, 6.0), 1),
            "bounce_rate": round(random.uniform(0.25, 0.70), 2),
        },
        "_source": "mock",
    }


# ---------------------------------------------------------------------------
# DataForSEO provider
# ---------------------------------------------------------------------------

def _dataforseo_sites(domains: list[str], region: str) -> list[dict[str, Any]]:
    login = _read_env_fallback("DATAFORSEO_LOGIN")
    password = _read_env_fallback("DATAFORSEO_PASSWORD")

    if not login or not password:
        api_log.push(
            source="dataforseo",
            query=",".join(domains[:5]),
            params={"region": region},
            response=None,
            elapsed_ms=0,
            error="DATAFORSEO_LOGIN / DATAFORSEO_PASSWORD 未配置，请在 .env 中填写",
        )
        return []

    country = _region_to_country(region)
    tasks = [{"target": d, "country_code": country} for d in domains]
    t0 = time.monotonic()

    try:
        with httpx.Client(auth=(login, password), timeout=25) as client:
            resp = client.post(_DFS_URL, json=tasks)
        elapsed = int((time.monotonic() - t0) * 1000)
        resp.raise_for_status()
        data = resp.json()

        top_code = data.get("status_code")
        if top_code != 20000:
            api_log.push(
                source="dataforseo",
                query=",".join(domains[:5]),
                params={"region": region, "country": country},
                response=data,
                elapsed_ms=elapsed,
                error=f"API error {top_code}: {data.get('status_message', '')}",
            )
            return []

        results: list[dict[str, Any]] = []
        for task in data.get("tasks", []):
            if task.get("status_code") != 20000:
                continue
            for item in task.get("result", []) or []:
                target = item.get("target", "")
                metrics = item.get("metrics", {}) or {}

                # DataForSEO 返回结构：metrics[country_code] 或 metrics["global"]
                country_data = (
                    metrics.get(country)
                    or metrics.get(country.lower())
                    or metrics.get("global")
                    or {}
                )

                monthly_visits = int(float(country_data.get("visits") or 0))
                traffic_dist = country_data.get("traffic_sources") or {}
                engagement_raw = country_data.get("engagement") or {}

                results.append({
                    "domain": target,
                    "monthly_visits": monthly_visits,
                    "traffic_sources": _norm_sources(traffic_dist),
                    "engagement": {
                        "avg_visit_duration_sec": int(float(
                            engagement_raw.get("avg_visit_duration")
                            or engagement_raw.get("average_visit_duration")
                            or 0
                        )),
                        "pages_per_visit": round(
                            float(engagement_raw.get("pages_per_visit") or 0), 1
                        ),
                        "bounce_rate": round(
                            float(engagement_raw.get("bounce_rate") or 0), 4
                        ),
                    },
                    "_source": "dataforseo",
                })

        api_log.push(
            source="dataforseo",
            query=",".join(domains[:5]),
            params={"region": region, "country": country, "domain_count": len(domains)},
            response={
                "fetched": len(results),
                "domains": [r["domain"] for r in results],
                "sample_visits": results[0]["monthly_visits"] if results else None,
            },
            elapsed_ms=elapsed,
        )
        return results

    except httpx.HTTPStatusError as exc:
        elapsed = int((time.monotonic() - t0) * 1000)
        api_log.push(
            source="dataforseo",
            query=",".join(domains[:5]),
            params={"region": region},
            response=None,
            elapsed_ms=elapsed,
            error=f"HTTP {exc.response.status_code}: {exc.response.text[:300]}",
        )
        return []

    except Exception as exc:
        elapsed = int((time.monotonic() - t0) * 1000)
        api_log.push(
            source="dataforseo",
            query=",".join(domains[:5]),
            params={"region": region},
            response=None,
            elapsed_ms=elapsed,
            error=str(exc),
        )
        return []


# ---------------------------------------------------------------------------
# Tool
# ---------------------------------------------------------------------------

class TrafficEstimationTool(BaseTool):
    name = "traffic_estimation"
    description = "估算竞品域名的月访问量、流量来源、互动指标"

    def run(self, params: dict[str, Any]) -> dict[str, Any]:
        domains: list[str] = params.get("domains", [])
        region: str = params.get("region", "global")
        provider = _read_env_fallback("TRAFFIC_PROVIDER") or "hybrid"

        # 缓存检查
        cache_key = ("|".join(sorted(domains)), region)
        if cache_key in _CACHE:
            ts, cached = _CACHE[cache_key]
            if time.monotonic() - ts < _CACHE_TTL_SEC:
                return cached

        real_sites: list[dict[str, Any]] = []

        # 调用真实 API
        if provider in ("dataforseo", "hybrid"):
            real_sites = _dataforseo_sites(domains, region)

        # 对未覆盖的域名用 mock 补齐
        covered = {s["domain"] for s in real_sites}
        for domain in domains:
            if domain not in covered:
                logger.debug("traffic: mock fallback for domain=%s", domain)
                real_sites.append(_mock_site(domain))

        result = {"region": region, "sites": real_sites}
        _CACHE[cache_key] = (time.monotonic(), result)
        return result


register_tool(TrafficEstimationTool())
