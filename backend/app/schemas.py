from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class AnalyzeRequest(BaseModel):
    product_name: str = Field(..., description="产品名称")
    product_description: str = Field(..., description="产品描述")
    target_users: list[str] = Field(default_factory=list)
    budget_monthly: float = Field(default=0, ge=0)
    hypothesis: dict = Field(default_factory=dict, description="可选：ROI 模型假设参数")


class ScoreItem(BaseModel):
    score: int = Field(..., ge=0, le=100)
    confidence: float = Field(..., ge=0, le=1)
    reason: str


class Scenario(BaseModel):
    cac: float
    retention_m3: float
    paid_conversion: float
    arppu: float
    payback_period_months: float


class AnalyzeResponse(BaseModel):
    meta: dict
    competitor_research: dict
    market_judgement: dict
    roi_estimation: dict
    strategy_advice: dict


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    time: datetime
