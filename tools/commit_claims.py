#!/usr/bin/env python3
"""Commit-subject claim check: a subject names the mechanism a commit changed.

A commit subject is a report. A stage pushed before its verification stage returns says what the
code now does, not the property the stage aims at; the property is reported after that
verification returns, narrowed to what survived (CLAUDE.md, Non-negotiables). This module
runs drift invariant 60's claim detector (tools/sync_check.py::_CLAIM_PATTERN) on the subject. A
flagged subject is accepted when the message carries a `Claim-Proof:` trailer that resolves the way
a claim-proof manifest entry does (`invariant:N`, or `tools/x.py::selftest::<pin label>`); it is
refused otherwise.

Where it runs:
  - the commit-msg hook written by tools/install_hooks.py (`message_problems`). The hook fails
    open with a DID-NOT-RUN line when this module or the drift guard cannot be imported, so a
    broken guard does not block local commits;
  - the CI guard job's commit hygiene step (`--range`), over the commits after
    CLAIM_SUBJECT_BOUNDARY. It fails closed, and it is the check that covers
    `git commit --no-verify`, clones without the hooks, and commits created through the GitHub
    API, none of which run a local hook.

Subjects that restate other subjects are handled rather than flagged:
  - a merge commit (two or more parents, or a commit made while MERGE_HEAD exists) restates the
    commits it merges, each checked on its own, and is skipped; so are `Merge ...` subjects in
    git's generated forms and `Revert "..."`;
  - `fixup! X` and `squash! X` are skipped when X is the subject of an earlier commit (that
    commit's own subject was checked); otherwise X is checked;
  - `amend! X` replaces the target's message on autosquash, so its replacement subject (the first
    line of the body) is checked.

CLI:
  python3 tools/commit_claims.py --message-file PATH   # one message (what the hook checks)
  python3 tools/commit_claims.py --range A..B          # every commit subject in a range (CI)
  python3 tools/commit_claims.py --selftest            # offline; writes nothing

Exit 1 on a refused subject. Stdlib only.
"""
from __future__ import annotations

import argparse
import ast
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

# Commits at or before this one predate the rule and are not re-checked. Its committer time is
# recorded as well, so the skip still holds in a clone that no longer contains the commit (for
# example after the branch is squash-merged).
CLAIM_SUBJECT_BOUNDARY = "9d4148cb9c692e207b38360e6c55291525aa2571"
CLAIM_SUBJECT_BOUNDARY_TIME = 1790260575

TRAILER_RE = re.compile(r"^claim-proof:[ \t]*(\S.*?)[ \t]*$", re.M | re.I)
MERGE_RE = re.compile(r"^Merge (?:branch(?:es)? |remote-tracking branch |pull request #\d+ |"
                      r"commit |tag |[0-9a-f]{7,40} into )")
REVERT_RE = re.compile(r'^Revert ".*"$')
AUTOSQUASH_RE = re.compile(r"^(fixup|squash|amend)! (.*)$")


def _git(args, check=True):
    try:
        out = subprocess.run(["git"] + args, cwd=str(ROOT), capture_output=True, text=True,
                             timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None
    if check and out.returncode != 0:
        return None
    return out.stdout


def _message_lines(msg):
    """The message as git stores it: comment lines dropped, and everything below the scissors
    line of `git commit --verbose` cut."""
    out = []
    for line in msg.splitlines():
        if line.startswith("# ") and ">8" in line and "-----" in line:
            break
        if line.startswith("#"):
            continue
        out.append(line.rstrip())
    while out and not out[0].strip():
        out.pop(0)
    return out


def subject_to_check(msg, known_subjects=None):
    """The subject the rule applies to, or None when git generated it or it restates a checked
    subject. `known_subjects` is the set of earlier subjects (None when git is unavailable, in
    which case a restated fixup!/squash! subject is checked like any other)."""
    lines = _message_lines(msg)
    if not lines:
        return None
    subject = lines[0].strip()
    if MERGE_RE.match(subject) or REVERT_RE.match(subject):
        return None
    m = AUTOSQUASH_RE.match(subject)
    while m:
        kind, rest = m.group(1), m.group(2).strip()
        if kind == "amend":
            body = [ln.strip() for ln in lines[1:] if ln.strip()]
            return body[0] if body else rest
        if known_subjects is not None and rest in known_subjects:
            return None
        subject = rest
        m = AUTOSQUASH_RE.match(subject)
    return subject


def _known_subjects():
    out = _git(["log", "--format=%s", "-n", "5000", "HEAD"])
    return None if out is None else {s.strip() for s in out.splitlines() if s.strip()}


def _merge_in_progress():
    return _git(["rev-parse", "-q", "--verify", "MERGE_HEAD"]) is not None


def _enforced_invariants(sync_check):
    """Invariant numbers labelled on a check_* function that main() registers (the same reading
    check_claim_proof uses for `invariant:N` proofs)."""
    tree = ast.parse(Path(sync_check.__file__).read_text(encoding="utf-8"))
    label_re = re.compile(r"^Invariants?\s+(\d+(?:\s*(?:,|and)\s*\d+)*)")
    main = next((n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main"), None)
    registered = set()
    if main is not None:
        registered = {n.func.id for n in ast.walk(main)
                      if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    out = set()
    for n in tree.body:
        if isinstance(n, ast.FunctionDef) and n.name in registered:
            m = label_re.match((ast.get_docstring(n) or "").strip())
            if m:
                out.update(int(x) for x in re.findall(r"\d+", m.group(1)))
    return out


def message_problems(msg, known_subjects=None, is_merge=None):
    """Problems for one commit message: [] when the subject passes."""
    if is_merge is None:
        is_merge = _merge_in_progress()
    if is_merge:
        return []
    import sync_check
    if known_subjects is None:
        known_subjects = _known_subjects()
    subject = subject_to_check(msg, known_subjects)
    if not subject:
        return []
    hit = sync_check._CLAIM_PATTERN.search(subject)
    if hit is None:
        return []
    proofs = TRAILER_RE.findall("\n".join(_message_lines(msg)))
    if not proofs:
        return [{"pattern_id": "claim_subject",
                 "match": f"{hit.group(0)!r} in {subject!r}: name the mechanism the commit "
                          f"changed, or add a Claim-Proof: trailer that resolves"}]
    enforced = _enforced_invariants(sync_check)
    selftest_mods = None
    if any("::selftest::" in p for p in proofs):
        selftest_mods = sync_check._claim_selftest_modules()
    problems = []
    for proof in proofs:
        ok, detail = sync_check._claim_resolve_proof(proof, enforced, selftest_mods)
        if not ok:
            problems.append({"pattern_id": "claim_proof_unresolved", "match": f"{proof}: {detail}"})
    return problems


def range_problems(rng, boundary=None, boundary_time=None):
    """Problems for every commit in `rng` after the boundary, or None when git cannot list it."""
    boundary = CLAIM_SUBJECT_BOUNDARY if boundary is None else boundary
    boundary_time = CLAIM_SUBJECT_BOUNDARY_TIME if boundary_time is None else boundary_time
    log = _git(["log", "--format=%H%x00%P%x00%ct%x00%B%x01", rng])
    if log is None:
        return None
    prior = _git(["rev-list", boundary]) if boundary else None
    skip = set(prior.split()) if prior else set()
    known = _known_subjects()
    problems = []
    for record in log.split("\x01"):
        if not record.strip():
            continue
        sha, parents, stamp, body = (record.lstrip("\n").split("\x00", 3) + ["", "", ""])[:4]
        sha = sha.strip()
        if sha in skip or (stamp.strip().isdigit() and int(stamp) <= boundary_time):
            continue
        for p in message_problems(body, known, is_merge=len(parents.split()) > 1):
            problems.append({**p, "path": f"commit:{sha[:12]}"})
    return problems


def _report(problems, mode):
    if problems is None:
        if os.environ.get("CI"):
            print(f"commit-claims [{mode}]: git could not list the commits in CI; failing closed")
            return 1
        print(f"commit-claims [{mode}]: DID NOT RUN (git could not list the commits)")
        return 0
    if problems:
        print(f"commit-claims [{mode}]: {len(problems)} subject(s) refused")
        for p in problems:
            where = f"{p['path']}: " if p.get("path") else ""
            print(f"  - {where}{p['pattern_id']}: {p['match']}")
        return 1
    print(f"commit-claims [{mode}]: clean")
    return 0


def selftest():
    failures = []
    ran = [0]

    def ok(cond, label):
        ran[0] += 1
        print(f"  [{'ok' if cond else 'FAIL'}] {label}")
        if not cond:
            failures.append(label)

    known = {"install_dependencies refuses when the .venv is absent",
             "every install lands in the repo .venv"}

    def ids(msg, is_merge=False):
        return [p["pattern_id"] for p in message_problems(msg, known, is_merge=is_merge)]

    ok(ids("P1: no code path installs machine-wide\n") == ["claim_subject"],
       "a subject the claim detector flags is refused without a Claim-Proof trailer")
    ok(ids("P1: every install instruction defaults to user-scoped\n") == ["claim_subject"],
       "a universal-word subject is refused without a Claim-Proof trailer")
    ok(ids("install_dependencies refuses when the .venv is absent\n") == [],
       "a subject naming the mechanism passes")
    ok(ids("P1: every gate runs in CI\n\nClaim-Proof: invariant:60\n") == [],
       "a flagged subject with a resolving invariant trailer passes")
    ok(ids("P1: every gate runs in CI\n\nClaim-Proof: invariant:9999\n")
       == ["claim_proof_unresolved"],
       "a Claim-Proof trailer naming an unenforced invariant is refused")
    ok(ids("P1: every subject is checked\n\n"
           "Claim-Proof: tools/commit_claims.py::selftest::a subject naming the mechanism passes\n")
       == [], "a selftest-pin Claim-Proof trailer resolves through the selftest sweep")
    ok(ids("P1: every branch merges cleanly\n", is_merge=True) == [],
       "a merge commit is skipped whatever its subject says")
    ok(ids("Merge pull request #7 from example/every-branch\n") == []
       and ids("Merge 1a2b3c4d into 5e6f7a8b\n") == []
       and ids('Revert "every install lands in the repo .venv"\n') == [],
       "git-generated merge and revert subjects are skipped")
    ok(ids("Merge every duplicate row into one record\n") == ["claim_subject"],
       "a hand-written subject that starts with Merge is still checked")
    ok(ids("fixup! every install lands in the repo .venv\n") == [],
       "a fixup! restating an earlier commit's subject is skipped")
    ok(ids("fixup! every file is safe\n") == ["claim_subject"],
       "a fixup! whose target subject is unknown is checked")
    ok(ids("amend! install_dependencies refuses when the .venv is absent\n\n"
           "every install is safe\n") == ["claim_subject"],
       "an amend! is checked on its replacement subject")
    ok(ids("# every comment line is dropped\nthe setup step reports its exit code\n") == [],
       "comment lines are not the subject")
    import install_hooks
    ok("commit_claims.message_problems(msg)" in install_hooks.COMMIT_MSG,
       "the commit-msg hook body runs the subject check")
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    ok(any(line.strip() == 'python3 tools/commit_claims.py --range "$RANGE"'
           for line in ci.splitlines()),
       "the CI commit hygiene step runs the subject check over the commit range")

    n = ran[0]
    print(f"commit_claims selftest: {'PASS' if not failures else 'FAIL'} "
          f"({n - len(failures)} of {n} checks)")
    return 0 if not failures else 1


def main(argv):
    ap = argparse.ArgumentParser(description="Commit-subject claim check (invariant 60 detector)")
    ap.add_argument("--message-file", metavar="PATH")
    ap.add_argument("--range", metavar="RANGE")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    if a.message_file:
        msg = Path(a.message_file).read_text(encoding="utf-8", errors="replace")
        return _report(message_problems(msg), "message")
    if a.range:
        return _report(range_problems(a.range), f"range {a.range}")
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
