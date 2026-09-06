"""tools/atomic_io.py -- the ONE atomic writer for Creator OS (P81).

Four writers existed before this module with four different guarantees (registry_io: temp+replace
with cleanup, no mode; handoff/queue: temp+replace, no cleanup, fixed temp name; mcp_server: temp+
replace, no cleanup, no mode; wizard: bare write_text on the same secrets-bearing file the MCP server
writes atomically). This module gives every writer the same contract:

  * atomic_write_text(path, text): serialize fully, write a PID-suffixed temp file in the SAME
    directory, copy the destination's existing mode onto it, os.replace onto the destination. A reader
    sees the old bytes or the new bytes, never a mix; a crash leaves the old file intact; the temp is
    never left behind; an operator's 0600 on a token-bearing file survives.
  * locked(path): an fcntl.flock exclusive lock on <path>.lock, held across a read-modify-write, so two
    PROCESSES (the wizard and the MCP server both write creator-os-config.local.json) cannot lose each
    other's update. On platforms without fcntl the lock is a no-op and says so once on stderr.

Stdlib only. Invariant 42 (writer census) treats this module as the sanctioned write implementation;
a write_text() on a .local.json / credential / register path anywhere else fails the drift guard.
"""
from __future__ import annotations

import contextlib
import os
import stat
import sys
from pathlib import Path

try:
    import fcntl  # POSIX only
except ImportError:  # pragma: no cover - Windows
    fcntl = None
    print("[atomic_io] WARNING: fcntl unavailable; cross-process locking is a no-op on this platform.",
          file=sys.stderr)


def atomic_write_text(path, text: str, *, encoding: str = "utf-8") -> None:
    """Write `text` to `path` atomically, preserving the destination's mode if it exists."""
    path = Path(path)
    mode = None
    try:
        mode = stat.S_IMODE(path.stat().st_mode)
    except FileNotFoundError:
        pass
    tmp = path.with_name(f"{path.name}.tmp{os.getpid()}")
    try:
        tmp.write_text(text, encoding=encoding)
        if mode is not None:
            os.chmod(tmp, mode)
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()


@contextlib.contextmanager
def locked(path):
    """Exclusive cross-process lock on <path>.lock for the duration of the block."""
    lock = Path(path).with_name(Path(path).name + ".lock")
    lock.parent.mkdir(parents=True, exist_ok=True)
    with open(lock, "a+") as fh:
        if fcntl is not None:
            fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            yield
        finally:
            if fcntl is not None:
                fcntl.flock(fh, fcntl.LOCK_UN)


def selftest() -> int:
    import json, subprocess, tempfile, textwrap
    failures = []

    def ok(name, cond):
        print(f"  [{'ok' if cond else 'FAIL'}] {name}")
        if not cond:
            failures.append(name)

    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "cfg.json"
        p.write_text("{}", encoding="utf-8")
        os.chmod(p, 0o600)
        atomic_write_text(p, '{"a": 1}\n')
        ok("existing 0600 mode preserved across the replace", stat.S_IMODE(p.stat().st_mode) == 0o600)
        ok("bytes landed", p.read_text(encoding="utf-8") == '{"a": 1}\n')
        q = Path(td) / "new.json"
        atomic_write_text(q, "x")
        ok("a new file is created (umask default mode)", q.exists())
        d = Path(td) / "dir"
        d.mkdir()
        try:
            atomic_write_text(d, "x")
            ok("replacing onto a directory raises", False)
        except IsADirectoryError:
            ok("replacing onto a directory raises", True)
        ok("no temp file survives a failed replace", not any(x.name.startswith("dir.tmp") for x in Path(td).iterdir()))
        # cross-process: two children do 50 locked read-modify-writes each; no lost update
        child = textwrap.dedent(f"""
            import json, sys, time
            sys.path.insert(0, {str(Path(__file__).resolve().parent)!r})
            from atomic_io import atomic_write_text, locked
            from pathlib import Path
            p = Path(sys.argv[1]); me = sys.argv[2]
            for _ in range(50):
                with locked(p):
                    d = json.loads(p.read_text() or "{{}}"); d[me] = d.get(me, 0) + 1
                    time.sleep(0.001); atomic_write_text(p, json.dumps(d))
        """)
        c = Path(td) / "counter.json"
        c.write_text("{}")
        procs = [subprocess.Popen([sys.executable, "-c", child, str(c), n]) for n in ("a", "b")]
        rcs = [pr.wait() for pr in procs]
        data = json.loads(c.read_text())
        ok("two processes under locked(): no lost update", rcs == [0, 0] and data == {"a": 50, "b": 50})
        ok("lock sidecar is beside the file", (Path(td) / "counter.json.lock").exists())
    print(f"atomic_io selftest: {'PASS' if not failures else 'FAIL'} ({len(failures)} failure(s))")
    return 1 if failures else 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    print(__doc__)
