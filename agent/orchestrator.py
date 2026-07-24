"""The agent's ReAct-style orchestration loop.

Flow: send conversation + tool schemas to the model -> if it returns tool
calls, gate each one through permissions, execute, feed results back -> repeat
until the model returns a plain text answer (or a turn limit is hit).
"""

from __future__ import annotations

import json

from model_client import ModelClient
from tools.base import ToolRegistry
from tools.permissions import ActivityLog, gate

SYSTEM_PROMPT = """\
You are TARS, a local agent that helps manage the user's projects, \
assignments, and deadlines, and can perform tasks on their computer using \
the tools available to you. Be direct and efficient. Only use a tool when \
it's actually needed to answer the request or complete the task.\
"""

MAX_TURNS = 8  # safety valve against infinite tool-call loops


class Orchestrator:
    def __init__(self, model_client: ModelClient, registry: ToolRegistry):
        self.model_client = model_client
        self.registry = registry
        self.activity_log = ActivityLog()

    def run(self, user_message: str, history: list[dict] | None = None) -> str:
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages += history or []
        messages.append({"role": "user", "content": user_message})

        tool_schemas = self.registry.schemas()

        for _ in range(MAX_TURNS):
            reply = self.model_client.chat(messages, tools=tool_schemas)
            messages.append(reply)

            tool_calls = reply.get("tool_calls")
            if not tool_calls:
                return reply.get("content", "")

            for call in tool_calls:
                fn = call["function"]
                name = fn["name"]
                args = fn.get("arguments", {})
                if isinstance(args, str):  # some models return a JSON string
                    args = json.loads(args)

                result_text = self._execute_tool(name, args)
                messages.append(
                    {
                        "role": "tool",
                        "name": name,
                        "content": result_text,
                    }
                )

        return "(TARS hit its turn limit without a final answer — check the activity log)"

    def _execute_tool(self, name: str, args: dict) -> str:
        try:
            tool = self.registry.get(name)
        except KeyError as e:
            return f"Error: {e}"

        approved = gate(tool, args, self.activity_log)
        if not approved:
            return "User denied this action."

        try:
            result = tool.run(**args)
            self.activity_log.record(name, tool.tier, args, approved=True, result=str(result))
            return str(result)
        except Exception as e:  # noqa: BLE001 - surface any tool error back to the model
            error_msg = f"Tool '{name}' raised an error: {e}"
            self.activity_log.record(name, tool.tier, args, approved=True, result=error_msg)
            return error_msg
