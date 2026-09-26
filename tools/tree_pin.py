#!/usr/bin/env python3
"""Pin the working tree before a read-only pass and verify afterwards that nothing moved.

  python3 tools/tree_pin.py pin                 # print {"head", "digest", "parts"} as JSON
  python3 tools/tree_pin.py verify '<pin JSON>' # exit 0 unchanged, 1 moved (names what), 2 bad pin
  python3 tools/tree_pin.py --selftest          # stubbed git and filesystem; writes nothing

The digest covers five things:
  - HEAD (`git rev-parse HEAD`);
  - tracked changes: `git diff HEAD --binary` plus the status code of every tracked entry, so
    staged, unstaged, deleted and mode-changed files all count, and a rename counts as a delete
    plus an add (`--no-renames`);
  - untracked files (`git status --untracked-files=all`), each as path, size and mtime;
  - ignored files (`git ls-files --others --ignored --directory`), each as path, size and mtime.
    A wholly ignored directory arrives as one entry and is walked here;
  - git state: every ref (`git for-each-ref`, except the `refs/heads/worktree-*` branches Claude
    Code creates for isolated agents), and the size and mtime of `.git/config` and of each file
    under `.git/hooks/`. Objects, logs and the index are not compared.

Excluded: `.venv/`, `dist/` and `.claude/worktrees/` at the repo root, and any `__pycache__/`.
A populated virtualenv holds tens of thousands of files that change whenever a package or a
bytecode file is written, and agent worktrees come and go during a pass. git reports a wholly
ignored directory as a single entry, so an excluded one costs one comparison, not a walk.

Every git call runs with GIT_OPTIONAL_LOCKS=0, so pinning never refreshes the index and never
takes `.git/index.lock`. Size and mtime, not content, are hashed for untracked and ignored files:
a write that keeps both the size and the nanosecond mtime is not detected. Writes outside the
repository (for example under /tmp) are not covered.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXCLUDED_PREFIXES = (".venv/", "dist/", ".claude/worktrees/")
EXCLUDED_NAMES = frozenset({"__pycache__"})
GIT_ENV = {"GIT_OPTIONAL_LOCKS": "0"}
PART_LABELS = {
    "tracked": "tracked changes (git diff HEAD and tracked status codes)",
    "untracked": "untracked files",
    "ignored": "ignored files (outside .venv/, dist/, __pycache__/, .claude/worktrees/)",
    "git": "git refs, .git/config or .git/hooks",
}
AGENT_WORKTREE_REFS = b"refs/heads/worktree-"


def git_runner(argv, cwd, run=subprocess.run):
    """Run one read-only git command with optional locks off; return stdout bytes."""
    env = dict(os.environ, **GIT_ENV)
    r = run(argv, cwd=str(cwd), capture_output=True, env=env)
    if r.returncode != 0:
        err = r.stderr.decode("utf-8", "replace") if isinstance(r.stderr, bytes) else str(r.stderr)
        raise RuntimeError(f"{' '.join(argv)} failed: {err.strip()}")
    return r.stdout if isinstance(r.stdout, bytes) else r.stdout.encode("utf-8")


def excluded(rel):
    rel = rel.replace(os.sep, "/")
    if any(rel == p.rstrip("/") or rel.startswith(p) for p in EXCLUDED_PREFIXES):
        return True
    return any(part in EXCLUDED_NAMES for part in rel.split("/"))


def status_entries(raw):
    """(XY, path) pairs from `git status --porcelain=v1 -z`. A rename or copy entry is followed by
    its source path as a separate NUL-terminated field; that field is consumed, not parsed."""
    items = raw.split(b"\0")
    i = 0
    while i < len(items):
        e = items[i]
        i += 1
        if len(e) < 4:
            continue
        xy = e[:2].decode("ascii", "replace")
        if "R" in xy or "C" in xy:
            i += 1
        yield xy, e[3:].decode("utf-8", "surrogateescape")


def _stat_record(root, rel, lstat):
    try:
        s = lstat(os.path.join(str(root), rel))
        return f"{rel}\0{s.st_size}\0{s.st_mtime_ns}\n".encode("utf-8", "surrogateescape")
    except OSError:
        return f"{rel}\0gone\n".encode("utf-8", "surrogateescape")


def _walk_files(root, rel_dir, walk):
    base = os.path.join(str(root), rel_dir.rstrip("/"))
    for dirpath, dirnames, filenames in walk(base):
        rel_here = os.path.relpath(dirpath, str(root)).replace(os.sep, "/")
        dirnames[:] = sorted(d for d in dirnames if not excluded(f"{rel_here}/{d}/"))
        for f in sorted(filenames):
            rel = f"{rel_here}/{f}"
            if not excluded(rel):
                yield rel


def _git_state(root, run, lstat, walk):
    """Digest of the refs (agent worktree branches aside), .git/config and .git/hooks/."""
    h = hashlib.sha256()
    refs = run(["git", "for-each-ref", "--format=%(refname)%00%(objectname)"], root)
    for line in sorted(refs.splitlines()):
        if line and not line.startswith(AGENT_WORKTREE_REFS):
            h.update(line + b"\n")
    common = run(["git", "rev-parse", "--git-common-dir"], root).decode("utf-8").strip()
    gdir = common if os.path.isabs(common) else os.path.join(str(root), common)
    h.update(_stat_record(gdir, "config", lstat))
    for dirpath, dirnames, filenames in walk(os.path.join(gdir, "hooks")):
        dirnames.sort()
        for f in sorted(filenames):
            rel = os.path.relpath(os.path.join(dirpath, f), gdir).replace(os.sep, "/")
            h.update(_stat_record(gdir, rel, lstat))
    return h.hexdigest()


def fingerprint(root=ROOT, runner=None, lstat=os.lstat, walk=os.walk):
    """{"head", "digest", "parts"} for the checkout at root. runner(argv, cwd) -> stdout bytes."""
    run = runner or git_runner
    head = run(["git", "rev-parse", "HEAD"], root).decode("utf-8").strip()
    tracked = hashlib.sha256(run(["git", "diff", "HEAD", "--binary", "--no-color", "--no-ext-diff",
                                  "--no-textconv"], root))
    untracked, ignored = hashlib.sha256(), hashlib.sha256()
    status = run(["git", "status", "--porcelain=v1", "-z", "--no-renames",
                  "--untracked-files=all", "--ignored=no"], root)
    for xy, rel in sorted(status_entries(status), key=lambda e: e[1]):
        if excluded(rel):
            continue
        if xy == "??":
            untracked.update(_stat_record(root, rel, lstat))
        else:
            tracked.update(f"{xy} {rel}\0".encode("utf-8", "surrogateescape"))
    listing = run(["git", "ls-files", "-z", "--others", "--ignored", "--exclude-standard",
                   "--directory"], root)
    for entry in sorted(e.decode("utf-8", "surrogateescape") for e in listing.split(b"\0") if e):
        if excluded(entry):
            continue
        if entry.endswith("/"):
            for rel in _walk_files(root, entry, walk):
                ignored.update(_stat_record(root, rel, lstat))
        else:
            ignored.update(_stat_record(root, entry, lstat))
    parts = {"tracked": tracked.hexdigest(), "untracked": untracked.hexdigest(),
             "ignored": ignored.hexdigest(), "git": _git_state(root, run, lstat, walk)}
    digest = hashlib.sha256(json.dumps({"head": head, **parts}, sort_keys=True).encode()).hexdigest()
    return {"head": head, "digest": digest, "parts": parts}


def compare(pin, now):
    """(exit_code, lines). 0 unchanged, 1 moved, 2 the pin is not a tree_pin record."""
    if not isinstance(pin, dict) or not pin.get("head") or not pin.get("digest"):
        return 2, ["tree_pin: the pin must be the JSON object `tree_pin.py pin` printed"]
    if pin["head"] == now["head"] and pin["digest"] == now["digest"]:
        return 0, [f"tree_pin: unchanged at {now['head'][:12]}"]
    lines = []
    if pin["head"] != now["head"]:
        lines.append(f"moved: HEAD {pin['head'][:12]} -> {now['head'][:12]}")
    old_parts = pin.get("parts") or {}
    for key, label in PART_LABELS.items():
        if key in old_parts and old_parts[key] != now["parts"][key]:
            lines.append(f"moved: {label}")
    if not lines:
        lines.append("moved: the working tree (the pin carries no per-part digests)")
    return 1, lines


# --- selftest: a stubbed git and filesystem, so nothing is created or run ---------------------------

class _FakeRepo:
    def __init__(self):
        self.head = "a" * 40
        self.diff = b""
        self.status = []                 # porcelain fields, NUL-joined on read
        self.ignored = []                # ls-files --directory entries
        self.files = {}                  # rel -> (size, mtime_ns)
        self.vanish = set()              # listed by walk, gone at lstat time
        self.calls = []
        self.refs = b"refs/heads/main\0" + b"a" * 40 + b"\n"

    def run(self, argv, cwd):
        self.calls.append(argv)
        if argv[1] == "rev-parse":
            return b".git\n" if "--git-common-dir" in argv else (self.head + "\n").encode()
        if argv[1] == "for-each-ref":
            return self.refs
        if argv[1] == "diff":
            return self.diff
        if argv[1] == "status":
            return b"".join(f.encode() + b"\0" for f in self.status)
        if argv[1] == "ls-files":
            return b"".join(e.encode() + b"\0" for e in self.ignored)
        raise AssertionError(f"unexpected git call {argv}")

    def lstat(self, path):
        rel = os.path.relpath(path, "/r").replace(os.sep, "/")
        if rel in self.vanish or rel not in self.files:
            raise FileNotFoundError(path)
        size, mtime = self.files[rel]
        return type("S", (), {"st_size": size, "st_mtime_ns": mtime})()

    def walk(self, base):
        rel_base = os.path.relpath(base, "/r").replace(os.sep, "/")
        found = [r[len(rel_base) + 1:] for r in list(self.files) + sorted(self.vanish)
                 if r.startswith(rel_base + "/")]
        pending = [""]
        while pending:
            sub = pending.pop(0)
            prefix = sub + "/" if sub else ""
            below = [r[len(prefix):] for r in found if r.startswith(prefix)]
            dirs = sorted({r.split("/", 1)[0] for r in below if "/" in r})
            names = sorted(r for r in below if "/" not in r)
            yield (base + "/" + sub if sub else base), dirs, names
            pending.extend(prefix + d for d in dirs)


def selftest():
    checks = []

    def check(name, cond):
        checks.append((name, bool(cond)))

    def fp(repo):
        return fingerprint(Path("/r"), runner=repo.run, lstat=repo.lstat, walk=repo.walk)

    repo = _FakeRepo()
    repo.status = [" M tools/x.py", "?? notes.md"]
    repo.diff = b"diff --git a/tools/x.py b/tools/x.py\n+edit\n"
    repo.files = {"notes.md": (10, 1), "creator-os-wizard-state.local.json": (5, 1),
                  "shared/cache/index.local.db": (4096, 1), ".git/config": (100, 1),
                  ".git/hooks/pre-commit.sample": (50, 1)}
    repo.ignored = ["creator-os-wizard-state.local.json", "shared/cache/"]
    base = fp(repo)
    check("stable across two calls", fp(repo) == base)
    check("pin carries head and digest", set(base) >= {"head", "digest"} and len(base["digest"]) == 64)

    repo.diff += b"+another edit\n"
    code, lines = compare(base, fp(repo))
    check("a tracked edit is named", code == 1 and lines == [f"moved: {PART_LABELS['tracked']}"])
    repo.diff = b"diff --git a/tools/x.py b/tools/x.py\n+edit\n"

    repo.status.append("?? scratch-notes.md")
    repo.files["scratch-notes.md"] = (3, 7)
    code, lines = compare(base, fp(repo))
    check("a new untracked file is named", code == 1 and lines == [f"moved: {PART_LABELS['untracked']}"])
    repo.status.pop()
    del repo.files["scratch-notes.md"]

    repo.files["shared/cache/index.local.db"] = (8192, 2)
    code, lines = compare(base, fp(repo))
    check("an ignored file inside an ignored directory is named",
          code == 1 and lines == [f"moved: {PART_LABELS['ignored']}"])
    repo.files["shared/cache/index.local.db"] = (4096, 1)
    check("the restored tree matches the pin again", compare(base, fp(repo))[0] == 0)

    repo.ignored += [".venv/", "dist/", "tools/__pycache__/"]
    repo.files.update({".venv/lib/site.py": (1, 1), "dist/pkg.zip": (9, 9),
                       "tools/__pycache__/x.cpython-312.pyc": (2, 2),
                       "shared/cache/__pycache__/c.pyc": (3, 3)})
    repo.status.append("?? .claude/worktrees/agent-1/")
    check("excluded paths do not move the digest", fp(repo)["digest"] == base["digest"])
    repo.files[".venv/lib/site.py"] = (100, 100)
    repo.files["shared/cache/__pycache__/c.pyc"] = (30, 30)
    check("writes inside excluded paths do not move the digest", fp(repo)["digest"] == base["digest"])
    check("the ignored listing uses --directory, so a wholly ignored tree is one entry",
          all("--directory" in c for c in repo.calls if c[1] == "ls-files"))

    repo.head = "b" * 40
    code, lines = compare(base, fp(repo))
    check("a HEAD move is named", code == 1 and lines[0] == "moved: HEAD aaaaaaaaaaaa -> bbbbbbbbbbbb")
    repo.head = "a" * 40

    refs = repo.refs
    repo.refs = refs + b"refs/heads/scratch\0" + b"c" * 40 + b"\n"
    code, lines = compare(base, fp(repo))
    check("a new branch is named", code == 1 and lines == [f"moved: {PART_LABELS['git']}"])
    repo.refs = refs + b"refs/heads/worktree-agent-1\0" + b"d" * 40 + b"\n"
    check("an agent worktree branch does not move the digest", fp(repo)["digest"] == base["digest"])
    repo.refs = refs
    repo.files[".git/config"] = (120, 2)
    check("a changed .git/config is named", compare(base, fp(repo))[1] == [f"moved: {PART_LABELS['git']}"])
    repo.files[".git/config"] = (100, 1)
    repo.files[".git/hooks/pre-commit"] = (9, 9)
    check("a new hook is named", compare(base, fp(repo))[1] == [f"moved: {PART_LABELS['git']}"])
    del repo.files[".git/hooks/pre-commit"]

    entries = list(status_entries(b"R  new/name.py\0old/name.py\0?? z.md\0 M y.py\0"))
    check("a rename entry consumes its source path",
          entries == [("R ", "new/name.py"), ("??", "z.md"), (" M", "y.py")])
    check("status is requested with --no-renames",
          any(c[1] == "status" and "--no-renames" in c for c in repo.calls))

    repo.ignored.append("tmp-out/")
    repo.files["tmp-out/a.txt"] = (1, 1)
    repo.vanish.add("tmp-out/b.txt")
    try:
        moved = compare(base, fp(repo))
        check("a file deleted mid-walk is recorded, not raised", moved[0] == 1)
    except OSError:
        check("a file deleted mid-walk is recorded, not raised", False)

    seen = {}

    def fake_run(argv, cwd, capture_output, env):
        seen.update(env)
        return subprocess.CompletedProcess(argv, 0, b"x\n", b"")
    git_runner(["git", "rev-parse", "HEAD"], "/r", run=fake_run)
    check("git runs with GIT_OPTIONAL_LOCKS=0", seen.get("GIT_OPTIONAL_LOCKS") == "0")
    check("a malformed pin exits 2", compare({"digest": "x"}, base)[0] == 2)
    check("a pin without parts still names a move",
          compare({"head": base["head"], "digest": "0" * 64}, base)[1][0].startswith("moved: the working tree"))

    for name, ok in checks:
        print(("PASS " if ok else "FAIL ") + name)
    failed = sum(1 for _, ok in checks if not ok)
    print(f"tree_pin selftest: {len(checks) - failed}/{len(checks)} passed")
    return 1 if failed else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="Pin the working tree and verify it did not move.")
    ap.add_argument("--selftest", action="store_true", help="stubbed selftest; writes nothing")
    ap.add_argument("--root", default=str(ROOT), help="checkout to pin (default: this repo)")
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("pin", help="print the pin as JSON")
    v = sub.add_parser("verify", help="compare the tree with a pin")
    v.add_argument("pin", help="the JSON that `pin` printed")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    if a.cmd == "pin":
        t0 = time.perf_counter()
        print(json.dumps(fingerprint(Path(a.root)), sort_keys=True))
        print(f"tree_pin: pinned in {time.perf_counter() - t0:.3f}s", file=sys.stderr)
        return 0
    if a.cmd == "verify":
        try:
            pin = json.loads(a.pin)
        except ValueError:
            pin = None
        ok_pin = isinstance(pin, dict) and pin.get("head") and pin.get("digest")
        code, lines = compare(pin, fingerprint(Path(a.root)) if ok_pin else {})
        for line in lines:
            print(line)
        return code
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
