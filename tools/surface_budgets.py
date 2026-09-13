#!/usr/bin/env python3
"""Surface budget checks (P72). External platforms impose hard caps that our packaged artifacts
must fit inside, and the P72 audit found the shipped ChatGPT custom instructions had never been
size-validated: Box 2 alone (3,863 chars) could not have been pasted under the old 1,500-char
cap, and the combined content exceeded the current 5,000-char cap under its stricter reading.
Each budget below cites its authority. A failing budget means the artifact will not paste or
load on the surface it is packaged for -- that is a build failure, not a style nit.

Caps sourced 2026-08-15:
  - ChatGPT custom instructions: 1,500 chars Free/Go, 5,000 Plus and above; per-field vs
    combined is NOT officially documented, so the full variant is checked against 5,000
    COMBINED (worst reading) and the compact variant against 1,500 combined.
    Authority: help.openai.com/en/articles/8096356 (excerpt confidence; page 403s direct fetch).
  - Codex AGENTS.md: combined project-doc budget `project_doc_max_bytes` defaults to 32 KiB;
    files past the limit are skipped silently.
    Authority: learn.chatgpt.com/docs/agent-configuration/agents-md (direct fetch;
    registry source codex-agents-md-config).
  - ChatGPT Project instructions: no documented cap; 8,000 chars is our conservative target so
    the artifact survives any plausible future limit.
    Authority: help.openai.com/en/articles/10169521 documents no limit (excerpt confidence).

CLI:
  python3 tools/surface_budgets.py             # check; exit 1 on violation
  python3 tools/surface_budgets.py --selftest  # same checks, sweep-discoverable output
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# (path, combined_char_cap) for two-box custom-instruction files.
BOX_FILES = [
    ("implementation/gpt/web/custom-instructions.md", 5000),
    ("implementation/gpt/web/custom-instructions-compact.md", 1500),
]

# (path, byte_cap, authority) for whole-file budgets. Missing files are skipped (they may land
# in a later phase); present files must fit.
FILE_BUDGETS = [
    ("AGENTS.md", 32 * 1024,
     "Codex project_doc_max_bytes default 32 KiB (learn.chatgpt.com/docs/agent-configuration/agents-md)"),
    ("implementation/gpt/project/project-instructions.md", 8000,
     "conservative target; no official cap documented (help/10169521)"),
]

_BOX_SPLIT = re.compile(r"^## Box \d.*$", re.M)


def check(root: Path = ROOT) -> list:
    """Return a list of human-readable violations. Empty == every artifact fits its surface."""
    problems = []
    for rel, cap in BOX_FILES:
        p = root / rel
        if not p.exists():
            problems.append(f"{rel}: missing (referenced by the ChatGPT setup docs)")
            continue
        boxes = _BOX_SPLIT.split(p.read_text(encoding="utf-8"))[1:]
        if len(boxes) != 2:
            problems.append(f"{rel}: expected exactly two '## Box N' sections, found {len(boxes)}")
            continue
        sizes = [len(b.strip()) for b in boxes]
        if sum(sizes) > cap:
            problems.append(f"{rel}: boxes {sizes[0]}+{sizes[1]}={sum(sizes)} chars > {cap} "
                            f"combined cap (help/8096356, worst reading)")
    for rel, cap, why in FILE_BUDGETS:
        p = root / rel
        if not p.exists():
            # P72 D6: a budgeted artifact that vanished must not pass silently.
            problems.append(f"{rel}: missing (budgeted artifact; deleted or moved)")
            continue
        if len(p.read_bytes()) > cap:
            problems.append(f"{rel}: {len(p.read_bytes())} bytes > {cap} ({why})")
    return problems


def _selftest_fixture() -> list:
    """Hermetic negative fixture (P82): prove check() can FAIL. The selftest used to run check()
    against the real repo and assert today's files fit, which passes just as happily when the
    detector is broken as when the artifacts are fine. This plants one over-cap two-box file and
    one over-cap byte-budget file in a temp root and returns what check() says about them."""
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "implementation/gpt/web").mkdir(parents=True)
        (root / "implementation/gpt/project").mkdir(parents=True)
        (root / "implementation/gpt/web/custom-instructions.md").write_text(
            "## Box 1\n" + "a" * 3000 + "\n## Box 2\n" + "b" * 2500, encoding="utf-8")
        (root / "implementation/gpt/web/custom-instructions-compact.md").write_text(
            "## Box 1\nhi\n## Box 2\nyo", encoding="utf-8")
        (root / "implementation/gpt/project/project-instructions.md").write_text(
            "x" * 8001, encoding="utf-8")
        (root / "AGENTS.md").write_text("ok", encoding="utf-8")
        return check(root=root)


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--selftest" in argv:
        fixture = _selftest_fixture()
        box_flagged = any("> 5000" in x for x in fixture)
        byte_flagged = any("8001 bytes > 8000" in x for x in fixture)
        if not (box_flagged and byte_flagged and len(fixture) == 2):
            print(f"  FAIL  fixture: the detector did not flag exactly the two planted "
                  f"violations (got {len(fixture)}: {fixture})")
            print("surface-budgets selftest: FAIL (fixture tier)")
            return 1
        problems = check()
        for x in problems:
            print(f"  FAIL  {x}")
        print(f"surface-budgets selftest: {'PASS' if not problems else 'FAIL'} "
              f"({len(problems)} violation(s); fixture tier proved the detector can fail)")
        return 1 if problems else 0
    problems = check()
    if problems:
        for x in problems:
            print(f"surface-budget: {x}")
        return 1
    print("surface-budgets: all packaged artifacts fit their documented caps")
    return 0


if __name__ == "__main__":
    sys.exit(main())
