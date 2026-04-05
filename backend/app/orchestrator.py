from __future__ import annotations

import logging
from datetime import datetime, timezone

from .agents.workflow import run_competitor_agent, run_market_agent, run_roi_agent, run_strategy_agent
from .schemas import AnalyzeRequest


logger = logging.getLogger("predict-app.orchestrator")


def run_full_analysis(req: AnalyzeRequest) -> dict:
    logger.info("[pipeline] start | product_name=%s", req.product_name)
    competitor = run_competitor_agent(req)
    logger.info("[pipeline] competitor done | count=%s", len(competitor.get("competitors", [])))
    market = run_market_agent(req, competitor)
    logger.info(
        "[pipeline] market done | heat=%s | demand=%s | crowded=%s",
        market.get("track_heat", {}).get("score"),
        market.get("demand_strength", {}).get("score"),
        market.get("competition_crowdedness", {}).get("score"),
    )
    roi = run_roi_agent(req, market)
    logger.info("[pipeline] roi done | recommendation=%s", roi.get("recommendation"))
    strategy = run_strategy_agent(req, competitor, market, roi)
    logger.info("[pipeline] strategy done | roadmap_phases=%s", len(strategy.get("roadmap", [])))

    confidence_values = [
        market.get("track_heat", {}).get("confidence", 0.5),
        market.get("demand_strength", {}).get("confidence", 0.5),
        market.get("competition_crowdedness", {}).get("confidence", 0.5),
    ]
    overall_confidence = round(sum(confidence_values) / len(confidence_values), 2)

    result = {
        "meta": {
            "project_name": req.product_name,
            "analysis_time": datetime.now(timezone.utc).isoformat(),
            "confidence": overall_confidence,
        },
        "competitor_research": competitor,
        "market_judgement": market,
        "roi_estimation": roi,
        "strategy_advice": strategy,
    }

    logger.info("[pipeline] finish | product_name=%s | confidence=%s", req.product_name, overall_confidence)
    return result
