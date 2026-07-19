#!/usr/bin/env python3
"""Creator OS eval structural linter (P67-D).

CI previously only `json.loads()`-ed every skills/**/evals/evals.json: a well-formed-JSON file
with empty, malformed, or duplicate-id cases passed silently. This linter checks the STRUCTURE of
every eval case across the whole skills tree (spokes, core, and atoms), offline and with no model
calls. It is intentionally NOT a behavioral runner: executing an eval is an LLM judgment and is an
opt-in, model-calling step (the skill-creator inner loop), never a push gate. This closes the
"green CI, hollow evals" hole without pretending to run the evals.

The eval corpus is heterogeneous by design (list-form and several dict-form shapes; prompt/input,
expect/expected/assertions, id/test_id), so the checks are tolerant: each case must be a dict with
one key from each of three families -- an identifier, an input, and a non-empty expectation -- and
ids must be unique within a file. Invariant 9 in sync_check.py separately enforces the atom
minimum-case-count; this complements it with per-case shape across all skills.

Usage:
  python3 tools/eval_lint.py            # lint the real tree; exit 1 on any problem
  python3 tools/eval_lint.py --list     # list every eval file and its case count
  python3 tools/eval_lint.py --selftest # crafted good/bad fixtures + real-tree-is-clean
"""
import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent

ID_KEYS = ("id", "test_id", "name")
INPUT_KEYS = ("prompt", "input")
# A concrete expectation. `assertions` is intentionally excluded: the scaffold that new_skill.py
# emits carries two boilerplate assertions ("output contains expected keys", "no fabricated data")
# while everything else is empty, so counting assertions would let a hollow scaffold pass.
EXPECT_KEYS = ("expect", "expected", "expected_output_keys")


def _cases(doc):
    """Extract the list of cases from either eval shape, or None if the file has no case list."""
    if isinstance(doc, list):
        return doc
    if isinstance(doc, dict):
        for key in ("evals", "cases"):
            v = doc.get(key)
            if isinstance(v, list):
                return v
    return None


def _nonempty(value):
    """A field counts as present only if it is a non-empty str / list / dict / mapping."""
    if isinstance(value, str):
        return value.strip() != ""
    if isinstance(value, (list, dict)):
        return len(value) > 0
    return value is not None


def lint_doc(doc):
    """Return a list of problem strings for one parsed eval document (empty == clean)."""
    problems = []
    cases = _cases(doc)
    if cases is None:
        return ["no eval case list found (expected a top-level list, or an 'evals'/'cases' array)"]
    if not cases:
        return ["eval case list is empty (need at least one case)"]
    seen_ids = set()
    for i, case in enumerate(cases):
        where = f"case #{i + 1}"
        if not isinstance(case, dict):
            problems.append(f"{where}: not an object")
            continue
        ident = next((case[k] for k in ID_KEYS if k in case), None)
        if not _nonempty(ident):
            problems.append(f"{where}: missing a non-empty id ({'/'.join(ID_KEYS)})")
        else:
            key = str(ident)
            if key in seen_ids:
                problems.append(f"{where}: duplicate id {key!r}")
            seen_ids.add(key)
        # A meaningful case exercises something: it must carry a non-empty input OR a concrete
        # expectation. A no-input refusal test (input {} with real expected_output_keys) is valid;
        # a scaffold with empty input AND empty concrete expectation is not.
        has_input = any(_nonempty(case.get(k)) for k in INPUT_KEYS)
        has_expect = any(_nonempty(case.get(k)) for k in EXPECT_KEYS)
        if not (has_input or has_expect):
            problems.append(f"{where} ({ident}): hollow scaffold: no non-empty input "
                            f"({'/'.join(INPUT_KEYS)}) and no concrete expectation "
                            f"({'/'.join(EXPECT_KEYS)})")
    return problems


def _iter_eval_files():
    return sorted(ROOT.glob("skills/**/evals/evals.json"))


def lint_tree():
    """Lint every eval file under skills/. Returns (problem_count, file_count)."""
    problems = 0
    files = _iter_eval_files()
    for path in files:
        rel = path.relative_to(ROOT)
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"FAIL {rel}: unreadable/invalid JSON: {exc}")
            problems += 1
            continue
        for p in lint_doc(doc):
            print(f"FAIL {rel}: {p}")
            problems += 1
    if not files:
        print("eval_lint: no skills/**/evals/evals.json files found")
    return problems, len(files)


def _selftest():
    checks = []

    def ok(name, cond):
        checks.append((name, bool(cond)))
        print(("ok   " if cond else "FAIL ") + name)

    good_list = [{"id": "a", "prompt": "do x", "expect": ["y happens"]}]
    good_dict = {"skill_name": "s", "evals": [{"test_id": "a", "input": "x", "expected": ["y"]}]}
    good_input_only = [{"id": "a", "input": {"deal_id": "d1"}, "assertions": ["k present"]}]
    good_no_input_refusal = [{"id": "a", "input": {}, "expected_output_keys": ["scene_cuts"]}]
    ok("clean list-form passes", lint_doc(good_list) == [])
    ok("clean dict-form (test_id/input/expected) passes", lint_doc(good_dict) == [])
    ok("input-only case passes", lint_doc(good_input_only) == [])
    ok("no-input refusal case (real expectation) passes", lint_doc(good_no_input_refusal) == [])

    hollow = [{"test_id": "a", "input": {}, "expected_output_keys": [],
               "assertions": ["output contains expected keys", "no fabricated data"]}]
    ok("hollow scaffold caught", any("hollow scaffold" in p for p in lint_doc(hollow)))
    ok("missing id caught", any("non-empty id" in p for p in lint_doc([{"prompt": "x"}])))
    ok("duplicate id caught", any("duplicate" in p for p in lint_doc(
        [{"id": "a", "prompt": "x", "expect": ["y"]}, {"id": "a", "prompt": "z", "expect": ["w"]}])))
    ok("non-object case caught", any("not an object" in p for p in lint_doc(["oops"])))
    ok("empty case list caught", lint_doc([]) != [])
    ok("no case list caught", lint_doc({"skill_name": "s"}) != [])

    problems, files = lint_tree()
    ok(f"real tree lints clean ({files} eval files)", problems == 0 and files > 0)

    failed = [n for n, c in checks if not c]
    print(f"eval_lint selftest: {'PASS' if not failed else 'FAIL (' + ', '.join(failed) + ')'}")
    return 1 if failed else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="Creator OS eval structural linter")
    ap.add_argument("--list", action="store_true", help="list eval files and case counts")
    ap.add_argument("--selftest", action="store_true", help="run the linter's own selftest")
    args = ap.parse_args(argv)
    if args.selftest:
        return _selftest()
    if args.list:
        for path in _iter_eval_files():
            try:
                doc = json.loads(path.read_text(encoding="utf-8"))
                n = len(_cases(doc) or [])
            except (OSError, json.JSONDecodeError):
                n = -1
            print(f"{len(str(n)) and n:>3}  {path.relative_to(ROOT)}")
        return 0
    problems, files = lint_tree()
    if problems:
        print(f"eval_lint: {problems} problem(s) across {files} eval file(s)")
        return 1
    print(f"eval_lint: {files} eval file(s) structurally clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
