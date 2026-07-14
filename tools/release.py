#!/usr/bin/env python3
"""release.py -- read-only release planner + checker for the Creator OS ecosystem (P47).

The self-update lane (tools/update_check.py) polls the repo's GitHub releases. With zero releases
published it always reports `no_release` while .claude-plugin/plugin.json advertises autoUpdate, so the
self-update path is inert. This tool READIES (it does not fire) the baseline release: it reports the
current release state and prints the EXACT, unexecuted commands to cut it.

Cutting a release is outward-facing and irreversible, so it is never automatic:

  python3 tools/release.py --check      # report local version + whether a matching release exists (read-only)
  python3 tools/release.py --plan        # print the exact `git tag` + `gh release create` commands (read-only)
  python3 tools/release.py --execute --yes  # actually cut it -- ONLY where `gh` is installed; else prints + refuses
  python3 tools/release.py --selftest     # offline

--execute never runs without both `gh` on PATH and an explicit --yes; absent `gh` it prints the manual
commands and refuses (this environment has no gh -- run it on a machine that does, or dispatch the
release CI job). Reuse: version.read_versions; update_check.build_report / local_version. This tool
never writes code, never pushes a branch, and never fabricates a release.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import update_check  # noqa: E402
import version as versionmod  # noqa: E402


def local_version():
    return versionmod.read_versions()[0]


def release_notes(version):
    """A clean, outward-appropriate baseline note. Deliberately generic: STATE.md is an internal
    phase log and is not dumped into a public release. The note points at the tracked history instead."""
    return (f"Creator OS {version} baseline release.\n\n"
            f"First tagged release of the Creator OS ecosystem (routing hub, governance skill, Content/"
            f"Document/Pipeline spokes, atom library, and the currency + freshness tooling). This tag "
            f"lets the self-update check (tools/update_check.py) resolve a published release instead of "
            f"reporting no_release. See STATE.md and the commit history for the phase-by-phase detail.")


def plan(version=None):
    version = version or local_version()
    tag = f"v{version}"
    notes = release_notes(version)
    return {
        "tag": tag,
        "title": f"Creator OS {tag}",
        "notes": notes,
        "commands": [
            f"git tag -a {tag} -m 'Creator OS {tag} baseline release'",
            f"git push origin {tag}",
            f"gh release create {tag} --title 'Creator OS {tag}' --notes '<the notes above>'",
        ],
        "boundary": ("Outward-facing and irreversible. Run these where `gh` is authenticated (your "
                     "machine or the release CI job); this tool will not push a tag or create a release "
                     "for you unless --execute --yes is used AND gh is installed."),
    }


def check(getter=None, offline=False):
    """Read-only: report the local version and whether a matching published release exists upstream."""
    local = local_version()
    kwargs = {"offline": offline}
    if getter is not None:
        kwargs["getter"] = getter
    report = update_check.build_report(local, **kwargs)
    return {
        "local_version": local,
        "expected_tag": f"v{local}",
        "release_status": report.get("status"),
        "latest_seen": report.get("latest_seen"),
        "note": report.get("note"),
        "self_update_inert": report.get("status") in ("no_release",),
    }


def execute(version=None, assume_yes=False, runner=None):
    """Cut the release -- guarded. Requires `gh` on PATH and assume_yes. Absent either, prints the plan
    and refuses (returns a dict with executed=False). runner is injectable for the selftest."""
    p = plan(version)
    have_gh = shutil.which("gh") is not None
    if not have_gh or not assume_yes:
        reason = ("gh is not installed in this environment" if not have_gh
                  else "--yes was not passed")
        return {"executed": False, "reason": reason, "plan": p,
                "next": "run the commands in plan.commands where gh is authenticated"}
    runner = runner or (lambda args: subprocess.run(args, cwd=str(ROOT), check=True))
    tag = p["tag"]
    runner(["git", "tag", "-a", tag, "-m", f"Creator OS {tag} baseline release"])
    runner(["git", "push", "origin", tag])
    runner(["gh", "release", "create", tag, "--title", p["title"], "--notes", p["notes"]])
    return {"executed": True, "tag": tag}


def selftest():
    checks = []

    def ok(name, cond):
        checks.append((name, bool(cond)))

    p = plan("0.1.0")
    ok("plan tag is v-prefixed", p["tag"] == "v0.1.0")
    ok("plan lists git tag + push + gh release create",
       any("git tag" in c for c in p["commands"]) and any("gh release create" in c for c in p["commands"]))
    ok("notes name the version and say baseline", "0.1.0" in p["notes"] and "baseline" in p["notes"].lower())
    ok("notes carry no claude.ai session link", "claude.ai/code/session" not in p["notes"])

    # check() maps an injected release report; the getter returns (data, err), never raises.
    def getter_404(url, timeout=0):
        return None, "404 Not Found"
    r = check(getter=getter_404)
    ok("check reports no_release as inert when 404", r["release_status"] == "no_release" and r["self_update_inert"])
    ok("check expected_tag matches local", r["expected_tag"] == f"v{r['local_version']}")

    def getter_current(url, timeout=0):
        return {"tag_name": f"v{local_version()}", "name": "x", "published_at": "2026-07-14T00:00:00Z"}, None
    r2 = check(getter=getter_current)
    ok("check reports current when a matching release exists", r2["release_status"] == "current"
       and not r2["self_update_inert"])

    # execute() refuses without gh (this env) and never runs the runner
    calls = []
    res = execute("0.1.0", assume_yes=True, runner=lambda args: calls.append(args))
    ok("execute refuses without gh and runs nothing", res["executed"] is False and not calls)
    ok("execute refusal carries the ready plan", "commands" in res["plan"])

    passed = sum(1 for _, c in checks if c)
    for name, c in checks:
        print(f"  [{'ok' if c else 'FAIL'}] {name}")
    total = len(checks)
    print(f"selftest: {'PASS' if passed == total else 'FAIL'} ({passed} of {total} checks)")
    return 0 if passed == total else 1


def main(argv):
    if "--selftest" in argv:
        return selftest()
    if "--plan" in argv:
        print(json.dumps(plan(), indent=2))
        return 0
    if "--execute" in argv:
        res = execute(assume_yes="--yes" in argv)
        print(json.dumps(res, indent=2))
        return 0 if res.get("executed") else 1
    if "--check" in argv:
        print(json.dumps(check(offline="--offline" in argv), indent=2))
        return 0
    print(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
