"""Base tool interface + registry.

Every tool declares:
  - a JSON schema (for the model to know it exists and how to call it)
  - a risk tier (1-4, see docs/ARCHITECTURE.md)
  - a `run(**kwargs)` method that actually does the work

Tools should NOT decide for themselves whether to ask for confirmation —
that's `permissions.py`'s job. A tool just declares its tier honestly.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class Tool:
    name: str
    description: str
    tier: int  # 1-4, see docs/ARCHITECTURE.md
    parameters_schema: dict  # JSON schema for the "parameters" field
    fn: Callable[..., Any]

    def to_ollama_schema(self) -> dict:
        """Convert to the OpenAI/Ollama-style tool schema."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters_schema,
            },
        }

    def run(self, **kwargs) -> Any:
        return self.fn(**kwargs)


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"Tool '{tool.name}' already registered")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool:
        if name not in self._tools:
            raise KeyError(f"Unknown tool: {name}")
        return self._tools[name]

    def all(self) -> list[Tool]:
        return list(self._tools.values())

    def schemas(self) -> list[dict]:
        return [t.to_ollama_schema() for t in self._tools.values()]
