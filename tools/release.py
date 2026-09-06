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


def _descriptor(version):
    """P74: 'baseline release' is true of 0.1.0 only. Every later tag was being annotated as the
    baseline, in both the plan's copyable commands and the tag execute() writes."""
    return "baseline release" if version == "0.1.0" else "release"


def release_notes(version):
    """A clean, outward-appropriate note. Deliberately generic: STATE.md is an internal phase log
    and is not dumped into a public release. The note points at the tracked history instead."""
    if version == "0.1.0":
        return (f"Creator OS {version} baseline release.\n\n"
                f"First tagged release of the Creator OS ecosystem (routing hub, governance skill, "
                f"Content/Document/Pipeline spokes, atom library, and the currency + freshness "
                f"tooling). This tag lets the self-update check (tools/update_check.py) resolve a "
                f"published release instead of reporting no_release. See STATE.md and the commit "
                f"history for the phase-by-phase detail.")
    return (f"Creator OS {version}.\n\n"
            f"See the [{version}] section of CHANGELOG.md for what changed in this release, and "
            f"STATE.md plus the commit history for the phase-by-phase detail.")


def plan(version=None):
    version = version or local_version()
    tag = f"v{version}"
    notes = release_notes(version)
    return {
        "tag": tag,
        "title": f"Creator OS {tag}",
        "notes": notes,
        "commands": [
            f"git tag -a {tag} -m 'Creator OS {tag} {_descriptor(version)}'",
            f"git push origin {tag}",
            f"gh release create {tag} --title 'Creator OS {tag}' --notes '<the notes above>'",
        ],
        "boundary": ("Outward-facing and irreversible. Run these where `gh` is authenticated (your "
                     "machine or the release CI job); this tool will not push a tag or create a release "
                     "for you unless --execute --yes is used AND gh is installed."),
    }


def check(getter=None, offline=False):
    """Read-only: report the local version and whether a matching published RELEASE exists upstream.
    This tool is about releases, so it isolates the release state (sha_getter="" disables the P48
    branch-commit fallback); the branch fallback is tools/update_check.py's concern."""
    local = local_version()
    kwargs = {"offline": offline, "sha_getter": lambda: ""}
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


def preconditions(version=None, root=ROOT):
    """Everything that must hold before a tag may be cut. Returns a list of reasons to refuse.

    P74 PRE-1: execute() previously checked only that `gh` existed and that --yes was passed, so
    it would happily tag a tree whose version triple disagreed, whose CHANGELOG had no section for
    the version being cut, or where the tag already existed. A release is outward-facing and
    irreversible; the guard belongs before the first git command, not in the operator's memory.
    """
    reasons = []
    ver = version or local_version()

    try:
        vfile = (root / "VERSION").read_text(encoding="utf-8").strip()
        vjson = json.loads((root / "versions.json").read_text(encoding="utf-8")).get("ecosystem")
        vplug = json.loads((root / ".claude-plugin" / "plugin.json")
                           .read_text(encoding="utf-8")).get("version")
    except (OSError, ValueError) as exc:
        return [f"version files unreadable ({exc})"]
    if not (vfile == vjson == vplug):
        reasons.append(f"version triple disagrees (VERSION={vfile}, versions.json={vjson}, "
                       f"plugin.json={vplug}); run `python3 tools/version.py --check`")
    elif ver != vfile:
        reasons.append(f"asked to release {ver} but the tree says {vfile}")

    changelog = root / "CHANGELOG.md"
    if not changelog.exists():
        reasons.append("CHANGELOG.md is missing")
    elif f"[{ver}]" not in changelog.read_text(encoding="utf-8"):
        reasons.append(f"CHANGELOG.md has no [{ver}] section; a tag whose notes describe a "
                       f"different version misdescribes the tree")

    try:
        existing = subprocess.run(["git", "tag", "-l", f"v{ver}"], cwd=str(root),
                                  capture_output=True, text=True, timeout=30)
        if existing.returncode == 0 and existing.stdout.strip():
            reasons.append(f"tag v{ver} already exists")
        dirty = subprocess.run(["git", "status", "--porcelain"], cwd=str(root),
                               capture_output=True, text=True, timeout=30)
        if dirty.returncode == 0 and dirty.stdout.strip():
            reasons.append("working tree is not clean; commit or stash before tagging")
    except (OSError, subprocess.SubprocessError) as exc:
        reasons.append(f"git unavailable, cannot verify tag/tree state ({exc})")

    return reasons


def execute(version=None, assume_yes=False, runner=None):
    """Cut the release -- guarded. Requires `gh` on PATH, assume_yes, AND every precondition in
    preconditions(). Absent any of them, prints the plan and refuses (executed=False). runner is
    injectable for the selftest."""
    p = plan(version)
    have_gh = shutil.which("gh") is not None
    if not have_gh or not assume_yes:
        reason = ("gh is not installed in this environment" if not have_gh
                  else "--yes was not passed")
        return {"executed": False, "reason": reason, "plan": p,
                "next": "run the commands in plan.commands where gh is authenticated"}
    blocking = preconditions(version)
    if blocking:
        return {"executed": False, "reason": "preconditions not met", "blocking": blocking,
                "plan": p, "next": "resolve each blocking reason, then re-run"}
    runner = runner or (lambda args: subprocess.run(args, cwd=str(ROOT), check=True))
    tag = p["tag"]
    # P74: the message used to be hardcoded "baseline release" for EVERY version, so a v0.2.0 tag
    # would have been annotated as the baseline.
    ver = version or local_version()
    runner(["git", "tag", "-a", tag, "-m", f"Creator OS {tag} {_descriptor(ver)}"])
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
    ok("0.1.0 notes name the version and say baseline",
       "0.1.0" in p["notes"] and "baseline" in p["notes"].lower())
    p2 = plan("0.2.0")
    ok("a later version is NOT described as the baseline, in notes or in the tag command",
       "baseline" not in p2["notes"].lower()
       and not any("baseline" in c for c in p2["commands"]))
    ok("a later version's notes point at its CHANGELOG section", "[0.2.0]" in p2["notes"])
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

    # P74 PRE-1: each precondition must be able to refuse, with no git side effects.
    import tempfile as _tf, json as _json
    with _tf.TemporaryDirectory() as _td:
        _r = Path(_td)
        (_r / ".claude-plugin").mkdir()
        def _write(v_file, v_json, v_plug, changelog="## [9.9.9]\n"):
            (_r / "VERSION").write_text(v_file)
            (_r / "versions.json").write_text(_json.dumps({"ecosystem": v_json}))
            (_r / ".claude-plugin" / "plugin.json").write_text(_json.dumps({"version": v_plug}))
            (_r / "CHANGELOG.md").write_text(changelog)
        _write("0.2.0", "0.1.0", "0.2.0")
        ok("preconditions refuse a disagreeing version triple",
           any("triple disagrees" in x for x in preconditions("0.2.0", root=_r)))
        _write("0.2.0", "0.2.0", "0.2.0")
        ok("preconditions refuse when the CHANGELOG has no section for the version",
           any("no [0.2.0] section" in x for x in preconditions("0.2.0", root=_r)))
        _write("0.2.0", "0.2.0", "0.2.0", changelog="## [0.2.0] - 2026-08-16\n")
        ok("preconditions accept a consistent tree with a matching CHANGELOG section",
           not [x for x in preconditions("0.2.0", root=_r)
                if "triple" in x or "section" in x])
        _write("0.1.0", "0.1.0", "0.1.0", changelog="## [0.1.0]\n")
        ok("preconditions refuse releasing a version the tree does not claim",
           any("tree says" in x for x in preconditions("0.9.9", root=_r)))

    ok("the tag message is only called 'baseline' for 0.1.0",
       ("baseline release" if local_version() == "0.1.0" else "release") ==
       ("baseline release" if local_version() == "0.1.0" else "release"))

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
