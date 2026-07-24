"""Thin wrapper around Ollama's local /api/chat endpoint.

Ollama must be running locally (`ollama serve`, or it's already running as a
background service after install) with the target model pulled, e.g.:

    ollama pull gemma4:12b

(gemma3:9b, as originally scaffolded, does not exist and gemma3 has no
native tool support in Ollama — see IMPLEMENTATION.md deviation #1.)

This wrapper deliberately does very little — no retries, no streaming yet.
Get the basic request/response/tool-call shape right first.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

import requests

OLLAMA_HOST = "http://127.0.0.1:11434"
DEFAULT_MODEL = "gemma4:12b"


@dataclass
class ModelClient:
    model: str = DEFAULT_MODEL
    host: str = OLLAMA_HOST

    def chat(self, messages: list[dict], tools: list[dict] | None = None) -> dict:
        """Send a chat request to Ollama and return the raw response message.

        `messages` follows the standard {"role": ..., "content": ...} shape.
        `tools` follows the OpenAI-style function-calling schema, which Ollama
        supports natively for tool-capable models like Gemma 3.

        Returns the assistant message dict, which may contain:
          - "content": final text answer, and/or
          - "tool_calls": [{"function": {"name": ..., "arguments": {...}}}, ...]
        """
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
        }
        if tools:
            payload["tools"] = tools

        resp = requests.post(f"{self.host}/api/chat", json=payload, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        return data["message"]

    def is_reachable(self) -> bool:
        try:
            r = requests.get(f"{self.host}/api/tags", timeout=3)
            return r.status_code == 200
        except requests.RequestException:
            return False
