from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Literal

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .orchestrator import run_full_analysis
from .routers.debug import router as debug_router
from .schemas import AnalyzeRequest, AnalyzeResponse, HealthResponse
from .services.report_exporter import export_json, export_markdown
from .tools import list_tools  # noqa: F401  — triggers tool registration


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("predict-app.api")

app = FastAPI(title="Product Prospect Analyzer", version="0.3.0")

# ── Debug Router ──
app.include_router(debug_router)

# ── CORS（开发时允许前端 localhost） ──
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", time=datetime.utcnow())


@app.post("/v1/analyze", response_model=AnalyzeResponse)
def analyze(payload: AnalyzeRequest) -> AnalyzeResponse:
    start = time.perf_counter()
    logger.info(
        "[analyze] request received | product_name=%s | target_users=%s | budget_monthly=%s | desc_len=%s",
        payload.product_name,
        payload.target_users,
        payload.budget_monthly,
        len(payload.product_description or ""),
    )
    result = run_full_analysis(payload)
    elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
    logger.info(
        "[analyze] completed | product_name=%s | confidence=%s | elapsed_ms=%s",
        payload.product_name,
        result.get("meta", {}).get("confidence"),
        elapsed_ms,
    )
    return AnalyzeResponse(**result)


class ExportRequest(BaseModel):
    data: dict
    format: Literal["markdown", "json"] = "markdown"


@app.post("/v1/export")
def export_report(payload: ExportRequest) -> Response:
    if payload.format == "markdown":
        content = export_markdown(payload.data)
        return Response(content=content, media_type="text/markdown",
                        headers={"Content-Disposition": "attachment; filename=report.md"})
    else:
        content = export_json(payload.data)
        return Response(content=content, media_type="application/json",
                        headers={"Content-Disposition": "attachment; filename=report.json"})


@app.get("/v1/tools")
def tools_list() -> dict:
    return {"tools": list_tools()}
