"""工具层：抽象基类 + 注册"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseTool(ABC):
    """所有外部数据工具的基类"""

    name: str = ""
    description: str = ""

    @abstractmethod
    def run(self, params: dict[str, Any]) -> dict[str, Any]:
        ...

    def __repr__(self) -> str:
        return f"<Tool: {self.name}>"


_TOOL_REGISTRY: dict[str, BaseTool] = {}


def register_tool(tool: BaseTool) -> None:
    _TOOL_REGISTRY[tool.name] = tool


def get_tool(name: str) -> BaseTool:
    if name not in _TOOL_REGISTRY:
        raise KeyError(f"Tool '{name}' not registered. Available: {list(_TOOL_REGISTRY.keys())}")
    return _TOOL_REGISTRY[name]


def list_tools() -> list[str]:
    return list(_TOOL_REGISTRY.keys())
