"""Tier 2 (terminal), Tier 3 (browser), and Tier 4 (computer-use) tools.

All stubs. Build these in this order (see HANDOFF.md for why), using
tools/file_tools.py as the shape to follow: plain functions + a `Tool`
declaration at the bottom, tier-tagged honestly.

Do not wire these into the orchestrator's default tool list until they have
real implementations — an unimplemented tool the model thinks it can call
is worse than no tool at all.
"""

from __future__ import annotations

from tools.base import Tool

# --- Tier 2: terminal ---------------------------------------------------

# TODO(fable-5):
#   - Maintain an allowlist of read-only-ish commands (ls, git status, cat,
#     grep, ...) that run without confirmation.
#   - Anything not on the allowlist must go through permissions.gate() and
#     show the *exact* command string before running.
#   - Run via subprocess with a timeout, capture stdout/stderr, cap output
#     length the same way file_tools.read_file caps content length.
#   - Never use shell=True with unsanitized input.

def run_command(command: str) -> str:
    raise NotImplementedError("Tier 2: implement allowlist + confirmation + subprocess execution")


# --- Tier 3: browser automation -----------------------------------------

# TODO(fable-5):
#   - Use Playwright with a DEDICATED browser profile/context — not the
#     user's daily browser with saved sessions. See HANDOFF.md: this
#     isolation boundary is deliberate, don't collapse it for convenience.
#   - Start with a small tool set: navigate(url), read_page_text(),
#     click(selector), fill(selector, text). Resist the urge to expose raw
#     Playwright as a single tool — the model should call named, scoped
#     actions so each one can be tiered/confirmed individually if needed.

def browser_navigate(url: str) -> str:
    raise NotImplementedError("Tier 3: implement via a dedicated Playwright browser context")


# --- Tier 4: full computer-use ------------------------------------------

# TODO(fable-5):
#   - Needs a vision-capable model variant (check current Gemma 3 vision
#     support before assuming the same 9B text checkpoint works here).
#   - Loop shape: screenshot -> model interprets + picks an action ->
#     pyautogui (or platform equivalent) executes -> screenshot again.
#   - This is the highest blast-radius tier. Every action should be
#     confirmable, and consider requiring confirmation for EVERY action
#     initially (not just the first one in a sequence), until real-world
#     testing shows that's too disruptive.
#   - Check whether this needs to swap the main Gemma model out of VRAM
#     rather than running both concurrently — see HANDOFF.md hardware note.

def computer_use_step(instruction: str) -> str:
    raise NotImplementedError("Tier 4: implement screenshot -> vision model -> input execution loop")


TOOLS: list[Tool] = []  # intentionally empty until the above are implemented
