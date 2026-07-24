# Implementation log

Running log of work sessions and deviations from HANDOFF.md / README.md,
per CLAUDE.md ("Deviations: conservative option, log to IMPLEMENTATION.md,
continue").

## Deviation #1 — default model gemma3:9b → gemma4:12b (2026-07-19)

README/HANDOFF specified `gemma3:9b`. Verified facts:
- Ollama's gemma3 library has no 9b tag (270m/1b/4b/12b/27b only; 9B was
  Gemma 2).
- Ollama's gemma3 template has no native tool-calling support
  (ollama/ollama#9941) — the orchestrator passes `tools=` on every chat
  call, so every request would fail.
- `gemma4:12b` (7.6GB, tools + vision + thinking, 256K context) exists
  and is the closest Gemma that satisfies the scaffold's requirements.
  Machine is an M4 Pro / 24GB, so 12B Q4 fits comfortably.

Conservative option chosen: stay on Gemma (owner constraint), bump to the
smallest tools-capable Gemma 4 ≥9B. Bonus: vision support gives Tier 4 a
path without a second model family.

## Session 2026-07-19 — HANDOFF steps 1+2

- Installed Ollama via Homebrew; pulled gemma4:12b.
- DEFAULT_MODEL updated in agent/model_client.py; README updated.
- Real CRUD in agent/db/db.py; file_tools ALLOWED_ROOTS now loads from
  the projects table.
- Added agent/scripts/smoke_db.py and agent/scripts/smoke_e2e.py
  (the done_when checks in loop/memory/STATE.md).
- Root package.json was an empty (0-byte) file, which broke
  loop/guardrails/verify.sh (npm can't parse it). Replaced with a minimal
  valid manifest wiring `typecheck` → frontend tsc and `test` → smoke_db.
- Result: all 3 done_when checks pass; fresh-context verifier (fable-5,
  read-only) verdict CONFIRMED. Gemma 4 12B native tool-calling verified
  directly against /api/chat before the e2e run (~25 tok/s on M4 Pro).

## Decision — Step 3 transport: local HTTP, not Tauri SQL plugin (2026-07-23)

HANDOFF.md left this open. Resolving it now, conservative option per
CLAUDE.md's dependency law:

- Tauri Rust-side SQL plugin needs two new deps (`tauri-plugin-sql` in
  Cargo.toml, `@tauri-apps/plugin-sql` in package.json). CLAUDE.md: "Never
  add a dependency. Propose it in STATE.md and stop."
- Local HTTP needs zero new deps: Python's stdlib `http.server` on the
  agent side, the webview's built-in `fetch()` on the frontend side.
  Also HANDOFF's own stated starting recommendation.
- Scope for this step: read-only (`GET /projects`, `GET /tasks/upcoming`),
  bound explicitly to 127.0.0.1. Writes stay direct-to-SQLite-from-dashboard
  per ARCHITECTURE.md's steady-state data flow — that's a separate step,
  not this one.

## Session 2026-07-23 — Step 3 implementation (HTTP transport wired)

- Added `agent/server.py` (stdlib `ThreadingHTTPServer`, 127.0.0.1:8765,
  `GET /projects` + `GET /tasks/upcoming?within_days=N`, CORS `*`, 404 JSON).
- Rewired `frontend/src/components/Dashboard.tsx` off `PLACEHOLDER_PROJECTS`
  to `fetch()` those two endpoints, with loading/error states.
- Added `agent/scripts/smoke_http.py` (seeds DB, hits both routes via
  `urllib.request` on port 8766); `python3 agent/scripts/smoke_http.py` and
  `bash loop/guardrails/verify.sh` both exit 0. No deps added.

## Session 2026-07-23 — loop pipeline: fixed invalid exit codes (macOS portability)

Root cause: every script in loop/ was written assuming GNU coreutils but
this machine runs macOS's BSD toolchain, and none of the scripts had the
executable bit set.

- chmod +x on loop.sh, guardrails/verify.sh, verify-goals.sh, and all of
  scripts/*.sh — `make trust`/`audit`/`goals`/`tick` invoke these via
  `./path`, which was failing with "Permission denied" (exit 126).
- trust-log.sh: `grep -P` (Perl regex) isn't supported by BSD grep —
  replaced both uses with equivalent `awk -F'\t'` field matches.
- cost-check.sh: `date -d '7 days ago'` is GNU-only — added a BSD
  fallback (`date -v-7d`).
- log-cost.sh / verify-goals.sh: `date -Is` errors on BSD date
  ("invalid argument 's' for -I") — fixed to the full-word form
  `date -Iseconds`, which both GNU and BSD accept.
- verify-goals.sh: three separate bugs —
  1. `sed -i "s/.../.../ "` with no suffix arg is a GNU-ism; BSD sed
     requires `-i` to take an argument. Fixed to `-i.bak ... && rm -f *.bak`,
     which is portable to both.
  2. `date +%s%3N` (millisecond timestamp) isn't a valid BSD date format;
     replaced with `$(date +%s%N) / 1000000`.
  3. `timeout` (and `gtimeout`) aren't installed on this machine at all —
     every goal predicate was silently evaluating as VIOLATED regardless
     of truth, because `timeout: command not found` (exit 127) was
     misread as predicate failure. Added a pure-bash fallback
     (`run_with_timeout`) used only when neither binary is present.
  4. Separately: the script had no `cd "$(dirname "$0")"` (unlike
     loop.sh, which does), so `make goals` — which runs it from the repo
     root — silently matched zero files in `goals/*.md` and reported
     "all standing goals hold" without checking anything. Fixed by
     cd'ing into the script's own directory first, matching loop.sh's
     convention.

All fixes verified in an isolated scratch copy first (seeded pass/fail
trust records, true/false goal predicates, over/under budget) before
confirming against the real (empty) loop/memory state via `make trust`,
`make audit`, `make goals`, `make queue`, and `loop/guardrails/verify.sh`
— all exit 0 now.

Deliberately NOT fixed (bigger decisions, flagging rather than doing
unilaterally): this directory isn't a git repository, and loop.sh's
TRIAGE/EXECUTE/GATE steps assume `git log`/`git worktree`/`git diff`/
`git commit`; the `gh` and `llm` CLIs are also not installed. `make tick`
(the actual orchestrator, not just its helper scripts) will still fail
immediately for these reasons — that needs a decision (git init here?
install gh/llm? run loop.sh from a different, already-git-initialized
location?), not a portability patch.
