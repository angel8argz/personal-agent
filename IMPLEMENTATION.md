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

## Session 2026-07-24 — Step 4a: Tier 2 terminal (backend, CLI gate)

HANDOFF step 4 is "Tier 2 (terminal) with the confirmation UI in the
frontend." Split at the owner's direction: this session is the backend only,
keeping the existing CLI confirmation. The frontend approval surface is 4b,
and the confirmation UI *pattern* (HANDOFF's open question) stays deferred —
`permissions.request_confirmation()` keeps its signature so the swap is
drop-in, per its own TODO.

- `agent/tools/terminal.py` (new) — real `run_command(command, cwd)`. No
  shell ever: `shlex.split` to argv, `subprocess.run` without `shell=True`,
  20s timeout, stdout/stderr captured and capped at 20k chars (same cap as
  `file_tools.read_file`). Non-zero exits are returned as results for the
  model to read, not raised.
- `agent/tools/scoping.py` (new) — the project-root sandbox check, lifted
  out of `file_tools._resolve_within_allowed` so Tier 1 and Tier 2 enforce
  one boundary instead of two copies. `file_tools.py` now imports it.
- Deviation from the stub's instructions: the stub told the next model to
  implement `run_command` in `stubs.py` and to keep the allowlist there.
  Both moved. A tier gets its own module (per ARCHITECTURE.md's "one module
  per tier"), and the allowlist is *policy*, so it lives in
  `permissions.py` — `base.py` is explicit that a tool must not decide its
  own confirmation requirement.
- `agent/tools/permissions.py` — `READ_ONLY_COMMANDS`,
  `READ_ONLY_GIT_SUBCOMMANDS`, `FORBIDDEN_FLAGS`, and
  `is_command_allowlisted()`. `gate()` auto-approves an allowlisted
  `run_command`; everything else falls through to confirmation showing the
  literal command. Three escape hatches closed deliberately:
  1. `git -C <dir> …` would escape the sandboxed cwd, so only a bare
     read-only subcommand in first position qualifies as allowlisted.
  2. `find` is read-only until `-delete`/`-exec`, so those flags disqualify
     it (`FORBIDDEN_FLAGS`).
  3. `cat /etc/passwd` would otherwise inherit `cat`'s auto-approval —
     path-looking args must resolve inside a registered root. Failing any of
     these means "ask the user", never "block".
- Design choice not specified by HANDOFF: `cwd` is a *required* tool
  parameter rather than defaulting to some ambient directory, and it must
  resolve inside a registered root. That makes every command's blast radius
  an explicit, inspectable argument, and is a first concrete piece of the
  "multi-project scoping" open question.
- Shell operators (`|`, `>`, `&&`, …) are rejected as whole argv *tokens*
  rather than substrings, with an error telling the model no shell exists.
  Substring matching would have broken legitimately quoted regexes like
  `grep 'foo$' file`.
- `agent/scripts/smoke_terminal.py` (new) — the done_when check: execution,
  non-zero exit, bad cwd, sandbox escape, piped command, unknown binary,
  output cap, timeout, 7 allowlisted / 10 denied commands, and `gate()`
  itself (auto-approves allowlisted, honours a denial, never prompts twice).
  Needs no Ollama. Wired into `npm test` alongside smoke_db and smoke_http.
- `agent/scripts/smoke_http.py` — was pinned to port 8766, which another
  process on this machine now holds, so the check failed on a bind error
  unrelated to what it tests. Switched to `PORT = 0` (OS picks) and read the
  bound port back off `httpd.server_address`.

Checks: `npm test` (all three smokes), `npm run typecheck`, and
`smoke_e2e.py` against real Ollama all exit 0. Live verification that the
model actually reaches for the tool: asked gemma4:12b to count lines in a
file via the terminal — it called `run_command("wc -l notes.txt")`, the
allowlist auto-approved it with no prompt, and the activity log recorded
`tier: 2, approved: true`. No dependencies added.

## Session 2026-07-25 — CLAUDE.md rewrite + stale model references

CLAUDE.md had been rewritten to describe a native macOS stack (Swift/SwiftUI,
MLX, SwiftData). No Swift exists in this repo — it's Python + Tauri/React —
and that description also silently reversed two HANDOFF.md decisions marked
don't-relitigate. Owner confirmed it was not a pivot, so CLAUDE.md now
describes the stack as built.

Also fixed four references in it that pointed at nothing:
- `src/auth/`, `src/billing/`, `migrations/` — never existed here. Replaced
  with what actually needs protecting: the gate and Tier 2 allowlist in
  `tools/permissions.py`, the sandbox in `tools/scoping.py`, and
  `tauri.conf.json`'s security config.
- `STATE.md` — deleted with `loop/`, so the dependency law was unfollowable.
  Dependency proposals now go to this file.
- The `/goal` → `goals/<name>.md` law — `/goal` was part of the deleted
  `loop/` harness and there is no `.claude/commands/`. Removed rather than
  repaired; flagged to the owner as the one law dropped outright.
- "inside any loop" in the effort cap — no referent post-`loop/`; reworded.

Definition of done is now named commands (`npm test`, `npm run typecheck`,
plus `smoke_e2e.py` for model-facing work, with its exit 2 called out as a
skip rather than a pass). Added three laws that were already true in the
code but unwritten: localhost-only binds, no `shell=True`, and no new
dependency across pip/npm/Cargo. Added a Conventions section (tool-module
shape, smoke-check requirement, BSD-userland gotchas). No commit-size law —
owner's call.

Stale `gemma3:9b` references cleaned up (README was already correct):
- HANDOFF.md's model bullet keeps its original 4B/27B reasoning and gains a
  "Superseded 2026-07-19" note. Erasing the rationale would lose *why*
  mid-size was chosen, which is what stops a future agent dropping to 4B.
- `model_client.py` claimed Ollama supports tool-calling "for tool-capable
  models like Gemma 3" — backwards, and contradicted its own docstring eight
  lines above. Now Gemma 4.
- `stubs.py`'s Tier 4 TODO told the next agent to check Gemma 3 vision
  support for "the same 9B text checkpoint". Both premises gone; rewritten to
  note gemma4:12b already has vision, while keeping the instruction to verify
  on real screenshots since that path is genuinely untested.
