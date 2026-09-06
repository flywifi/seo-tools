#!/usr/bin/env python3
"""CommandPost macro emitter (feature 7) — emit() works; trigger() is a STUB.

CommandPost is a macOS Lua automation layer for Final Cut Pro finishing chores that FCPXML
cannot reach (apply a brand LUT, drop the standard intro, run an export preset). Emitting the
Lua snippet is knowledge and works everywhere; TRIGGERING it needs macOS + CommandPost and is
gated behind video_editing_enabled + commandpost_macros. See shared/videoedit-engine.md.
"""
from __future__ import annotations

import json
import sys


def emit(action: str, params: dict | None = None) -> str:
    """Return a CommandPost/Hammerspoon Lua snippet describing a finishing action.
    Spec-only; safe to produce on any OS. The user reviews and runs it in CommandPost."""
    params = params or {}
    lines = [
        "-- Creator OS finishing macro (review before running in CommandPost)",
        f"-- action: {action}",
    ]
    for k, v in params.items():
        lines.append(f"-- {k}: {v}")
    lines.append("-- CommandPost API entry: cp.apple.finalcutpro / cp.plugins")
    return "\n".join(lines) + "\n"


def trigger(action: str, params: dict | None = None) -> dict:
    """Would drive CommandPost to execute the macro. Gated; STUB until enabled."""
    raise NotImplementedError(
        "CommandPost triggering is not enabled. Turn on video_editing_enabled + commandpost_macros "
        "on macOS with CommandPost installed. Until then, emit() gives you a reviewable Lua snippet."
    )



def selftest() -> int:
    """Offline proof that emit() produces a snippet without driving anything. NEVER calls
    trigger(): that would attempt to drive a real macOS app (P74 WP4)."""
    failures = []

    def ok(name, cond):
        print(f"  [{'ok' if cond else 'FAIL'}] {name}")
        if not cond:
            failures.append(name)

    lua = emit("apply-brand-lut", {"lut": "moody-vintage"})
    ok("emit returns a non-empty snippet", isinstance(lua, str) and lua.strip() != "")
    ok("the snippet carries the action name", "apply-brand-lut" in lua)
    ok("the snippet carries the parameter value", "moody-vintage" in lua)
    ok("an unknown action still yields a string rather than raising",
       isinstance(emit("no-such-action", {}), str))

    print(f"commandpost selftest: {'PASS' if not failures else 'FAIL'} ({len(failures)} failure(s))")
    return 1 if failures else 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        raise SystemExit(selftest())
    print(emit(sys.argv[1] if len(sys.argv) > 1 else "apply-brand-lut", {"lut": "moody-vintage"}))
