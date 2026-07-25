# CLAUDE.md

TARS is a local-first AI agent for managing the owner's projects,
assignments, and deadlines, and for doing work on their machine. It runs
fully on-device — no cloud fallback, and that's a design decision, not a gap
(docs/ARCHITECTURE.md, "Non-goals").

Read HANDOFF.md before changing architecture: it records what was decided
and why, so decisions don't get silently re-litigated. IMPLEMENTATION.md is
the running log of sessions and deviations — append to it, don't rewrite it.

## Stack (as built)

- **Agent core** — Python 3, `agent/`. Use the venv interpreter,
  `agent/.venv/bin/python`, not bare `python3`. Sole dependency: `requests`.
- **Inference** — Ollama on `127.0.0.1:11434`, model `gemma4:12b` (native
  tool-calling + vision, 256K context). Requires `ollama serve` running.
  See IMPLEMENTATION.md "Deviation #1" for why this model and not `gemma3:9b`.
- **Desktop app** — Tauri 2 + React 18 + TypeScript in `frontend/`; the Rust
  shell is `frontend/src-tauri/`.
- **Data** — SQLite through stdlib `sqlite3`, in `agent/db/` (`schema.sql`
  for shape, `db.py` for access).
- **Transport** — frontend → agent over local HTTP on `127.0.0.1:8765`
  (`agent/server.py`, stdlib only, read-only so far).

The owner eventually wants an iOS companion and web sync, so keep the three
layers separable: UI (`frontend/`), agent core (`agent/orchestrator.py` +
`agent/tools/`), inference provider (`agent/model_client.py`). Don't let
them bleed into each other.

## The tier system

Tools are tiered 1–4 by blast radius: 1 file/DB, 2 terminal, 3 browser,
4 full computer-use. Tiers 1–2 are built; 3–4 are stubs in
`agent/tools/stubs.py`. HANDOFF.md has the ordering rationale — it's the
load-bearing safety decision, don't collapse it for convenience.

`agent/tools/permissions.py` is the single choke point every tool call
passes through. A tool declares its tier honestly and never decides its own
confirmation policy.

## NEVER (laws; exceptions require asking first)

- Never weaken the permission boundary: `agent/tools/permissions.py` (the
  gate and the Tier 2 allowlist) or `agent/tools/scoping.py` (the
  project-root sandbox). Widening either takes approval, not judgment.
- Never touch `frontend/src-tauri/tauri.conf.json` security/capabilities, or
  any signing or entitlements config, unattended.
- Never report work as done from your own assessment. Done = the checks
  passed: `npm test` (smoke_db + smoke_terminal + smoke_http) and
  `npm run typecheck`. For anything the model itself invokes, also
  `agent/.venv/bin/python agent/scripts/smoke_e2e.py` — it needs Ollama and
  exits 2 when unreachable, which is a skip, not a pass.
- Never edit, comment out, or delete a test to make a check pass. Fixing the
  code is the only path.
- Never add a dependency — pip, npm, or Cargo. Propose it in
  IMPLEMENTATION.md and stop.
- Never invent a secret, an HTTP endpoint, a tool schema, or a convention.
  Stop and ask.
- Never bind a server to anything but `127.0.0.1` — never `0.0.0.0`.
- Never run a terminal command through a shell. Tier 2 is argv-only via
  `shlex`, never `shell=True`.
- Never echo, transcribe, or explain your internal reasoning in response text.
- Reserve effort `xhigh` for one-shot reviews, not routine work.

## Conventions

- A new tool tier gets its own module in `agent/tools/`, shaped like
  `file_tools.py` / `terminal.py`: plain functions, a `TOOLS` list of `Tool`
  declarations at the bottom, registered in `agent/tools/__init__.py`.
- Every feature lands with a non-interactive `agent/scripts/smoke_*.py`
  check wired into `npm test`. Smoke scripts must not need Ollama; the one
  that does (`smoke_e2e.py`) is run separately.
- This machine is macOS/BSD userland. GNU-only invocations fail here —
  `date -d`, `sed -i` with no suffix argument, `grep -P`, and `timeout`
  (not installed at all). See the 2026-07-23 portability entry in
  IMPLEMENTATION.md.
