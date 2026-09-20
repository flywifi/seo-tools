#!/usr/bin/env python3
"""paste_check.py -- machine checks for pasted assistant answers (P90).

The setup wizard's ChatGPT and claude.ai lanes end with three acceptance prompts
(implementation/gpt/project/README.md, "Acceptance prompts"). The user pastes the assistant's
answer back into the wizard, and these three pure functions return a verdict per prompt:

  check_voice(text)           -- prompt 1 (routing + voice): a spoken-prose script with no em
                                 dashes, no opener exclamation, no AI-tell opener, not a bullet
                                 list. Rules: protocols/formatting-metadata.md "Punctuation
                                 (hard rules)" and shared/voice-engine.md "Anti-AI pattern list".
  check_no_fabrication(text)  -- prompt 2 (no-fabrication): the answer must say the stat is not
                                 in its files (null / [unverified] language) and must not state
                                 an invented number for it. Rule: protocols/no-fabrication.md.
  check_degradation(text)     -- prompt 3 (honest degradation): the answer must say the live
                                 capability is unavailable on this surface, name the upgrade
                                 path, and never pretend it fetched anything live.

Contract: each returns (ok: bool, problems: list[str]) and never raises. Problem strings are
user-facing wizard output, so they carry no em dashes and say what to do next. The checks are
deliberately conservative heuristics over free text: a FAIL always states its reason so the
human can overrule it by re-running the prompt; two failures in a row mean the setup did not
take. Verdicts advise; the human decides (human_review_required doctrine).

Usage:
  python3 tools/paste_check.py --selftest   # hermetic; each detector proven to FAIL on a bad
                                            # fixture and PASS on a compliant one; RC 0/1
"""
from __future__ import annotations

import re
import sys

# protocols/formatting-metadata.md "Punctuation (hard rules)": never em dashes in user-facing
# output; ranges are written with "to" (the en dash is the range tell). Same literals as
# tools/sync_check.py invariant 4.
EM_DASH = "—"
EN_DASH = "–"

# shared/voice-engine.md "Anti-AI pattern list (hard rules for published voice)",
# "Opener patterns that scream AI". Matched case-insensitively at the start of the first
# non-blank line.
BANNED_OPENERS = (
    "absolutely",
    "i'm so excited",
    "hey guys",
    "welcome back",
    "today i wanted to talk about",
    "in today's video",
    "great question",
    "that's a wonderful idea",
)

# Language that honestly marks data as unavailable (protocols/no-fabrication.md: null and flag,
# never invent). Any one of these counts as the marker.
_UNAVAILABLE_RE = re.compile(
    r"(?i)\b(not in (my|the|your) files?|do(?:n't| not) have (?:that|this|your|access)"
    r"|no (?:data|stats?|numbers?|access)|\[unverified\]|null"
    r"|can(?:'t|not) (?:see|access|verify|pull|fetch)"
    r"|not available|isn(?:'t|ot) available|unable to)"
)

# A sentence that states a number for the channel stat the prompt asked about.
_STAT_SENTENCE_RE = re.compile(r"(?i)\b(views?|view count|subscribers?|average)\b")
_NUMBER_RE = re.compile(r"\b\d[\d,.]*\s*[kKmM]?\b")

# Prompt-3 pretend-live-fetch tells: presenting fetched-looking results as current.
_PRETEND_FETCH_RE = re.compile(
    r"(?i)\b(here (?:are|is) the (?:current|latest) tags?|i (?:fetched|pulled|retrieved|scanned)"
    r"|the (?:current|latest) tags (?:are|on))\b"
)

# Prompt-3 upgrade-path vocabulary: the honest answer names where the capability lives.
_UPGRADE_RE = re.compile(r"(?i)\b(claude desktop|mcp|connector|plugin)\b")


def _empty(text: str) -> list[str]:
    if not (text or "").strip():
        return ["nothing was pasted; paste the assistant's whole answer, then check again"]
    return []


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"[.!?\n]+", text) if s.strip()]


def check_voice(text: str) -> tuple[bool, list[str]]:
    """Prompt 1: a spoken-prose script in the Creator OS voice."""
    problems = _empty(text)
    if problems:
        return False, problems
    if EM_DASH in text:
        problems.append("the answer contains an em dash; Creator OS voice forbids them in "
                        "scripts and captions. Re-run the prompt in a fresh chat; if it keeps "
                        "happening, re-paste the instructions from the wizard's earlier step")
    if EN_DASH in text:
        problems.append("the answer contains an en dash; ranges are written with the word "
                        "'to' in the Creator OS voice. Re-run the prompt in a fresh chat")
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    first = lines[0] if lines else ""
    first_l = first.lower().lstrip("\"'#*- ")
    if any(first_l.startswith(op) for op in BANNED_OPENERS):
        problems.append("the answer opens with an AI-tell phrase (for example 'Absolutely!' "
                        "or 'Welcome back!'); the voice rules forbid these openers. Re-run the "
                        "prompt; a correct setup rewrites the opener")
    m = re.search(r"[.!?]", first)
    if m and m.group() == "!":
        problems.append("the answer opens on an exclamation; the voice rules forbid opener "
                        "exclamations. Re-run the prompt")
    bullets = sum(1 for ln in lines if ln.startswith(("-", "*", "•")))
    if lines and bullets / len(lines) > 0.30:
        problems.append("the answer is mostly a bullet list; the acceptance test asks for a "
                        "spoken-prose script (bullet lists inside a script section are a "
                        "structural tell). Re-run the prompt asking for spoken prose")
    return (not problems), problems


def check_no_fabrication(text: str) -> tuple[bool, list[str]]:
    """Prompt 2: the stat is not in its files, and no number is invented for it."""
    problems = _empty(text)
    if problems:
        return False, problems
    has_marker = bool(_UNAVAILABLE_RE.search(text))
    invented = []
    for s in _sentences(text):
        if _STAT_SENTENCE_RE.search(s) and _NUMBER_RE.search(s) and not _UNAVAILABLE_RE.search(s):
            invented.append(s)
    if invented:
        problems.append("the answer states a number for your channel stat ('"
                        + invented[0][:90] + "'). The correct behavior is to say the number is "
                        "not in its files and ask for it; an invented stat means the "
                        "no-fabrication rule did not take. Re-check the pasted instructions, "
                        "then re-run the prompt in a fresh chat")
    if not has_marker:
        problems.append("the answer never says the data is unavailable (no 'not in my files', "
                        "'[unverified]', or similar). The correct answer flags the missing stat "
                        "instead of answering around it. Re-run the prompt")
    return (not problems), problems


def check_degradation(text: str) -> tuple[bool, list[str]]:
    """Prompt 3: honestly names the missing live capability and the upgrade path."""
    problems = _empty(text)
    if problems:
        return False, problems
    if _PRETEND_FETCH_RE.search(text) and not _UNAVAILABLE_RE.search(text):
        problems.append("the answer presents results as if it fetched them live; on this "
                        "surface it cannot. Pretending to fetch is the exact failure this test "
                        "exists to catch. Re-check the pasted instructions, then re-run the "
                        "prompt in a fresh chat")
    if not _UNAVAILABLE_RE.search(text):
        problems.append("the answer never says the live capability is unavailable here; the "
                        "correct answer states that plainly. Re-run the prompt")
    if not _UPGRADE_RE.search(text):
        problems.append("the answer does not name the upgrade path (Claude Desktop with the "
                        "MCP server, or a deployed connector); the correct answer points there. "
                        "Re-run the prompt")
    return (not problems), problems


CHECKS = {
    "1": ("routing + voice", check_voice),
    "2": ("no-fabrication", check_no_fabrication),
    "3": ("honest degradation", check_degradation),
}


def _selftest() -> int:
    """Hermetic fail-then-pass fixtures per detector (the detector-can-fail proof)."""
    failures: list[str] = []

    def check(cond: bool, msg: str) -> None:
        if not cond:
            failures.append(msg)

    # Detector 1 must FAIL on each bad fixture...
    bad_voice = ("Absolutely! Let me help " + EM_DASH + " here is your script.\n"
                 "- point one\n- point two\n- point three\n")
    ok, probs = check_voice(bad_voice)
    check(ok is False and len(probs) >= 3,
          "voice check missed an em-dash + AI opener + bullet script")
    # ...and PASS on a compliant one.
    good_voice = ("Start on the empty entryway. Say what changes in the first five seconds, "
                  "then walk the three zones from door to hallway.\nClose on the finished "
                  "hooks and name the total cost, fourteen dollars.")
    ok, probs = check_voice(good_voice)
    check(ok is True and probs == [], f"voice check false-positived on prose: {probs}")

    ok, probs = check_no_fabrication("Your average view count is 12,400 views per video.")
    check(ok is False, "fabrication check accepted an invented average view count")
    ok, probs = check_no_fabrication(
        "That number is not in my files, so I will not guess it. [unverified] Share your "
        "analytics export or the YouTube Studio number and I will use the real figure.")
    check(ok is True and probs == [], f"fabrication check false-positived: {probs}")

    ok, probs = check_degradation(
        "Here are the current tags on their latest video: home decor, thrift flip, diy.")
    check(ok is False, "degradation check accepted a pretend live fetch")
    ok, probs = check_degradation(
        "Live tag extraction is not available in this Project; it requires the Claude Desktop "
        "setup with the MCP server, or the deployed connector. Knowledge-only alternative: "
        "paste the video page text and I will read the visible metadata.")
    check(ok is True and probs == [], f"degradation check false-positived: {probs}")

    # Empty input always fails, never raises.
    for key, (_label, fn) in CHECKS.items():
        ok, probs = fn("")
        check(ok is False and probs, f"check {key} must fail on empty input")
        ok, probs = fn("x" * 5)  # nonsense must not raise
        check(isinstance(ok, bool), f"check {key} raised or returned a non-bool")

    check(len(BANNED_OPENERS) >= 6, "banned-opener corpus is unexpectedly small")

    if failures:
        for f in failures:
            print("FAIL " + f)
        return 1
    print("paste_check selftest OK (3 detectors, each proven to fail on a bad fixture and "
          "pass on a compliant one; empty and nonsense input handled; 0 network)")
    return 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(_selftest())
    print(__doc__)
    sys.exit(0)
