# API debug log monitor router.
from __future__ import annotations
import os
from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from .. import api_log

router = APIRouter(prefix="/debug", tags=["debug"])
_HTML_PATH = os.path.join(os.path.dirname(__file__), "_debug_ui.html")

@router.get("/logs")
def get_logs() -> dict:
    entries = api_log.all_entries()
    return {"count": len(entries), "items": entries}

@router.delete("/logs")
def clear_logs() -> dict:
    api_log.clear()
    return {"status": "cleared"}

@router.get("/ui", response_class=HTMLResponse)
def debug_ui() -> HTMLResponse:
    with open(_HTML_PATH, encoding="utf-8") as f:
        html = f.read()
    return HTMLResponse(content=html)
