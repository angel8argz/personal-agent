# Handoff notes

Written by Claude Sonnet 5, scaffolding this project after a planning conversation
with the project owner. Handing off to Fable 5 (or whoever's next) to build out.
This file is the "what we decided and why" — read it before changing architecture,
so decisions don't get silently re-litigated.

## Project owner's constraints (don't relitigate without asking)

- **Hardware:** modest discrete GPU (6-12GB VRAM) or Apple Silicon (16-24GB unified
  memory). Not a workstation. Model choice and concurrency assumptions should
  respect this — don't assume you can run a 27B model and a vision loop
  simultaneously without checking.
- **Wants all four capability tiers eventually:** safe file/DB ops, terminal
  commands, browser automation, and full computer-use (screen vision + input
  control). Full computer-use was explicitly requested, not just implied — but
  it's also explicitly the last thing to build (see tier order below).
- **Wants a native-feeling desktop app**, not a browser tab. That's why Tauri
  over Electron — Electron's bundled Chromium plus a local LLM plus a browser
  automation tool is a lot of memory pressure on a 6-12GB-class machine.

## Why these specific choices

- **Ollama, not raw llama.cpp / vLLM:** simplest path to a local OpenAI-ish API,
  handles GGUF quantization, has native tool-calling support so we're not hand-
  rolling a function-calling prompt format.
- **A mid-size Gemma as the default, not 4B or 27B:** 4B is fast but noticeably
  weaker at multi-step tool use; 27B likely won't fit comfortably in 6-12GB VRAM.
  The middle of the range is the balance point. This is a starting point, not a
  hard rule — if early testing shows it's too slow or too weak, that's a
  legitimate reason to revisit.
  **Superseded 2026-07-19:** this originally specified `gemma3:9b`. That tag
  doesn't exist (Ollama's gemma3 ships 270m/1b/4b/12b/27b — 9B was Gemma 2), and
  gemma3 has no native tool-calling in Ollama, so every request would have failed.
  The default is now `gemma4:12b` — same reasoning, nearest tag that satisfies it,
  and its vision support gives Tier 4 a path without a second model family. See
  IMPLEMENTATION.md "Deviation #1".
- **Custom orchestrator instead of LangChain/LangGraph:** those frameworks add
  real overhead (both cognitive and runtime) that isn't worth it for a personal
  single-agent loop. If the tool-calling logic grows genuinely complex (parallel
  tool calls, subagents), reconsider — but don't reach for a framework by default.
- **SQLite instead of Postgres/etc:** this is a single-user local app. No reason
  for a client-server DB.

## The tier system (this is the load-bearing safety decision)

Four tiers, in the order they should be *built* (not just used):

1. **Tier 1 — File & project ops.** Reads/writes scoped to explicit project
   directories the user has registered, plus the SQLite DB. Reads run without
   confirmation. Writes/deletes should show a diff or summary and require
   confirmation until the user has explicitly trusted a given directory.
2. **Tier 2 — Terminal commands.** An allowlist (e.g. `ls`, `git status`, `cat`)
   runs without asking. Anything not on the allowlist shows the literal command
   about to run and requires explicit user confirmation before executing.
3. **Tier 3 — Browser automation.** Playwright, driving a *dedicated* browser
   profile/context — not the user's daily-driver browser with saved sessions
   and passwords. This is a deliberate isolation boundary, don't casually
   collapse it for convenience.
4. **Tier 4 — Full computer-use.** Screenshot in, vision-capable model reasons
   about the screen, pyautogui (or platform equivalent) executes clicks/typing.
   This is the least mature part of the plan on purpose — build it last, and
   revisit whether it needs to swap the main Gemma model out of memory rather
   than running both concurrently on constrained hardware.

Every tier above Tier 1 defaults to "ask before acting" until the user has had
a chance to build trust and explicitly loosen a permission. Don't flip that
default to save clicks — the whole point of the tier system is that the blast
radius of a mistake grows with each tier, and the user opted into all four
knowingly. Log every executed action (`agent/tools/permissions.py` has an
`ActivityLog` stub) — this is the safety net, not an afterthought.

## Current state of this scaffold

Nothing here is production logic. Specifically:

- `agent/model_client.py` — real Ollama API call, but no retry/streaming/error
  handling beyond the basics.
- `agent/orchestrator.py` — a real ReAct loop shape, but only wired to a couple
  of Tier 1 example tools. Tier 2-4 tools are stubs that raise
  `NotImplementedError` with a comment on what they should do.
- `agent/db/schema.sql` — a real, usable schema for projects/tasks/deadlines.
  Probably fine to keep as-is initially.
- `frontend/` — a Tauri app that launches and shows a static three-column
  dashboard with placeholder data. No IPC wiring to the agent yet, no real
  data loading from SQLite yet.

## Immediate next steps, roughly in order

1. Get `agent/main.py` running end-to-end against a real Ollama + Gemma
   install, exercising the Tier 1 file tools, before touching the frontend.
2. Wire the SQLite schema into real CRUD in `agent/db/db.py` (currently just
   `init_db()`).
3. Replace the frontend's placeholder data with real reads from SQLite
   (either via Tauri's Rust-side SQL plugin, or by having the frontend call
   the Python agent's HTTP layer — that decision hasn't been made yet, see
   open question below).
4. Build Tier 2 (terminal) with the confirmation UI in the frontend.
5. Tier 3, then Tier 4 — see the tier ordering rationale above for why not
   sooner.

## Open questions left unresolved — use judgment, but flag the choice

- **Frontend ↔ agent transport:** not decided whether the Tauri frontend talks
  to the Python agent over local HTTP (simplest, adds a running process) or
  whether the agent logic should eventually get ported into Rust/embedded.
  Starting recommendation: local HTTP on `127.0.0.1` only, bound explicitly to
  localhost, not `0.0.0.0`.
- **Confirmation UI pattern:** whether tool confirmations show as a modal, a
  slide-in panel, or an inline chat-style approval — not decided. Should feel
  fast to approve (single keypress ideally) since it'll happen often.
- **Multi-project scoping:** the schema supports multiple projects, but tool
  sandboxing (which directories Tier 1 can touch) per-project isn't designed
  yet.
