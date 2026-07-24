# TARS — a local agent OS for project management + task automation

A personal, fully-local agent (named after the robot in *Interstellar*) that:
1. Runs an open-weight Gemma model on-device via Ollama — no cloud calls.
2. Gives you a native desktop dashboard for projects, assignments, and deadlines.
3. Can act as an agent on your computer — files, terminal, browser, and eventually
   full screen control — gated behind a tiered permission system.

This repo is a **scaffold**, not a finished product. It exists to hand off a clear,
opinionated starting point to whoever (or whichever model) builds it out next.
Read `HANDOFF.md` first — it has the context, decisions, and open questions.

## Stack

| Layer | Choice | Why |
|---|---|---|
| Model runtime | [Ollama](https://ollama.com) running Gemma 4 (12B) | Easiest local inference server, native tool calling (Gemma 3 lacked it — see IMPLEMENTATION.md), quantization handled for you |
| Agent core | Custom Python ReAct loop (`agent/`) | Full control, no framework overhead — matters on modest hardware |
| Frontend | Tauri + React + TypeScript (`frontend/`) | Native-feeling app, uses system webview instead of bundling Chromium (much lighter than Electron) |
| Data | SQLite (`agent/db/`) | Zero-config, fast, trivially portable |

## Prerequisites

- [Rust](https://rustup.rs) (for Tauri)
- [Node.js](https://nodejs.org) 18+ and npm
- Python 3.11+
- [Ollama](https://ollama.com) installed, then: `ollama pull gemma4:12b`

## Quick start

```bash
# 1. Agent backend (run this first to sanity-check the model + tools)
cd agent
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python3 main.py

# 2. Frontend (separate terminal)
cd frontend
npm install
npm run tauri dev
```

The agent currently runs as a standalone CLI loop in `agent/main.py` — that's
intentional. Get the model + tool-calling working there first, before wiring it
up to the Tauri app over IPC/HTTP. See `HANDOFF.md` for why.

## Repo layout

```
tars/
├── HANDOFF.md              ← read this first
├── docs/
│   └── ARCHITECTURE.md     ← tier system, data flow, design rationale
├── agent/                  ← Python agent core (model + tools + orchestration)
│   ├── main.py             ← CLI entry point for testing
│   ├── orchestrator.py     ← ReAct loop
│   ├── model_client.py     ← Ollama API wrapper
│   ├── tools/               ← Tier 1-4 tool implementations
│   └── db/                 ← SQLite schema + helpers
└── frontend/                ← Tauri + React desktop app
    ├── src-tauri/           ← Rust shell
    └── src/                 ← React dashboard UI
```
