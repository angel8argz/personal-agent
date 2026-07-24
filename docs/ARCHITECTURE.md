# Architecture

## Components

**Desktop app (`frontend/`)** — Tauri + React. Owns the project/task/deadline
dashboard UI, and (eventually) the chat interface + tool-confirmation prompts
for talking to the agent.

**Agent core (`agent/`)** — Python process. Owns:
- `model_client.py`: talks to Ollama's local API (`http://127.0.0.1:11434`).
- `orchestrator.py`: the ReAct loop — sends the conversation + available tool
  schemas to the model, parses tool calls out of the response, executes them
  via the tool registry, feeds results back, repeats until the model returns
  a final answer.
- `tools/`: one module per tier, each tool declaring its own JSON schema for
  the model and its own permission requirements.
- `db/`: SQLite schema + access layer for projects, tasks, deadlines.

## Data flow (steady state, once wired up)

1. User adds/edits a project or task directly in the dashboard → straight
   SQLite writes, no model involved.
2. User asks the agent something in chat ("what's due this week?",
   "reorganize my thesis folder") → message goes to the orchestrator.
3. Orchestrator sends the message + tool schemas to Gemma via Ollama.
4. Model responds with either a final answer, or one or more tool calls.
5. Tool calls route through `tools/permissions.py` first — Tier 1 reads pass
   straight through, everything else surfaces a confirmation to the user
   before executing.
6. Tool results feed back into the conversation, loop continues until the
   model produces a final answer.
7. Every executed tool call gets appended to the activity log.

## Why the orchestrator doesn't call tools directly

`tools/permissions.py` is a deliberate choke point between "model decided to
do X" and "X actually happens." Don't let individual tool implementations
call each other or execute without going through this gate — that's the
whole safety mechanism for the tiered risk model described in `HANDOFF.md`.

## Non-goals for this scaffold

- No multi-user support. This is a single-person local tool.
- No cloud fallback or remote model option — deliberately fully local per the
  project brief. If that changes, it's a real design conversation, not a
  quiet addition.
- No attempt yet at streaming responses to the frontend — get the request/
  response loop correct first.
