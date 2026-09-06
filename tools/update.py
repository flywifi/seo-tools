#!/usr/bin/env python3
"""Creator OS regular update — pull the active update channel's branch and rebuild if needed.

Run this instead of bare `git pull` to get code updates, verify the drift
guard, and rebuild the keyword cache automatically when canonical sources change.
The branch is the active update channel's (stable -> main by default; see P48 /
tools/update_check.py resolve_channel), so it always matches what the update check
compared against.

Your local data files (*.local.json, competitor snapshots, SQLite caches) are
never touched by this script.

Usage:
    python3 tools/update.py
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PYTHON = sys.executable

sys.path.insert(0, str(ROOT / "tools"))
from update_check import resolve_channel  # noqa: E402  (shared channel->branch resolution, P48)


def _run(cmd: list, capture: bool = False) -> tuple:
    result = subprocess.run(
        cmd,
        cwd=str(ROOT),
        capture_output=capture,
        text=True,
    )
    return result.returncode, result.stdout if capture else ""


def get_head_sha() -> str:
    rc, out = _run(["git", "rev-parse", "HEAD"], capture=True)
    return out.strip() if rc == 0 else ""


def pull_updates() -> bool:
    """Pull from the active update channel's branch (P48). Returns True if new commits were pulled.
    Default channel `stable` -> `main`, so the behavior is unchanged unless a channel/branch override
    is set. This is the SAME branch tools/update_check.py compares against."""
    channel, branch = resolve_channel()
    before = get_head_sha()
    print(f"Pulling from origin {branch} ({channel} channel)...", flush=True)
    rc, _ = _run(["git", "pull", "origin", branch])
    if rc != 0:
        print("  [error] git pull failed. Check your network connection and try again.", flush=True)
        sys.exit(1)
    after = get_head_sha()
    if before == after:
        print("  Already up to date.", flush=True)
        return False
    print(f"  Updated: {before[:7]} -> {after[:7]}", flush=True)
    return True


def canonical_sources_changed(old_sha: str, new_sha: str) -> bool:
    """Check if canonical-sources/ changed between two SHAs."""
    if not old_sha or not new_sha or old_sha == new_sha:
        return False
    rc, out = _run(
        ["git", "diff", "--name-only", old_sha, new_sha, "--", "canonical-sources/"],
        capture=True,
    )
    return rc == 0 and bool(out.strip())


def rebuild_cache() -> None:
    cache_script = ROOT / "shared" / "cache" / "cache.py"
    if not cache_script.exists():
        print("  [warn] shared/cache/cache.py not found — skipping cache rebuild.", flush=True)
        return
    print("  Canonical sources changed — rebuilding keyword cache...", flush=True)
    rc, _ = _run([PYTHON, str(cache_script), "--build"])
    if rc == 0:
        print("  [ok] Keyword cache rebuilt.", flush=True)
    else:
        print("  [warn] Cache rebuild failed. Run manually: python3 shared/cache/cache.py --build", flush=True)


def run_drift_guard() -> None:
    sync_script = ROOT / "tools" / "sync_check.py"
    if not sync_script.exists():
        print("  [warn] tools/sync_check.py not found — skipping.", flush=True)
        return
    rc, _ = _run([PYTHON, str(sync_script)])
    if rc == 0:
        print("  [ok] Drift guard clean.", flush=True)
    else:
        print("  [warn] Drift guard reported issues. Review above and fix before using the system.", flush=True)


def main() -> None:
    print("Creator OS — update", flush=True)
    print("=" * 40, flush=True)

    before_sha = get_head_sha()
    updated = pull_updates()
    after_sha = get_head_sha()

    print("\nVerifying...", flush=True)
    run_drift_guard()

    if updated and canonical_sources_changed(before_sha, after_sha):
        rebuild_cache()
    elif updated:
        print("  Canonical sources unchanged — no cache rebuild needed.", flush=True)

    print("\nDone.", flush=True)


if __name__ == "__main__":
    main()
