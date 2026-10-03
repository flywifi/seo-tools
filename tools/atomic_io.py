"""tools/atomic_io.py -- the ONE atomic writer for Creator OS (P81).

Four writers existed before this module with four different guarantees (registry_io: temp+replace
with cleanup, no mode; handoff/queue: temp+replace, no cleanup, fixed temp name; mcp_server: temp+
replace, no cleanup, no mode; wizard: bare write_text on the same secrets-bearing file the MCP server
writes atomically). This module gives every writer the same contract:

  * atomic_write_text(path, text): serialize fully, write a PID-suffixed temp file in the SAME
    directory, copy the destination's existing mode onto it, os.replace onto the destination. A reader
    sees the old bytes or the new bytes, never a mix; a crash leaves the old file intact; the temp is
    never left behind; an operator's 0600 on a token-bearing file survives.
  * locked(path): an exclusive lock on <path>.lock, held across a read-modify-write, so two
    PROCESSES (the wizard and the MCP server both write creator-os-config.local.json) cannot lose each
    other's update. POSIX uses fcntl.flock; Windows (P101) locks the sidecar's first byte with
    msvcrt.locking, polling the non-blocking form so a wait has no ten-second limit. On a platform
    with neither, the lock is a no-op and says so once on stderr.

A directory at the destination is refused with IsADirectoryError before anything is written, the
same on every platform (Windows' os.replace would raise PermissionError instead). Windows ignores
POSIX mode bits, so the copied mode only keeps the read-only attribute there.

Stdlib only. Invariant 42 (writer census) treats this module as the sanctioned write implementation;
a write_text() on a .local.json / credential / register path anywhere else fails the drift guard.
"""
from __future__ import annotations

import contextlib
import errno
import os
import stat
import sys
import time
from pathlib import Path

try:
    import fcntl  # POSIX only
except ImportError:  # pragma: no cover - Windows
    fcntl = None
try:
    import msvcrt  # Windows only
except ImportError:
    msvcrt = None
if fcntl is None and msvcrt is None:  # pragma: no cover
    print("[atomic_io] WARNING: no fcntl or msvcrt; cross-process locking is a no-op on this platform.",
          file=sys.stderr)


def atomic_write_text(path, text: str, *, encoding: str = "utf-8") -> None:
    """Write `text` to `path` atomically, preserving the destination's mode if it exists."""
    path = Path(path)
    if path.is_dir():
        raise IsADirectoryError(errno.EISDIR, "is a directory", str(path))
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
        _replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()


def _replace(src, dst, os_name=None, replace=None, sleep=None) -> None:
    """os.replace; on Windows, retried briefly while another process (a virus scanner, the search
    indexer) holds the destination open, which makes the replace fail with PermissionError there."""
    os_name = os_name or os.name
    replace = replace or os.replace
    sleep = sleep or time.sleep
    for attempt in range(20):
        try:
            replace(src, dst)
            return
        except PermissionError:
            if os_name != "nt" or attempt == 19:
                raise
            sleep(0.05)


@contextlib.contextmanager
def locked(path):
    """Exclusive cross-process lock on <path>.lock for the duration of the block."""
    lock = Path(path).with_name(Path(path).name + ".lock")
    lock.parent.mkdir(parents=True, exist_ok=True)
    with open(lock, "a+") as fh:
        _acquire(fh)
        try:
            yield
        finally:
            _release(fh)


# The errno msvcrt.locking sets when another handle holds the region with LK_NBLCK (EACCES).
# EDEADLOCK is set by LK_LOCK and LK_RLCK alone, which _acquire does not use.
_LOCK_HELD = (errno.EACCES,)


def _acquire(fh) -> None:
    if fcntl is not None:
        fcntl.flock(fh, fcntl.LOCK_EX)
    elif msvcrt is not None:
        # LK_LOCK gives up after ten one-second retries; poll LK_NBLCK instead, so a long writer
        # is waited for the way flock waits.
        fh.seek(0)
        while True:
            try:
                msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
                return
            except OSError as exc:
                if exc.errno not in _LOCK_HELD:
                    raise   # a bad handle or argument is an error, not a lock to wait for
                time.sleep(0.01)


def _release(fh) -> None:
    if fcntl is not None:
        fcntl.flock(fh, fcntl.LOCK_UN)
    elif msvcrt is not None:
        fh.seek(0)
        msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)


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
        if os.name == "nt":   # NTFS keeps no POSIX mode bits: chmod sets only the read-only flag
            print("  [skip] existing 0600 mode preserved across the replace (no POSIX modes on Windows)")
        else:
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
        # P101: the Windows branch of locked() (msvcrt), in this process so the code under test is
        # this module's (child processes import the file on disk). On Windows it is the real
        # msvcrt; elsewhere a stand-in backed by a non-blocking flock (separate open() calls
        # conflict even within one process), with fcntl hidden, so the polling loop in _acquire is
        # what serialises two threads.
        import threading, types, time as _t
        base = None
        if os.name == "nt" and msvcrt is not None:
            base, consts = msvcrt.locking, msvcrt   # the real lock: two handles conflict in-process
        elif fcntl is not None:
            real_f = fcntl

            def base(fd, mode, n):   # msvcrt's contract over flock: a held lock raises EACCES
                try:
                    if mode in (1, 2):   # LK_LOCK waits, LK_NBLCK does not
                        real_f.flock(fd, real_f.LOCK_EX | (real_f.LOCK_NB if mode == 2 else 0))
                    else:
                        real_f.flock(fd, real_f.LOCK_UN)
                except BlockingIOError:
                    raise OSError(errno.EACCES, "locked by another handle") from None
            consts = types.SimpleNamespace(LK_UNLCK=0, LK_LOCK=1, LK_NBLCK=2)
        lock_impl = None
        if base is not None:
            calls = []

            def _recording(fd, mode, n):   # every call: (mode, file offset, byte count)
                calls.append((mode, os.lseek(fd, 0, os.SEEK_CUR), n))
                return base(fd, mode, n)
            lock_impl = types.SimpleNamespace(LK_UNLCK=consts.LK_UNLCK, LK_LOCK=consts.LK_LOCK,
                                              LK_NBLCK=consts.LK_NBLCK, locking=_recording)
        if lock_impl is not None:
            g = globals()
            saved = (g["fcntl"], g["msvcrt"])
            g["fcntl"], g["msvcrt"] = None, lock_impl
            c2 = Path(td) / "counter2.json"
            c2.write_text("{}", encoding="utf-8")
            errors = []

            def worker(me):
                try:
                    for _ in range(50):
                        with locked(c2):
                            d = json.loads(c2.read_text(encoding="utf-8") or "{}")
                            d[me] = d.get(me, 0) + 1
                            _t.sleep(0.001)
                            atomic_write_text(c2, json.dumps(d))
                except Exception as exc:  # noqa: BLE001 - a broken lock shows up as a collision
                    errors.append(exc)
            try:
                ts = [threading.Thread(target=worker, args=(n,)) for n in ("a", "b")]
                for t in ts:
                    t.start()
                for t in ts:
                    t.join()
            finally:
                g["fcntl"], g["msvcrt"] = saved
            ok("the msvcrt branch serialises two writers: no lost update",
               not errors and json.loads(c2.read_text(encoding="utf-8")) == {"a": 50, "b": 50})
            takes = [c for c in calls if c[0] != lock_impl.LK_UNLCK]
            gives = [c for c in calls if c[0] == lock_impl.LK_UNLCK]
            ok("the msvcrt branch polls LK_NBLCK and unlocks the same region: one byte at offset 0",
               takes and gives and set(takes) == {(lock_impl.LK_NBLCK, 0, 1)}
               and set(gives) == {(lock_impl.LK_UNLCK, 0, 1)})
            # Release frees the lock while the handle is still open: a second handle can then
            # take it at once (closing the handle, which also frees it, comes later).
            g["fcntl"], g["msvcrt"] = None, lock_impl
            sidecar = Path(td) / "rel.lock"
            try:
                with open(sidecar, "a+") as fa, open(sidecar, "a+") as fb:
                    _acquire(fa)
                    _release(fa)
                    try:
                        fb.seek(0)
                        lock_impl.locking(fb.fileno(), lock_impl.LK_NBLCK, 1)
                        free = True
                        fb.seek(0)
                        lock_impl.locking(fb.fileno(), lock_impl.LK_UNLCK, 1)
                    except OSError:
                        free = False
            finally:
                g["fcntl"], g["msvcrt"] = saved
            ok("the msvcrt branch releases the lock while the handle is still open", free)
        # An error other than a held lock (a bad handle or argument) is raised, not retried
        # forever. The stand-in raises EINVAL once; a second call means it was retried.
        tries = {"n": 0}

        def _bad(fd, mode, n):
            tries["n"] += 1
            if tries["n"] > 1:
                raise RuntimeError("retried")
            raise OSError(errno.EINVAL, "bad argument")
        g = globals()
        saved = (g["fcntl"], g["msvcrt"])
        g["fcntl"], g["msvcrt"] = None, types.SimpleNamespace(LK_UNLCK=0, LK_LOCK=1, LK_NBLCK=2, locking=_bad)
        try:
            with open(Path(td) / "bad.lock", "a+") as fh:
                _acquire(fh)
            outcome = "returned"
        except RuntimeError:
            outcome = "retried"
        except OSError as exc:
            outcome = "raised" if exc.errno == errno.EINVAL else "other"
        finally:
            g["fcntl"], g["msvcrt"] = saved
        ok("the msvcrt branch raises an error other than a held lock instead of retrying it",
           outcome == "raised")
        # A directory at the destination is refused before writing, so Windows (where os.replace
        # raises PermissionError onto a directory) gives the same IsADirectoryError.
        g = globals()
        saved_replace = g["_replace"]

        def _windows_like_replace(src, dst):
            raise PermissionError(13, "Access is denied", str(dst))
        g["_replace"] = _windows_like_replace
        try:
            atomic_write_text(d, "x")
            refused = False
        except IsADirectoryError:
            refused = True
        except PermissionError:
            refused = False
        finally:
            g["_replace"] = saved_replace
        ok("a directory destination raises IsADirectoryError even where replace would say PermissionError",
           refused)
        # _replace retries a Windows PermissionError (a scanner holding the file) and succeeds;
        # elsewhere a PermissionError is raised at once.
        def flaky(fails):
            state = {"n": 0}

            def rep(src, dst):
                state["n"] += 1
                if state["n"] <= fails:
                    raise PermissionError(13, "in use", str(dst))
            return rep, state
        rep, st = flaky(2)
        _replace("a", "b", os_name="nt", replace=rep, sleep=lambda s: None)
        ok("on Windows a replace refused twice is retried and succeeds", st["n"] == 3)
        rep, st = flaky(2)
        try:
            _replace("a", "b", os_name="posix", replace=rep, sleep=lambda s: None)
            posix_raised = False
        except PermissionError:
            posix_raised = True
        ok("off Windows a refused replace raises at once, without retrying", posix_raised and st["n"] == 1)
        rep, st = flaky(99)
        try:
            _replace("a", "b", os_name="nt", replace=rep, sleep=lambda s: None)
            gave_up = False
        except PermissionError:
            gave_up = True
        ok("on Windows the retry gives up after 20 attempts", gave_up and st["n"] == 20)
    print(f"atomic_io selftest: {'PASS' if not failures else 'FAIL'} ({len(failures)} failure(s))")
    return 1 if failures else 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    print(__doc__)
