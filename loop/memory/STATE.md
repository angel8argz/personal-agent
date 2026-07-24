# STATE

## Next task: Step 4 — Tier 2 terminal tool (HANDOFF next-steps)

Allowlisted commands (e.g. `ls`, `git status`, `cat`) run without asking;
anything else shows the literal command and requires confirmation before
executing. `agent/tools/stubs.py` currently raises NotImplementedError
for this tier — read it plus `agent/tools/permissions.py` before starting.
Frontend confirmation UI pattern is still an open question per HANDOFF
(modal vs slide-in vs inline) — flag the choice, don't silently pick one
without noting it. Not started.

## DONE: Step 3 — wire frontend to real SQLite data (local HTTP)

Completed 2026-07-23. Transport decision: local HTTP on 127.0.0.1,
stdlib only on both sides (zero new deps) — Tauri's SQL-plugin
alternative would have needed two new deps, blocked by CLAUDE.md's
dependency law. See IMPLEMENTATION.md for the full decision writeup.

Implemented by sonnet-5: `agent/server.py` (127.0.0.1:8765, read-only
`GET /projects` + `GET /tasks/upcoming`), `Dashboard.tsx` rewired off
`PLACEHOLDER_PROJECTS` onto real fetches with loading/error states,
`agent/scripts/smoke_http.py` added.

All 4 done_when checks pass; fresh-context verifier (fable-5, no prior
context, read-only) verdict PASS, citing file/line evidence, no
out-of-scope changes, no new deps found in requirements.txt/package.json/
Cargo.toml or the lockfile. One non-blocking note from the verifier:
CLAUDE.md's "/goal" logging law wasn't applied here — no standing /goal
was declared for this task (STATE.md's done_when is a task checklist,
not a /goal-mechanism condition; loop/goals/ and goal-ledger.tsv are
still empty). Not fabricating a goals/*.md entry without an established
schema to follow — flagging instead per "never invent a convention."

### done_when (machine-checkable) — all passed
1. `agent/server.py` exists: stdlib `http.server`, binds explicitly to
   `127.0.0.1` (never `0.0.0.0`), fixed port. `GET /projects` and
   `GET /tasks/upcoming?within_days=N` return JSON built from real
   `db.db` reads (no placeholder data).
2. `frontend/src/components/Dashboard.tsx` fetches from that server on
   mount (native `fetch`, no new dependency) instead of
   `PLACEHOLDER_PROJECTS`; shows a loading and an error state.
3. `agent/scripts/smoke_http.py` exits 0: starts the server against a
   temp DB seeded with a known project/task, hits both endpoints, and
   asserts the seeded data round-trips.
4. `loop/guardrails/verify.sh` exits 0.

## DONE: Step 1+2 — agent loop end-to-end + real DB CRUD

Completed 2026-07-19: all 3 done_when checks pass; fresh-context
verifier verdict CONFIRMED (no gamed checks; one minor note: e2e
sentinel assertion accepts either of the two seeded tokens).

Started 2026-07-19. HANDOFF.md next-steps 1 and 2 (combined because
exercising Tier 1 file tools requires ALLOWED_ROOTS, which per the
TODO in file_tools.py must come from the SQLite projects table).

### done_when (machine-checkable)
1. `python3 agent/scripts/smoke_db.py` exits 0 — CRUD round-trip:
   create project (with root_path) → create tasks → list upcoming →
   update status → delete cascades; ALLOWED_ROOTS loads from projects
   table; file tool sandbox rejects paths outside registered roots.
2. `python3 agent/scripts/smoke_e2e.py` exits 0 — against live Ollama +
   gemma4:12b, a scripted orchestrator run is asked to read a seeded
   file in a registered project dir and the returned answer contains
   the seeded sentinel string; activity_log.jsonl gained ≥1 entry.
3. `loop/guardrails/verify.sh` exits 0.

## Environment facts (verified 2026-07-19)
- Machine: Apple M4 Pro, 24 GB unified memory.
- Ollama: installing via brew (was absent).
- Model: gemma4:12b — see IMPLEMENTATION.md deviation #1
  (gemma3:9b does not exist and gemma3 has no native tool support).

## Dependency proposals (per CLAUDE.md law)
- None pending. requests is already declared in agent/requirements.txt.
  Playwright (Tier 3) and pyautogui (Tier 4) will need proposals here
  before those tiers start.
