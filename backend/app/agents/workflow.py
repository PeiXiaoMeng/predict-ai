from __future__ import annotations

import logging
import random

from ..tools import get_tool
from .prompts import COMPETITOR_PROMPT, MARKET_PROMPT, ROI_PROMPT, STRATEGY_PROMPT


logger = logging.getLogger("predict-app.agents")


# ---------------------------------------------------------------------------
# 1. 竞品研究 Agent
# ---------------------------------------------------------------------------

def run_competitor_agent(req) -> dict:
    """调用工具获取竞品快照，再组装为竞品地图。

    优先通过 CompetitorSnapshotTool 的 search 模式调用 ProductHunt API
    获取真实竞品；若无 Token 或请求失败则降级为 Mock 名称。
    """
    _ = COMPETITOR_PROMPT  # TODO: 未来送入 LLM
    logger.info("[competitor] start | product_name=%s", req.product_name)

    snapshot_tool = get_tool("competitor_snapshot")
    count = random.randint(5, 8)

    # ── 尝试 ProductHunt search 模式 ─────────────────────────────────────
    search_result = snapshot_tool.run({
        "mode": "search",
        "search_query": req.product_name,
        "count": count,
    })
    snapshots: list[dict] = search_result.get("products", [])
    data_source: str = search_result.get("source", "mock")
    search_reason: str = search_result.get("reason", "")
    logger.info("[competitor] fetched | source=%s | count=%d", data_source, len(snapshots))

    competitors = []
    points = []
    for snap in snapshots:
        name = snap["product_name"]
        segment = random.choice(["direct", "adjacent", "substitute"])

        # 证据字段：真实数据比 mock 更丰富
        evidence_parts = [f"team_size={snap['estimated_team_size']}"]
        if snap.get("votes"):
            evidence_parts.append(f"ph_votes={snap['votes']}")
        if snap.get("rating"):
            evidence_parts.append(f"rating={snap['rating']}")
        if snap.get("website"):
            evidence_parts.append(snap["website"])
        if snap.get("founded_year"):
            evidence_parts.append(f"since={snap['founded_year']}")

        competitors.append({
            "name": name,
            "segment": segment,
            "pricing": snap["pricing"],
            "core_features": snap["core_features"],
            "differentiators": [snap["positioning"]],
            "evidence": evidence_parts,
        })
        points.append({"name": name, "x": random.randint(20, 95), "y": random.randint(20, 95)})

    result = {
        "segments": ["direct", "adjacent", "substitute"],
        "competitors": competitors,
        "competitor_map": {
            "x_axis": "user_value",
            "y_axis": "implementation_complexity",
            "points": points,
        },
        "data_source": data_source,  # 透传来源供前端/日志参考
    }

    if not competitors and data_source == "producthunt_no_match":
        result["notice"] = (
            f"ProductHunt 未检索到与“{req.product_name}”高度相关的竞品；"
            "已自动进行中文→英文语义检索，仍无有效匹配。建议补充领域数据源。"
        )
        if search_reason:
            result["search_reason"] = search_reason

    logger.info("[competitor] done | count=%s | source=%s", len(competitors), data_source)
    return result


# ---------------------------------------------------------------------------
# 2. 市场判断 Agent
# ---------------------------------------------------------------------------

def run_market_agent(req, competitor) -> dict:
    """汇总搜索、流量、内容、评论四个工具的输出来打分"""
    _ = (MARKET_PROMPT, competitor)

    keywords = req.product_name.split() + req.target_users[:3]
    competitor_names = [c["name"] for c in competitor.get("competitors", [])[:5]]
    domains = [f"{n.lower().replace(' ', '')}.com" for n in competitor_names[:4]]

    # 调工具
    search_result = get_tool("search_trends").run({"keywords": keywords, "region": "global", "time_range": "12m"})
    traffic_result = get_tool("traffic_estimation").run({"domains": domains, "region": "global"})
    content_result = get_tool("content_heat").run({"topics": keywords[:3], "platforms": ["twitter", "youtube", "reddit"]})
    sentiment_result = get_tool("review_sentiment").run({"product_names": competitor_names[:4], "channels": ["app_store", "google_play", "reddit"]})

    # 简单加权打分
    search_score = sum(t["trend_index"] for t in search_result["trends"]) / max(len(search_result["trends"]), 1)
    traffic_score = min(100, sum(s["monthly_visits"] for s in traffic_result["sites"]) / max(len(traffic_result["sites"]), 1) / 50_000)
    content_score = content_result["overall_heat_score"]
    sentiment_avg = sum(p["sentiment_score"] for p in sentiment_result["products"]) / max(len(sentiment_result["products"]), 1)
    sentiment_score = int((sentiment_avg + 1) / 2 * 100)  # [-1,1] -> [0,100]

    w = {"search": 0.30, "traffic": 0.25, "content": 0.20, "sentiment": 0.25}
    weighted_total = (
        search_score * w["search"]
        + traffic_score * w["traffic"]
        + content_score * w["content"]
        + sentiment_score * w["sentiment"]
    )

    return {
        "track_heat": {"score": int(weighted_total), "confidence": round(random.uniform(0.55, 0.85), 2), "reason": "aggregated from tools"},
        "demand_strength": {"score": int(sentiment_score), "confidence": round(random.uniform(0.50, 0.80), 2), "reason": "review sentiment"},
        "competition_crowdedness": {"score": min(100, len(competitor.get("competitors", [])) * 12), "confidence": round(random.uniform(0.50, 0.75), 2), "reason": f"{len(competitor.get('competitors', []))} competitors found"},
        "signal_breakdown": [
            {"signal": "search", "value": round(search_score, 1), "weight": w["search"]},
            {"signal": "traffic", "value": round(traffic_score, 1), "weight": w["traffic"]},
            {"signal": "content", "value": content_score, "weight": w["content"]},
            {"signal": "sentiment", "value": sentiment_score, "weight": w["sentiment"]},
        ],
    }


def _payback_months(cac: float, paid_conversion: float, arppu: float, monthly_retention: float, service_cost: float = 1.0):
    total = 0.0
    month = 0
    retained = 1.0
    while month < 36:
        month += 1
        gm = paid_conversion * arppu * retained - service_cost * retained
        total += gm
        if total >= cac:
            return month
        retained *= monthly_retention
    return 999


def run_roi_agent(req, market):
    _ = ROI_PROMPT
    scenarios = {
        "conservative": {"cac": 120, "retention_m3": 0.22, "paid_conversion": 0.03, "arppu": 18},
        "base": {"cac": 85, "retention_m3": 0.32, "paid_conversion": 0.05, "arppu": 22},
        "aggressive": {"cac": 60, "retention_m3": 0.42, "paid_conversion": 0.07, "arppu": 28},
    }

    for key, s in scenarios.items():
        monthly_retention = max(min(s["retention_m3"] ** (1 / 3), 0.99), 0.5)
        s["payback_period_months"] = _payback_months(
            cac=s["cac"],
            paid_conversion=s["paid_conversion"],
            arppu=s["arppu"],
            monthly_retention=monthly_retention,
            service_cost=1.2,
        )

    base_pb = scenarios["base"]["payback_period_months"]
    conservative_pb = scenarios["conservative"]["payback_period_months"]

    if base_pb <= 9 and conservative_pb <= 15:
        rec = "go"
    elif base_pb <= 15:
        rec = "wait"
    else:
        rec = "no-go"

    return {
        "scenarios": scenarios,
        "recommendation": rec,
        "stop_loss_rule": {
            "window_days": 60,
            "kpi": "activation_rate & d7_retention",
            "threshold": "activation<20% and d7<15%",
            "action": "pause paid acquisition, keep low-cost experiments",
        },
    }


def run_strategy_agent(req, competitor, market, roi):
    _ = (STRATEGY_PROMPT, req, competitor, market, roi)
    return {
        "launch_strategy": "先聚焦单一核心场景，先验证留存，再考虑扩张",
        "mvp_do": [
            "一条核心工作流",
            "新手引导 + 激活漏斗",
            "基础付费闭环",
            "反馈收集机制",
        ],
        "mvp_not_do": ["复杂协作", "多平台同步", "重度自定义"],
        "roadmap": [
            {
                "phase": "P0",
                "goal": "问题-方案匹配",
                "deliverables": ["落地页", "核心流程"],
                "metric": "activation_rate",
            },
            {
                "phase": "P1",
                "goal": "留存验证",
                "deliverables": ["习惯回路", "通知机制"],
                "metric": "d7_retention",
            },
            {
                "phase": "P2",
                "goal": "商业化验证",
                "deliverables": ["定价实验"],
                "metric": "paid_conversion",
            },
        ],
    }
