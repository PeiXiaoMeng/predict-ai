"""API 调用日志仓库（进程内共享，重启清零）。

各工具调用外部 API 后，调用 push() 将原始请求/响应记录到这里。
debug router 从这里读取并推送给前端。
"""
from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from typing import Any

_MAX = 200
_store: list[dict[str, Any]] = []


def push(
    source: str,          # "producthunt" | "google_trends" | "serpapi"
    query: str,           # 触发本次调用的查询词
    params: dict,         # 发送给 API 的参数（redact token）
    response: Any,        # 原始响应对象（dict / None / error str）
    elapsed_ms: int,
    error: str | None = None,
) -> None:
    entry: dict[str, Any] = {
        "id": str(uuid.uuid4())[:8],
        "ts": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "query": query,
        "params": params,
        "response": response,
        "elapsed_ms": elapsed_ms,
        "error": error,
        "ok": error is None,
    }
    _store.insert(0, entry)
    if len(_store) > _MAX:
        _store.pop()


def all_entries() -> list[dict[str, Any]]:
    return list(_store)


def clear() -> None:
    _store.clear()
