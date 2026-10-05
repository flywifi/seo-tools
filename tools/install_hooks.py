#!/usr/bin/env python3
"""Install the Creator OS privacy git hooks (P31). Stdlib, idempotent, per-clone.

Git hooks do not travel with the repository, so every clone runs this once (documented in
CLAUDE.md). Two hooks are installed:

- pre-commit: runs `tools/secret_scan.py --staged` — blocks staged secrets (API keys, key
  blocks, credential values, session links, personal emails) AND any staged file whose name
  matches the forbidden classes (.local., .csv/.xlsx/.xls, .ofx/.qfx, .pem/.key, .env*).
  It also refuses a staged audit-record file name (tools/secret_scan.py::audit_record_name);
  a staged deletion passes, since removing the file is the fix.
- commit-msg: scans the commit message itself — blocks claude.ai session links, non-allowlisted
  email addresses, and other secret patterns from ever entering commit metadata (the
  over-sharing vector the hygiene policy exists to stop).
  It also runs tools/commit_claims.py: a subject the invariant-60 claim detector flags needs a
  resolving Claim-Proof: trailer (the check fails open locally when it cannot import).

The CI guard job is the backstop for clones that skipped this (tracked-content scan plus the
commit-message scan bounded by the policy SHA in tools/secret-scan-allowlist.json).

Each hook runs the Python that installed it, by its absolute path (P102): a bare `python3` can be
the Microsoft Store's stand-in on Windows, which exits 9009 without running anything. When that
Python is gone (a rebuilt .venv, an upgraded Python), the hook uses the first of python3, python and
`py -3` that runs, and with none it refuses the commit and says to run this tool again. The hooks
are written with LF line endings on every system.

CLI:
  python3 tools/install_hooks.py             # install/refresh both hooks
  python3 tools/install_hooks.py --selftest  # check the hook text and run the commit-msg hook
"""
from __future__ import annotations

import argparse
import os
import stat
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# The interpreter lines both hooks start with; install() puts the quoted interpreter path in place of
# the placeholder. The hook runs that Python when it exists; otherwise the first of python3, python
# and `py -3` that runs at all (the Microsoft Store's stand-in for python3 exits 9009 and is skipped);
# with none, it refuses the commit.
_PYTHON_LINES = """CREATOR_OS_PY=@PYTHON@
if [ -e "$CREATOR_OS_PY" ]; then
  creator_os_py() { "$CREATOR_OS_PY" "$@"; }
else
  for p in python3 python "py -3"; do $p -c "import sys" >/dev/null 2>&1 && break; p=; done
  if [ -z "$p" ]; then
    echo "Creator OS hook: no working Python (tried $CREATOR_OS_PY, python3, python, py -3); commit refused. Run tools/install_hooks.py again with a working Python." >&2
    exit 1
  fi
  creator_os_py() { $p "$@"; }
fi
"""

PRE_COMMIT = """#!/bin/sh
# Creator OS privacy hook (installed by tools/install_hooks.py). Blocks staged secrets,
# forbidden file types, and .local. files before they can enter a commit.
""" + _PYTHON_LINES + """creator_os_py "$(git rev-parse --show-toplevel)/tools/secret_scan.py" --staged
"""

COMMIT_MSG = """#!/bin/sh
# Creator OS commit-hygiene hook (installed by tools/install_hooks.py). Rejects commit
# messages carrying session links, personal emails, or secret patterns.
""" + _PYTHON_LINES + """creator_os_py - "$1" <<'PY'
import sys
import subprocess
from pathlib import Path
# Inside this heredoc __file__ is "<stdin>", so the tools/ directory comes from git itself.
top = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True,
                     text=True).stdout.strip()
sys.path.insert(0, top + "/tools")
import secret_scan
allowlist = secret_scan._load_allowlist()
problems = []

msg = Path(sys.argv[1]).read_text(encoding="utf-8", errors="replace")
problems += secret_scan.scan_text(msg, "commit-message", allowlist)

# P74: the author-email rule. It is imported from secret_scan rather than restated (ADR 0015),
# so this hook and the CI backstop apply one rule.
author = subprocess.run(["git", "var", "GIT_AUTHOR_IDENT"], capture_output=True,
                        text=True).stdout.strip()
email = author.partition("<")[2].partition(">")[0].strip() if "<" in author else ""
if not email:
    email = subprocess.run(["git", "config", "user.email"], capture_output=True,
                           text=True).stdout.strip()
if email and not secret_scan.EMAIL_ALLOW_RE.search(email) \\
        and not secret_scan._allowed(allowlist, "commit-message", "author_email"):
    problems.append({"pattern_id": "author_email", "match": email})

# Commit-subject claims (tools/commit_claims.py): a subject the invariant-60 detector flags needs a
# resolving Claim-Proof: trailer. This check fails open, with a DID-NOT-RUN line, when it cannot be
# imported; the CI commit hygiene step over the pushed commits fails closed.
try:
    import commit_claims
    problems += commit_claims.message_problems(msg)
except Exception as exc:  # noqa: BLE001
    print(f"commit-msg hook: claim-subject check DID NOT RUN ({type(exc).__name__}: {exc}); "
          "the CI commit hygiene step still checks this subject")

if problems:
    print("commit-msg hook: commit rejected (commit and PR hygiene, CLAUDE.md):")
    for f in problems:
        print(f"  - {f['pattern_id']}: {f['match']}")
    if any(f["pattern_id"].startswith("claim_") for f in problems):
        print("  Name the mechanism the commit changed, or add a Claim-Proof: trailer naming the")
        print("  invariant or selftest pin that proves the claim (tools/commit_claims.py).")
    if any(f["pattern_id"] == "author_email" for f in problems):
        print("  Set the repo-local noreply address:")
        print("    git config user.email '<your-github-noreply-address>'")
    sys.exit(1)
PY
"""


def _sh_quote(text) -> str:
    """text as one single-quoted POSIX shell word."""
    return "'" + str(text).replace("'", "'\"'\"'") + "'"


def render(body, python=None) -> str:
    """A hook's text with the interpreter it runs: python (default sys.executable) as an absolute
    path with forward slashes, which Git for Windows' sh reads, quoted for spaces and quotes."""
    return body.replace("@PYTHON@", _sh_quote(Path(python or sys.executable).resolve().as_posix()))


def install(dry_run=False, hooks_dir=None, python=None):
    hooks_dir = Path(hooks_dir) if hooks_dir is not None else ROOT / ".git" / "hooks"
    if not hooks_dir.exists():
        print("no .git/hooks directory here (not a git checkout?); nothing installed")
        return 1
    results = []
    for name, template in (("pre-commit", PRE_COMMIT), ("commit-msg", COMMIT_MSG)):
        body = render(template, python)
        target = hooks_dir / name
        exists = target.exists()
        current = target.read_text(encoding="utf-8") if exists else None
        if dry_run:
            state = "up to date" if current == body else ("would update" if exists else "would install")
            results.append((name, state))
            continue
        target.write_text(body, encoding="utf-8", newline="\n")
        target.chmod(target.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        results.append((name, "updated" if exists else "installed"))
    for name, state in results:
        print(f"  {name}: {state}")
    return 0


def _shell():
    """A POSIX sh for running a hook: sh on PATH, else Git for Windows' bash (battery.bash_for_syntax)."""
    import shutil
    found = shutil.which("sh")
    if found and os.name != "nt":
        return found
    try:
        sys.path.insert(0, str(ROOT / "tools"))
        import battery
        return battery.bash_for_syntax() or found
    except Exception:  # noqa: BLE001
        return found


def selftest() -> int:
    """The hook text carries the installing interpreter quoted and no bare python3; install() writes
    LF only; the rendered commit-msg hook, run by sh in this checkout, passes a clean message,
    rejects a session link, and refuses with a message when its interpreter is gone."""
    import subprocess
    import tempfile
    checks, skips = [], []

    def ok(name, cond):
        checks.append((name, bool(cond)))

    odd = "/opt/My Py/it's/python3"
    text = render(COMMIT_MSG, odd)
    ok("the hook names its interpreter as one quoted word, spaces and quotes kept",
       "CREATOR_OS_PY='/opt/My Py/it'\"'\"'s/python3'\n" in text and "@PYTHON@" not in text)
    ok("neither hook calls a bare python3",
       not any(line.lstrip().startswith("python3") for body in (PRE_COMMIT, COMMIT_MSG)
               for line in body.splitlines()))
    ok("the commit-msg hook still runs the claim check", "commit_claims.message_problems(msg)" in COMMIT_MSG)
    with tempfile.TemporaryDirectory() as td:
        hooks = Path(td) / "hooks"
        hooks.mkdir()
        rc = install(hooks_dir=hooks, python=sys.executable)
        raw = [(hooks / n).read_bytes() for n in ("pre-commit", "commit-msg")]
        ok("install writes both hooks with LF line endings only",
           rc == 0 and all(b"\r\n" not in r and r.startswith(b"#!/bin/sh\n") for r in raw))
        ok("the installed hooks name this interpreter",
           all(Path(sys.executable).resolve().as_posix().encode() in r for r in raw))
        sh = _shell()
        git_ok = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=str(ROOT),
                                capture_output=True, text=True).returncode == 0
        if not sh or not git_ok:
            skips.append("running the hook: " + ("no POSIX sh found" if not sh else "not a git checkout"))
        else:
            env = dict(os.environ, GIT_AUTHOR_NAME="Hook Selftest",
                       GIT_AUTHOR_EMAIL="hook-selftest@users.noreply.github.com")

            def run_hook(hook, message):
                msg = Path(td) / "msg.txt"
                msg.write_text(message, encoding="utf-8")
                return subprocess.run([sh, str(hook), str(msg)], cwd=str(ROOT), env=env,
                                      capture_output=True, text=True, encoding="utf-8",
                                      errors="replace", timeout=120)
            clean = run_hook(hooks / "commit-msg", "Add a selftest line\n")
            link = run_hook(hooks / "commit-msg", "Add a line\n\nhttps://claude.ai/" + "code/session_" + "01ABC\n")
            gone = Path(td) / "gone-hook"
            gone.write_text(render(COMMIT_MSG, Path(td) / "no-such-python"), encoding="utf-8", newline="\n")
            fallback = run_hook(gone, "Add a line\n\nhttps://claude.ai/" + "code/session_" + "01ABC\n")
            # A PATH whose python3, python and py are stand-ins that exit 9009, as the Store's alias
            # does, plus the tools a hook calls (git, sh) from their real folders.
            stubs = Path(td) / "stubs"
            stubs.mkdir()
            for name in ("python3", "python", "py"):
                stub = stubs / name
                stub.write_text("#!/bin/sh\necho 'Python was not found; run without arguments to install "
                                "from the Microsoft Store'\nexit 9009\n", encoding="utf-8", newline="\n")
                stub.chmod(0o755)
            import shutil as _shutil
            keep = [str(stubs)] + sorted({str(Path(w).parent) for w in (
                _shutil.which("git"), _shutil.which("sh") or sh) if w})
            env_stub = dict(env, PATH=os.pathsep.join(keep))
            msg = Path(td) / "msg.txt"
            nothing = subprocess.run([sh, str(gone), str(msg)], cwd=str(ROOT), env=env_stub,
                                     capture_output=True, text=True, encoding="utf-8",
                                     errors="replace", timeout=120)
            # A pinned interpreter that exists is the one the hook runs, even with only stand-ins on
            # PATH: a wrapper that marks stderr, then runs this Python.
            pinned = Path(td) / "pinned-python"
            pinned.write_text("#!/bin/sh\necho PINNED-INTERPRETER >&2\nexec "
                              + _sh_quote(Path(sys.executable).resolve().as_posix()) + ' "$@"\n',
                              encoding="utf-8", newline="\n")
            pinned.chmod(0o755)
            pinned_hook = Path(td) / "pinned-hook"
            pinned_hook.write_text(render(COMMIT_MSG, pinned), encoding="utf-8", newline="\n")
            msg.write_text("Add a selftest line\n", encoding="utf-8")
            used = subprocess.run([sh, str(pinned_hook), str(msg)], cwd=str(ROOT), env=env_stub,
                                  capture_output=True, text=True, encoding="utf-8",
                                  errors="replace", timeout=120)
            ok("the installed commit-msg hook passes a clean message", clean.returncode == 0)
            ok("a hook runs its pinned interpreter when it exists, before any name on PATH",
               used.returncode == 0 and "PINNED-INTERPRETER" in used.stderr)
            ok("the installed commit-msg hook rejects a session link",
               link.returncode == 1 and "session_link" in link.stdout)
            ok("a hook whose interpreter is gone falls back to a Python on PATH and still checks",
               fallback.returncode == 1 and "session_link" in fallback.stdout)
            ok("with only stand-ins on PATH the hook refuses and says to reinstall",
               nothing.returncode == 1 and "run tools/install_hooks.py again" in nothing.stderr.lower()
               .replace("run tools/install_hooks.py again with", "run tools/install_hooks.py again"))
    failed = [n for n, c in checks if not c]
    for n, c in checks:
        print(("ok   " if c else "FAIL ") + n)
    for s in skips:
        print(f"  [skip] {s}")
    print(f"install_hooks selftest: {len(checks) - len(failed)}/{len(checks)} passed"
          + (f", {len(skips)} skipped" if skips else ""))
    return 1 if failed else 0


def main(argv):
    ap = argparse.ArgumentParser(description="Install the Creator OS privacy git hooks")
    ap.add_argument("--selftest", action="store_true",
                    help="check the hook text and run the commit-msg hook; writes only to a temp folder")
    ap.add_argument("--dry-run", action="store_true", help="report what would be written")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    return install(dry_run=a.dry_run)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
