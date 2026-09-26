#!/usr/bin/env python3
"""Commit-subject claim check: a subject names the mechanism a commit changed.

A commit subject is a report. A stage pushed before its verification stage returns says what the
code now does, not the property the stage aims at; the property is reported after that
verification returns, narrowed to what survived (CLAUDE.md, Non-negotiables). This module
runs drift invariant 60's claim detector (tools/sync_check.py::_CLAIM_PATTERN) on the subject. A
flagged subject is accepted when the message carries a `Claim-Proof:` trailer that resolves the way
a claim-proof manifest entry does (`invariant:N`, or `tools/x.py::selftest::<pin label>`); it is
refused otherwise.

The subject is git's subject: the message's first paragraph with its lines joined by spaces (what
`git log --format=%s` prints), not its first line alone. As in git, a line ends at a newline
alone, and it is blank when it holds only spaces, tabs or carriage returns (GIT_SPACE), so a
no-break space, a form feed or a Unicode line separator does not end the paragraph. Commits that
CLAIM_SUBJECT_BOUNDARY reaches predate this reading and are not re-checked.

Where it runs:
  - the commit-msg hook written by tools/install_hooks.py (`message_problems`). The hook fails
    open with a DID-NOT-RUN line when this module or the drift guard cannot be imported, so a
    broken guard does not block local commits;
  - the CI guard job's commit hygiene step (`--range`), over the commits that
    CLAIM_SUBJECT_BOUNDARY does not reach by ancestry (when that commit is not in the clone, the
    step reports that it could not run). It fails closed, and it is the check that covers
    `git commit --no-verify`, clones without the hooks, and commits created through the GitHub
    API, none of which run a local hook.

Subjects that restate other subjects are handled rather than flagged:
  - a merge commit whose subject has a form git or GitHub generates (MERGE_SUBJECT_RE) restates
    the commits it merges, each checked on its own, and is skipped. A merge is recognised by its
    structure: two or more parents in the --range walk, MERGE_HEAD in the hook (git merge writes
    it before it runs the commit-msg hook). A merge subject written by hand, and a `Merge ...`
    subject on a single-parent commit, are checked like any other. A branch, tag or remote name
    inside a generated form is not read;
  - `Revert "X"` and `Reapply "X"` are skipped when X is a known subject, as for fixup! below;
    otherwise the whole subject is checked;
  - `fixup! X` and `squash! X` are skipped when X is a known subject; otherwise X is checked. A
    known subject is one a commit after the boundary carries (the hook or the CI step checked
    it), or one from a commit the boundary reaches that the detector does not flag: a flagged
    subject from before the boundary was not checked, so a subject restating it is checked;
  - `amend! X` replaces the target's message on autosquash, so its replacement subject (the
    paragraph after the amend! subject) is checked.

The commit-msg hook reads its message file the way git's default cleanup stores it, comment lines
dropped. A `#` line that git keeps (`git commit -m`, `--cleanup=verbatim` or `whitespace`) is not
the hook's subject; the --range walk reads the stored message, `#` lines included, and checks it.

The claim detector reads ASCII word patterns. The subject is folded first (NFKD; format characters
and combining marks dropped; NFKC), and a subject that still carries a character outside ASCII
other than punctuation or a space (a Cyrillic or Greek look-alike letter, or a symbol such as
U+212E that reads as a letter) is refused. A promise phrased outside the detector's vocabulary
("without exception", "bulletproof") is not seen.

A Claim-Proof trailer is checked for resolution, not relevance: an enforced invariant or an
executed pin resolves whatever claim the subject makes, and whether it proves that claim is left
to the reader.

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
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

# This commit and its ancestors predate the rule as it now reads and are not re-checked. The skip
# is by ancestry (git rev-list), not by date, so a backdated commit is still checked. A clone that
# does not contain this commit cannot tell which commits predate it; --range then reports that it
# could not run, which fails closed in CI.
CLAIM_SUBJECT_BOUNDARY = "4dfaad859fb3dbeb066233374b5904685cff23d4"

TRAILER_RE = re.compile(r"^claim-proof:[ \t]*(\S.*?)[ \t]*$", re.M | re.I)
# The subject forms git and GitHub generate for a merge commit: git merge and git pull, GitHub's
# merge and update-branch buttons, and the test merge a pull_request CI run checks out. A merge
# commit whose subject has one of these forms is skipped, and the names in it are not read. A ref
# name holds no whitespace, so a quoted name is one word.
MERGE_SUBJECT_RE = re.compile(
    r"^Merge (?:(?:branch(?:es)?|remote-tracking branch(?:es)?|tags?|commits?) '[^'\s]+'"
    r"(?:(?:, | and |; (?:branch|remote-tracking branch|tag|commit) )'[^'\s]+')*"
    r"(?: of \S+)?(?: into \S+)?|pull request #\d+ from \S+|[0-9a-f]{7,40}(?: into \S+)?)$")
# git quotes the reverted commit's first line in a revert subject; a revert of a revert reads
# `Reapply "..."` in newer git and `Revert "Revert "...""` in older git.
REVERT_RE = re.compile(r'^(?:Revert|Reapply) "(.*)"$')
AUTOSQUASH_RE = re.compile(r"^(fixup|squash|amend)! (.*)$")
# The characters git's isspace() accepts: git trims them from the end of a message line, and a
# line holding only these is blank. A no-break space, a form feed and a Unicode line or paragraph
# separator are not among them.
GIT_SPACE = " \t\r"


def _git(args, check=True):
    try:
        out = subprocess.run(["git"] + args, cwd=str(ROOT), capture_output=True, text=True,
                             timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None
    if check and out.returncode != 0:
        return None
    return out.stdout


def _message_lines(msg, stored=False):
    """The message lines the rule reads. A stored message (`stored`: what `git log` prints for a
    commit in the --range walk) is read as it is, `#` lines and scissors lines included. The file
    the commit-msg hook receives is read the way git's default cleanup stores it: comment lines
    dropped, and everything below the scissors line of `git commit --verbose` cut."""
    out = []
    for line in msg.split("\n"):
        if not stored and line.startswith("# ") and ">8" in line and "-----" in line:
            break
        if not stored and line.startswith("#"):
            continue
        out.append(line.rstrip(GIT_SPACE))
    while out and not out[0].strip(GIT_SPACE):
        out.pop(0)
    return out


def _paragraphs(lines):
    """`lines` split at blank lines (lines of GIT_SPACE characters): a list of paragraphs, each a
    list of its lines."""
    out, cur = [], []
    for line in lines:
        if line.strip(GIT_SPACE):
            cur.append(line)
        elif cur:
            out.append(cur)
            cur = []
    if cur:
        out.append(cur)
    return out


def subject_to_check(msg, known_subjects=None, stored=False):
    """The subject the rule applies to, or None when git generated it or it restates a checked
    subject. `known_subjects` is the set of known subjects (_known_subjects; None when git is
    unavailable, in which case a restated subject is checked like any other)."""
    lines = _message_lines(msg, stored)
    if not lines:
        return None
    paragraphs = _paragraphs(lines)
    subject = " ".join(paragraphs[0]).strip()
    m = REVERT_RE.match(subject)
    if m and known_subjects is not None and m.group(1) in known_subjects:
        return None
    m = AUTOSQUASH_RE.match(subject)
    while m:
        kind, rest = m.group(1), m.group(2).strip()
        if kind == "amend":
            return " ".join(paragraphs[1]).strip() if len(paragraphs) > 1 else rest
        if known_subjects is not None and rest in known_subjects:
            return None
        subject = rest
        m = AUTOSQUASH_RE.match(subject)
    return subject


def _known_subjects(boundary=None):
    """Subjects a fixup!, squash!, Revert or Reapply may restate without being checked again, or
    None when git cannot list the history. A commit the boundary commit does not reach was
    checked (by the hook or the CI step), so its subjects count. A commit it reaches was not, so
    its subject counts only when the detector does not flag it; when the boundary commit is not
    in the clone, every commit is read that way. Each commit gives git's subject (`%s`, which
    fixup! and squash! quote) and its first line (which Revert quotes)."""
    import sync_check
    boundary = CLAIM_SUBJECT_BOUNDARY if boundary is None else boundary
    out = _git(["log", "--format=%H%x00%s%x00%B%x01", "-n", "5000", "HEAD"])
    if out is None:
        return None
    reached = set()
    if boundary:
        prior = _git(["rev-list", boundary])
        reached = set(prior.split()) if prior is not None else None
    known = set()
    for record in out.split("\x01"):
        if not record.strip():
            continue
        sha, subject, body = (record.lstrip("\n").split("\x00", 2) + ["", ""])[:3]
        checked = reached is not None and sha.strip() not in reached
        first = next((ln.strip(GIT_SPACE) for ln in body.split("\n") if ln.strip(GIT_SPACE)), "")
        for form in {subject.strip(), first}:
            if form and (checked or not sync_check._CLAIM_PATTERN.search(form)):
                known.add(form)
    return known


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


def _fold(text):
    """`text` as the claim detector reads it: compatibility forms folded (fullwidth letters,
    ligatures, no-break spaces), then format characters (zero-width, bidi, soft hyphen) and
    combining marks dropped."""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if unicodedata.category(c) not in ("Cf", "Mn", "Me"))
    return unicodedata.normalize("NFKC", text)


def _foreign(text):
    """The characters in `text` outside ASCII other than punctuation (P*) and spaces (Zs)."""
    return sorted({c for c in text if ord(c) > 127
                   and not unicodedata.category(c).startswith("P")
                   and unicodedata.category(c) != "Zs"})


def message_problems(msg, known_subjects=None, is_merge=None, stored=False):
    """Problems for one commit message: [] when the subject passes. `stored` reads `msg` as a
    stored commit message (the --range walk) instead of the file the commit-msg hook receives."""
    if is_merge is None:
        is_merge = _merge_in_progress()
    import sync_check
    if known_subjects is None:
        known_subjects = _known_subjects()
    subject = subject_to_check(msg, known_subjects, stored)
    if not subject or (is_merge and MERGE_SUBJECT_RE.match(subject)):
        return []
    folded = _fold(subject)
    hit = sync_check._CLAIM_PATTERN.search(folded)
    if hit is None:
        foreign = _foreign(folded)
        if foreign:
            return [{"pattern_id": "claim_subject_non_ascii",
                     "match": f"characters outside ASCII ({''.join(foreign)!r}) in {subject!r}: "
                              f"the claim detector reads ASCII words, so spell the subject in "
                              f"ASCII (punctuation such as a dash or a quote mark may stay)"}]
        return []
    proofs = TRAILER_RE.findall("\n".join(_message_lines(msg, stored)))
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


def range_problems(rng, boundary=None):
    """Problems for every commit in `rng` that the boundary commit does not reach (ancestry, not
    date), or None when git cannot list the range or resolve the boundary."""
    boundary = CLAIM_SUBJECT_BOUNDARY if boundary is None else boundary
    log = _git(["log", "--format=%H%x00%P%x00%B%x01", rng])
    if log is None:
        return None
    skip = set()
    if boundary:
        prior = _git(["rev-list", boundary])
        if prior is None:
            return None
        skip = set(prior.split())
    known = _known_subjects(boundary)
    problems = []
    for record in log.split("\x01"):
        if not record.strip():
            continue
        sha, parents, body = (record.lstrip("\n").split("\x00", 2) + ["", ""])[:3]
        sha = sha.strip()
        if sha in skip:
            continue
        for p in message_problems(body, known, is_merge=len(parents.split()) > 1,
                                   stored=True):
            problems.append({**p, "path": f"commit:{sha[:12]}"})
    return problems


def _report(problems, mode):
    if problems is None:
        if os.environ.get("CI"):
            print(f"commit-claims [{mode}]: git could not list the commits or resolve "
                  f"CLAIM_SUBJECT_BOUNDARY in CI; failing closed")
            return 1
        print(f"commit-claims [{mode}]: DID NOT RUN (git could not list the commits or "
              f"resolve CLAIM_SUBJECT_BOUNDARY)")
        return 0
    if problems:
        print(f"commit-claims [{mode}]: {len(problems)} subject(s) refused")
        for p in problems:
            where = f"{p['path']}: " if p.get("path") else ""
            print(f"  - {where}{p['pattern_id']}: {p['match']}")
        return 1
    print(f"commit-claims [{mode}]: clean")
    return 0


def _scripted_git(commits, reached, boundary=None):
    """A stand-in for _git that answers from a scripted history, for the selftest. `commits` holds
    (sha, parents, message) or (sha, parents, message, committer_time) tuples, newest first;
    `reached` is the set of shas the boundary commit reaches, or None when that commit is not in
    the clone. It answers `git rev-list <boundary>` for `boundary` (CLAIM_SUBJECT_BOUNDARY when
    None) and for no other commit, and gives `%s` as git does: the first paragraph, its lines
    joined by spaces. Any other git query (MERGE_HEAD, say) answers as absent."""
    boundary = CLAIM_SUBJECT_BOUNDARY if boundary is None else boundary

    def fake(args, check=True):
        if args[0] == "rev-list":
            if reached is None or list(args) != ["rev-list", boundary]:
                return None
            return "".join(f"{s}\n" for s in sorted(reached))
        if args[0] != "log":
            return None
        fmt = next(a for a in args if a.startswith("--format=")).split("=", 1)[1]
        out = []
        for sha, parents, msg, *stamp in commits:
            head = []
            for ln in msg.lstrip("\n").split("\n"):
                if not ln.strip(GIT_SPACE):
                    break
                head.append(ln.rstrip(GIT_SPACE))
            fields = {"H": sha, "P": parents, "ct": str(stamp[0] if stamp else 4102444800),
                      "s": " ".join(head), "B": msg, "x00": "\x00", "x01": "\x01"}
            out.append(re.sub(r"%(x00|x01|ct|H|P|s|B)", lambda m: fields[m.group(1)], fmt))
        return "\n".join(out) + "\n"
    return fake


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

    def on_history(commits, reached, call, boundary=None):
        """Run `call` with _git answering from a scripted history instead of the repository."""
        global _git
        saved, _git = _git, _scripted_git(commits, reached, boundary)
        try:
            return call()
        finally:
            _git = saved

    def range_ids(commits, reached=frozenset()):
        got = on_history(commits, reached, lambda: range_problems("x..y", boundary="b" * 40),
                         boundary="b" * 40)
        return None if got is None else [(p["path"], p["pattern_id"]) for p in got]

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
    ok(ids("Merge branch 'topic'\n", is_merge=True) == []
       and ids("Merge pull request #7 from example/every-branch\n\nP1: every guard holds\n",
               is_merge=True) == []
       and ids("Merge 1a2b3c4d into 5e6f7a8b\n", is_merge=True) == []
       and ids("Merge branch 'main' of github.com:example/repo into topic\n", is_merge=True) == []
       and ids("Merge branches 'a', 'b' and 'c'\n", is_merge=True) == [],
       "a merge commit with a subject git or GitHub generates is skipped")
    ok(ids("P1: every branch merges cleanly\n", is_merge=True) == ["claim_subject"]
       and ids("Merge branch 'x': every guard always holds\n", is_merge=True) == ["claim_subject"]
       and ids("Merge branch 'every guard always holds'\n", is_merge=True) == ["claim_subject"],
       "a merge commit whose subject is written by hand is checked")
    ok(ids('Revert "every install lands in the repo .venv"\n') == []
       and ids('Reapply "every install lands in the repo .venv"\n') == [],
       "a Revert or Reapply quoting a known subject is skipped")
    ok(ids('Revert "every guard now always holds, nothing leaks"\n') == ["claim_subject"],
       "a Revert quoting a subject that is not a known subject is checked")
    ok(ids('Revert "Every install lands in the repo .venv"\n') == ["claim_subject"]
       and subject_to_check('Revert "every install lands in the repo .venv"\n', None) is not None,
       "a Revert is skipped on an exact known subject, and is checked when none are known")
    ok(ids("Merge branch 'x': every guard always holds\n") == ["claim_subject"]
       and ids("Merge pull request #1 every invariant always holds\n") == ["claim_subject"]
       and ids("Merge 1a2b3c4 into everything-always-holds\n") == ["claim_subject"],
       "a Merge subject on a commit that is not a merge is checked")
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
    backdated = [("1" * 40, "a" * 40, "P1: every guard always holds\n", 1000000000)]
    ok(range_ids(backdated) == [("commit:111111111111", "claim_subject")],
       "a commit the boundary does not reach is checked whatever its committer date says")
    ok(range_ids(backdated, reached={"0" * 40, "1" * 40, "b" * 40}) == [],
       "a commit the boundary commit reaches is skipped")
    ok(range_ids(backdated, reached=None) is None,
       "--range reports it could not run when the boundary commit is not in the clone")
    saved_ci = os.environ.get("CI")
    os.environ["CI"] = "true"
    try:
        rc = on_history(backdated, None, lambda: main(["--range", "x..y"]))
    finally:
        if saved_ci is None:
            os.environ.pop("CI", None)
        else:
            os.environ["CI"] = saved_ci
    ok(rc == 1, "the --range CLI fails closed in CI when the boundary commit is not in the clone")
    merges = [("3" * 40, "a" * 40, "Merge branch 'x': every guard always holds\n"),
              ("4" * 40, "a" * 40 + " " + "c" * 40, "Merge branch 'every-fix'\n"),
              ("8" * 40, "a" * 40 + " " + "c" * 40, "P96: every guard always holds\n")]
    ok(range_ids(merges) == [("commit:333333333333", "claim_subject"),
                             ("commit:888888888888", "claim_subject")],
       "the --range walk skips a two-parent commit with a generated merge subject, not the others")
    ok([p["pattern_id"] for p in on_history([], set(), lambda: message_problems(
        "Merge branch 'x': every guard always holds\n", known))] == ["claim_subject"],
       "the hook checks a Merge subject when no merge is in progress")
    ok(ids("P96: tweak the guard\nso every guard always holds\n\nbody\n") == ["claim_subject"],
       "a claim on a later line of the subject paragraph is checked")
    ok(ids("fixup! every install lands\nin the repo .venv\n") == [],
       "a fixup! is matched on its whole subject paragraph, as git log %s prints it")
    ok(ids("amend! install_dependencies refuses when the .venv is absent\n\n"
           "the setup step reports its exit code\nand every install is safe\n") == ["claim_subject"],
       "an amend! is checked on its whole replacement paragraph")
    ok(ids("amend! install_dependencies refuses when the .venv is absent\n\n"
           "the setup step\nevery install is safe\n") == ["claim_subject"],
       "an amend! replacement paragraph is joined with spaces, as git joins a subject")
    ok(ids("P96: tweak the guard\n \nevery guard always holds\n") == ["claim_subject"]
       and ids("P96: tweak the guard  every guard always holds\n") == ["claim_subject"]
       and ids("P96: tweak the guard\r\revery guard always holds\n") == ["claim_subject"]
       and ids("P96: tweak the guard\n\x0c\nevery guard always holds\n") == ["claim_subject"],
       "the subject paragraph ends at a line of spaces, tabs or carriage returns, as in git")
    ok(ids("P96: tweak the guard\r\n\r\nevery guard always holds\r\n") == [],
       "a blank line written with a carriage return ends the subject paragraph")
    ok(range_ids([("5" * 40, "a" * 40, "#P96: every guard always holds\n")])
       == [("commit:555555555555", "claim_subject")],
       "the --range walk checks a stored subject that starts with #")
    ok(range_ids([("9" * 40, "a" * 40, "# every guard always holds ----- >8 -----\n")])
       == [("commit:999999999999", "claim_subject")],
       "the --range walk does not cut a stored message at a scissors line")
    ok([p["pattern_id"] for p in message_problems(
        "# every guard always holds\nP96: tweak\n", known, is_merge=False, stored=True)]
       == ["claim_subject"], "a stored message keeps its # lines")
    history = [("8" * 40, "7" * 40, "P98: each pin names\nits own file\n"),
               ("7" * 40, "6" * 40, "P97: each guard reads its own file\n"),
               ("6" * 40, "a" * 40, "P95-2: every pin counts\nonce it can fail.\n")]

    def restated(msg, reached):
        return [p["pattern_id"] for p in on_history(
            history, reached, lambda: message_problems(msg, is_merge=False))]
    ok(restated("squash! P95-2: every pin counts once it can fail.\n", {"6" * 40})
       == ["claim_subject"]
       and restated("fixup! P95-2: every pin counts once it can fail.\n", {"6" * 40})
       == ["claim_subject"],
       "a fixup! or squash! restating a flagged subject from before the boundary is checked")
    ok(restated("fixup! P97: each guard reads its own file\n", {"6" * 40}) == [],
       "a fixup! restating a subject after the boundary is skipped")
    ok(restated('Revert "P98: each pin names"\n', {"6" * 40}) == [],
       "a Revert quoting the first line of a checked subject is skipped")
    ok(restated("fixup! P97: each guard reads its own file\n", None) == ["claim_subject"],
       "when the boundary commit is not in the clone a restated flagged subject is checked")
    ok(ids("P96: еvery guard аlways holds\n") == ["claim_subject_non_ascii"]
       and ids("P96: Еvery guard holds\n") == ["claim_subject_non_ascii"]
       and ids("P96: nøthing leaks\n") == ["claim_subject_non_ascii"],
       "a subject spelled with non-ASCII look-alike letters is refused")
    ok(ids("P96: ℮very guard holds\n") == ["claim_subject_non_ascii"]
       and ids("P96: ∊very guard holds\n") == ["claim_subject_non_ascii"],
       "a subject spelled with a symbol that reads as a letter is refused")
    ok(_foreign("a b c d—e") == [" ", " "],
       "a line or paragraph separator counts as outside ASCII; a dash and a no-break space do not")
    ok(ids("P96: ev​ery guard alw​ays holds\n") == ["claim_subject"]
       and ids("P96: ｅｖｅｒｙ guard holds\n") == ["claim_subject"]
       and ids("P96: évery guard holds\n") == ["claim_subject"]
       and ids("P96: évery guard holds\n") == ["claim_subject"]
       and ids("P96: ev̶ery guard holds\n") == ["claim_subject"],
       "zero-width, fullwidth, accented and combining-mark spellings are folded before detection")
    ok(ids("P96: the loader — tidied for the café case, “quoted”\n") == [],
       "punctuation and accented letters outside the vocabulary pass")
    ok(ids("P96: guards hold without exception\n") == [],
       "a promise phrased outside the detector vocabulary is not seen")
    ok(ids("P1: every guard always holds\n\nClaim-Proof: invariant:6\n") == [],
       "a resolving Claim-Proof trailer passes whatever claim the subject makes")
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
