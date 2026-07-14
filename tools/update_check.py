#!/usr/bin/env python3
"""update_check.py -- token-free self-update check for the Creator OS ecosystem itself.

The fourth currency lane. dependency_currency.py watches third-party deps; source_currency.py
watches web sources; competitor_snapshot.py watches competitors. This one answers the question no
existing checker covers: "has a NEWER Creator OS release been published upstream than the copy I
have installed?" It is a read-only poll of the repo's own GitHub releases (stdlib urllib, honoring
the env proxy + CA bundle, never raises), compared against the locally installed VERSION.

It NEVER pulls, never writes code, and contacts only the public releases API. Applying an update
stays the user's explicit `python3 tools/update.py` run (git pull + drift guard + cache rebuild),
which by design never touches *.local.json data. The optional `check --apply` only stamps
last_checked / latest_seen on the registry's own `creator-os-release` currency entry (token-free
maintenance), through the shared registry_io writer.

Design rules honored (P44):
  R2  check is decoupled from apply: this tool only checks and proposes; it never applies.
  R5  nothing leaves the machine: outbound is a single GET to the public releases API; no upload.

Reuse (not reinvented): dependency_currency._http_get_json / fetch_latest / parse_version / _cmp;
version.read_versions; registry_io.save_registry (the sole registry writer).

Usage:
  python3 tools/update_check.py report                 # read-only: poll releases, compare, print JSON
  python3 tools/update_check.py check                  # report + a one-line apply hint
  python3 tools/update_check.py check --apply           # + token-free stamp of the release entry
  python3 tools/update_check.py report --offline         # skip network; status 'unknown' (no nag)
  python3 tools/update_check.py --selftest               # pure compare logic + injected fetcher, no network
"""
import argparse
import json
import os
import subprocess
import sys
from datetime import date
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parent))
import registry_io  # noqa: E402  (the single shared registry writer)
import version as version_mod  # noqa: E402
from dependency_currency import _cmp, _http_get_json, fetch_latest, parse_version  # noqa: E402

TOOL = "tools/update_check.py"
# The upstream the installed copy tracks. Overridable so a fork / self-host can point elsewhere and
# so the selftest never depends on a real slug.
REPO = os.environ.get("CREATOR_OS_UPDATE_REPO", "flywifi/seo-tools")
# The registry currency entry this tool stamps (seeded via source_currency.py seed-sources, P44-1).
RELEASE_ENTRY_ID = "creator-os-release"


def release_url(repo=None):
    return f"https://api.github.com/repos/{repo or REPO}/releases/latest"


# ── deterministic compare (pure; the selftest pins this) ─────────────────────

def compare_versions(local, latest):
    """Compare installed vs upstream. Returns current | behind | ahead | unknown.
    'behind' is the only state that means an update is available."""
    lv, av = parse_version(local), parse_version(latest)
    if not lv or not av:
        return "unknown"
    c = _cmp(av, lv)  # latest vs local
    if c > 0:
        return "behind"
    if c < 0:
        return "ahead"
    return "current"


# ── report (a proposal; never applies) ───────────────────────────────────────

def local_version():
    """The installed ecosystem version (VERSION file, mirrored in versions.json/plugin.json)."""
    return version_mod.read_versions()[0]


# ── update channels + branch-commit fallback (P48) ───────────────────────────
# When there is NO published release, compare the installed commit against a tracked branch so the
# self-update path is not inert. Model the branch as a named channel: `stable` -> main (the released
# line), `nightly` -> an experimental branch. Read-only; one GET; never raises; never nags.

DEFAULT_CHANNELS = {"stable": "main", "nightly": "main"}
REPO_ROOT = Path(__file__).resolve().parent.parent


def _load_update_config(root=REPO_ROOT):
    """Read the `update` block from creator-os-config.json, then overlay creator-os-config.local.json
    (local wins). Own tiny loader, matching the per-tool load_config variants. Never raises."""
    merged = {}
    for name in ("creator-os-config.json", "creator-os-config.local.json"):
        p = root / name
        if not p.exists():
            continue
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        upd = data.get("update") if isinstance(data, dict) else None
        if not isinstance(upd, dict):
            continue
        for k, v in upd.items():
            if k == "channels" and isinstance(v, dict):
                merged.setdefault("channels", {}).update({kk: vv for kk, vv in v.items() if isinstance(vv, str)})
            else:
                merged[k] = v
    return merged


def resolve_channel(config_loader=_load_update_config):
    """Resolve (channel, branch). Precedence (highest first): CREATOR_OS_UPDATE_BRANCH env (explicit
    branch escape hatch) > CREATOR_OS_UPDATE_CHANNEL env > merged config `update.channel` > default
    `stable`. The branch comes from the channels map (default {stable: main, nightly: main})."""
    upd = config_loader() or {}
    channels = dict(DEFAULT_CHANNELS)
    channels.update(upd.get("channels") or {})
    channel = os.environ.get("CREATOR_OS_UPDATE_CHANNEL") or upd.get("channel") or "stable"
    if channel not in channels:
        channel = "stable"
    branch = os.environ.get("CREATOR_OS_UPDATE_BRANCH") or channels.get(channel) or "main"
    return channel, branch


def get_local_sha(runner=subprocess.run):
    """The installed commit sha via `git rev-parse HEAD`. Returns "" on any failure (git absent, not a
    repo, shallow/detached is fine — HEAD always resolves). Injectable for the offline selftest."""
    try:
        out = runner(["git", "rev-parse", "HEAD"], cwd=str(REPO_ROOT),
                     capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return ""
    if getattr(out, "returncode", 1) == 0:
        return (out.stdout or "").strip()
    return ""


def compare_url(repo, base_sha, branch):
    """GitHub compare, base=local sha, head=tracked branch (three-dot). Quote the branch (names carry
    '/'); leave '...' literal."""
    return f"https://api.github.com/repos/{repo}/compare/{base_sha}...{quote(branch, safe='')}"


def classify_compare(gh_status, ahead_by):
    """Pure (pinned by the selftest). base=local, head=branch, so GitHub's own direction inverts:
    'ahead' means the upstream branch has commits the local copy lacks -> the local copy is BEHIND."""
    if gh_status == "ahead":
        return "behind_unreleased"
    if gh_status == "identical":
        return "current"
    if gh_status == "behind":
        return "ahead"
    return "unknown"  # diverged / anything unexpected


def parse_compare(data):
    """Return (gh_status, ahead_by, behind_by, upstream_sha, upstream_date, err). Truncation-safe: the
    decision reads only status + ahead_by (always accurate); the commits array truncates at 250, so
    upstream_sha (cosmetic) is taken from commits[-1] only when untruncated, else from permalink_url,
    else None. Guards every access; returns an err string rather than raising."""
    if not isinstance(data, dict):
        return None, 0, 0, None, None, "compare payload is not an object"
    gh_status = data.get("status")
    if gh_status not in ("ahead", "behind", "identical", "diverged"):
        return None, 0, 0, None, None, f"unexpected compare status {gh_status!r}"
    ahead_by = int(data.get("ahead_by") or 0)
    behind_by = int(data.get("behind_by") or 0)
    commits = data.get("commits") if isinstance(data.get("commits"), list) else []
    total = data.get("total_commits")
    upstream_sha, upstream_date = None, None
    untruncated = isinstance(total, int) and total <= len(commits)
    if commits and untruncated and isinstance(commits[-1], dict):
        upstream_sha = commits[-1].get("sha")
        commit = commits[-1].get("commit") or {}
        committer = commit.get("committer") or {}
        upstream_date = (committer.get("date") or "")[:10] or None
    if not upstream_sha:
        purl = data.get("permalink_url") or ""
        if "..." in purl:
            tail = purl.rsplit("...", 1)[-1]
            upstream_sha = (tail.split(":", 1)[-1] or None) if ":" in tail else None
    return gh_status, ahead_by, behind_by, upstream_sha, upstream_date, None


def branch_fallback(repo, branch, channel, getter=_http_get_json, sha_getter=get_local_sha):
    """Compare the installed commit against the tracked branch. Returns the annotation dict, or None
    when there is no local sha (caller then keeps `no_release`). Never raises; degrades to
    `unreachable` on any compare failure (e.g. the installed sha is not present upstream -> 404)."""
    local_sha = sha_getter()
    if not local_sha:
        return None
    base = {"detection_method": "branch", "channel": channel, "tracked_branch": branch,
            "installed_commit": local_sha[:12], "upstream_commit": None,
            "latest_seen": None, "latest_seen_date": None, "commits_behind": 0}
    data, err = getter(compare_url(repo, local_sha, branch))
    if err or data is None:
        base.update(status="unreachable", update_available=False,
                    note=(f"Could not compare against the {channel} branch ({branch}); the installed "
                          "commit may not exist upstream. No update state is implied."))
        return base
    gh_status, ahead_by, _behind, upstream_sha, upstream_date, perr = parse_compare(data)
    if perr:
        base.update(status="unreachable", update_available=False,
                    note=f"Unreadable compare response ({perr}). No update state is implied.")
        return base
    status = classify_compare(gh_status, ahead_by)
    commits_behind = ahead_by if status == "behind_unreleased" else 0
    notes = {
        "behind_unreleased": f"{commits_behind} newer commit(s) on the {channel} channel (branch "
                             f"{branch}); no release cut yet.",
        "current": f"Up to date with the {channel} channel (branch {branch}); no release published yet.",
        "ahead": f"Your copy is ahead of the {channel} channel (branch {branch}) (a development build).",
        "unknown": f"Your copy has diverged from the {channel} channel (branch {branch}).",
    }
    base.update(status=status, update_available=(status == "behind_unreleased"),
                note=notes[status], commits_behind=commits_behind,
                upstream_commit=(upstream_sha[:12] if upstream_sha else None),
                latest_seen=(upstream_sha[:12] if upstream_sha else None),
                latest_seen_date=upstream_date)
    return base


def build_report(local, offline=False, getter=_http_get_json, repo=None, branch=None, channel=None,
                 sha_getter=get_local_sha):
    """Poll the repo's latest release and classify. `local` is the installed version string;
    `getter` is injectable so the selftest never hits the network. Never raises. When no release is
    published, falls back to a branch-commit comparison (P48)."""
    repo = repo or REPO
    if channel is None or branch is None:
        rc_channel, rc_branch = resolve_channel()
        channel = channel or rc_channel
        branch = branch or rc_branch
    entry = {"upstream_api": "github_releases", "check_url": release_url(repo)}
    if offline:
        latest, latest_date, err = None, None, "offline"
    else:
        latest, latest_date, err = fetch_latest(entry, getter=getter)

    branch_extra = {"detection_method": "release"}
    if latest is None:
        if offline:
            status, note = "unknown", "Offline: no check performed. No update state is implied."
            update_available = False
        elif err and "404" in err:
            # No published release: fall back to a branch-commit comparison (P48). If there is no
            # local sha (git absent / not a repo), keep the original no_release behavior.
            fb = branch_fallback(repo, branch, channel, getter=getter, sha_getter=sha_getter)
            if fb is None:
                status, note, update_available = (
                    "no_release", "No published release upstream yet; nothing to compare against.", False)
            else:
                status, note, update_available = fb["status"], fb["note"], fb["update_available"]
                latest, latest_date = fb["latest_seen"], fb["latest_seen_date"]
                branch_extra = {k: fb[k] for k in ("detection_method", "channel", "tracked_branch",
                                                   "commits_behind", "installed_commit", "upstream_commit")}
        else:
            status, note = "unreachable", "Could not reach the releases API; try again later."
            update_available = False
    else:
        status = compare_versions(local, latest)
        note = {
            "current": "You are on the latest published release.",
            "behind": "A newer Creator OS release is available upstream.",
            "ahead": "Your installed version is newer than the latest published release (development copy).",
            "unknown": "Versions could not be compared.",
        }[status]
        update_available = status == "behind"

    report = {
        "as_of": date.today().isoformat(),
        "computed_by": f"{TOOL}.compare_versions",
        "repo": repo,
        "local_version": local,
        "latest_seen": latest,
        "latest_seen_date": latest_date,
        "status": status,
        "update_available": update_available,
        "note": note,
        "apply": {
            "how": "python3 tools/update.py",
            "note": ("Applying is your explicit choice. It pulls new code and rebuilds the cache. "
                     "It never touches your .local data files (rate card, deals, contracts, templates)."),
        },
        "boundary": ("Read-only version check. This tool never pulls, never writes code, and contacts "
                     "only the public releases API. Nothing about your data leaves this machine."),
        "human_review_required": True,
    }
    report.update(branch_extra)
    if err:
        report["fetch_error"] = err
    return report


# ── token-free stamp of the release currency entry (via the shared writer) ────

def apply_stamp(registry, report, saver=registry_io.save_registry):
    """Stamp last_checked / latest_seen on the registry's creator-os-release entry. Reachable
    results only. `saver` is injectable so the selftest never writes the real registry."""
    if report.get("latest_seen") is None:
        return {"stamped": [], "note": "no latest_seen observed; nothing to stamp"}
    by_id = {s["id"]: s for s in registry.get("sources", [])}
    entry = by_id.get(RELEASE_ENTRY_ID)
    if not entry:
        return {"stamped": [],
                "note": f"{RELEASE_ENTRY_ID} not in registry; run: python3 tools/source_currency.py seed-sources <file>"}
    today = date.today().isoformat()
    entry["last_checked"] = today
    entry["latest_seen"] = report["latest_seen"]
    entry["latest_seen_date"] = report.get("latest_seen_date")
    drift = report["status"] in ("behind", "behind_unreleased")
    if drift:
        entry["last_changed_detected"] = today
    registry["last_registry_update"] = today
    saver(registry)
    return {"stamped": [RELEASE_ENTRY_ID], "drift_flagged": [RELEASE_ENTRY_ID] if drift else []}


# ── selftest (pure logic + injected fetcher; no network) ─────────────────────

def selftest():
    checks = []

    def ok(name, cond):
        checks.append((name, bool(cond)))

    ok("compare behind", compare_versions("0.1.0", "0.2.0") == "behind")
    ok("compare current", compare_versions("0.1.0", "v0.1.0") == "current")
    ok("compare ahead", compare_versions("0.2.0", "0.1.0") == "ahead")
    ok("compare tag prefix", compare_versions("1.0.0", "v1.0.0") == "current")
    ok("compare padded", compare_versions("1.2", "1.2.0") == "current")
    ok("compare unknown when unparseable", compare_versions("0.1.0", "") == "unknown")

    def getter_behind(url):
        return {"tag_name": "v0.2.0", "published_at": "2026-07-10T00:00:00Z"}, None

    def getter_current(url):
        return {"tag_name": "v0.1.0", "published_at": "2026-06-01T00:00:00Z"}, None

    def getter_404(url):
        return None, "HTTPError: HTTP Error 404: Not Found"

    def getter_down(url):
        return None, "URLError: <urlopen error timed out>"

    r = build_report("0.1.0", getter=getter_behind, repo="o/r")
    ok("behind -> update_available", r["status"] == "behind" and r["update_available"] is True)
    ok("behind carries latest", r["latest_seen"] == "v0.2.0" and r["latest_seen_date"] == "2026-07-10")
    ok("report always proposes apply", r["apply"]["how"] == "python3 tools/update.py")
    ok("report never auto-applies (human_review_required)", r["human_review_required"] is True)

    r2 = build_report("0.1.0", getter=getter_current, repo="o/r")
    ok("current -> no update", r2["status"] == "current" and r2["update_available"] is False)

    # 404 with no local sha (git absent) preserves the original no_release behavior; the branch-fallback
    # path (local sha present) is covered by the P48 cases below.
    r3 = build_report("0.1.0", getter=getter_404, repo="o/r", sha_getter=lambda: "")
    ok("404 + no git -> no_release, no nag", r3["status"] == "no_release" and r3["update_available"] is False)

    r4 = build_report("0.1.0", getter=getter_down, repo="o/r")
    ok("unreachable -> no update state implied", r4["status"] == "unreachable" and r4["update_available"] is False)

    r5 = build_report("0.1.0", offline=True, getter=getter_behind, repo="o/r")
    ok("offline -> unknown, no network implied", r5["status"] == "unknown" and r5["update_available"] is False)

    # ── P48: channel resolution (pure; injected config_loader + env) ─────────
    ok("classify ahead -> behind_unreleased", classify_compare("ahead", 2) == "behind_unreleased")
    ok("classify identical -> current", classify_compare("identical", 0) == "current")
    ok("classify behind -> ahead", classify_compare("behind", 0) == "ahead")
    ok("classify diverged -> unknown", classify_compare("diverged", 0) == "unknown")
    ok("resolve default -> stable/main", resolve_channel(config_loader=lambda: {}) == ("stable", "main"))
    ok("resolve nightly maps its branch",
       resolve_channel(config_loader=lambda: {"channel": "nightly", "channels": {"nightly": "dev"}}) == ("nightly", "dev"))
    os.environ["CREATOR_OS_UPDATE_CHANNEL"] = "nightly"
    ok("env channel wins over config",
       resolve_channel(config_loader=lambda: {"channel": "stable", "channels": {"nightly": "exp"}}) == ("nightly", "exp"))
    del os.environ["CREATOR_OS_UPDATE_CHANNEL"]
    os.environ["CREATOR_OS_UPDATE_BRANCH"] = "hotfix"
    ok("env branch wins entirely",
       resolve_channel(config_loader=lambda: {"channel": "stable"})[1] == "hotfix")
    del os.environ["CREATOR_OS_UPDATE_BRANCH"]

    # ── P48: branch-commit fallback via a url-dispatched injected getter ──────
    fake_sha = lambda: "localsha0abcd"  # noqa: E731

    def compare_getter(gh_status, ahead_by=0, total=None, commits=None):
        def g(url):
            if "/compare/" in url:
                p = {"status": gh_status, "ahead_by": ahead_by, "behind_by": 0,
                     "permalink_url": "https://github.com/o/r/compare/o:localsha0abcd...o:upstreamsha99"}
                if commits is not None:
                    p["commits"] = commits
                    p["total_commits"] = total if total is not None else len(commits)
                return p, None
            return None, "HTTPError: HTTP Error 404: Not Found"  # releases -> 404
        return g

    upstream_commits = [{"sha": "upstreamsha99abc", "commit": {"committer": {"date": "2026-07-14T00:00:00Z"}}}]
    ba = build_report("0.1.0", getter=compare_getter("ahead", 3, commits=upstream_commits),
                      repo="o/r", branch="main", channel="nightly", sha_getter=fake_sha)
    ok("branch ahead -> behind_unreleased + update",
       ba["status"] == "behind_unreleased" and ba["update_available"] is True and ba["commits_behind"] == 3)
    ok("branch mode annotates channel/branch/method",
       ba["detection_method"] == "branch" and ba["channel"] == "nightly" and ba["tracked_branch"] == "main")
    ok("branch mode latest_seen is a short sha", bool(ba["latest_seen"]) and len(ba["latest_seen"]) <= 12)

    bi = build_report("0.1.0", getter=compare_getter("identical"), repo="o/r", branch="main",
                      channel="stable", sha_getter=fake_sha)
    ok("branch identical -> current", bi["status"] == "current" and bi["update_available"] is False)
    bl = build_report("0.1.0", getter=compare_getter("behind"), repo="o/r", branch="main",
                      channel="stable", sha_getter=fake_sha)
    ok("branch local-ahead -> ahead", bl["status"] == "ahead" and bl["update_available"] is False)
    bd = build_report("0.1.0", getter=compare_getter("diverged"), repo="o/r", branch="main",
                      channel="stable", sha_getter=fake_sha)
    ok("branch diverged -> unknown", bd["status"] == "unknown" and bd["update_available"] is False)

    def getter_all_404(url):
        return None, "HTTP Error 404: Not Found"
    bc = build_report("0.1.0", getter=getter_all_404, repo="o/r", branch="main", channel="stable",
                      sha_getter=fake_sha)
    ok("compare 404 (sha not upstream) -> unreachable", bc["status"] == "unreachable" and bc["update_available"] is False)

    bn = build_report("0.1.0", getter=getter_404, repo="o/r", branch="main", channel="stable",
                      sha_getter=lambda: "")
    ok("no local sha -> no_release preserved", bn["status"] == "no_release")

    br = build_report("0.1.0", getter=getter_behind, repo="o/r", branch="main", channel="stable",
                      sha_getter=fake_sha)
    ok("release exists -> detection_method release, no fallback",
       br.get("detection_method") == "release" and br["status"] == "behind")

    spy = []

    def getter_spy(url):
        spy.append(url)
        return {"tag_name": "v0.2.0", "published_at": "2026-07-10T00:00:00Z"}, None
    bo = build_report("0.1.0", offline=True, getter=getter_spy, repo="o/r", branch="main",
                      channel="stable", sha_getter=fake_sha)
    ok("offline -> unknown and getter never called", bo["status"] == "unknown" and spy == [])

    bt = build_report("0.1.0", getter=compare_getter("ahead", 300, total=300, commits=[{"sha": "x"}] * 250),
                      repo="o/r", branch="main", channel="nightly", sha_getter=fake_sha)
    ok("truncated compare -> behind_unreleased, commits_behind == ahead_by",
       bt["status"] == "behind_unreleased" and bt["commits_behind"] == 300)

    writesB = []
    regB = {"sources": [{"id": RELEASE_ENTRY_ID, "category": "creator-os-release"}]}
    resB = apply_stamp(regB, ba, saver=writesB.append)
    ok("branch behind stamps sha + flags drift",
       resB.get("drift_flagged") == [RELEASE_ENTRY_ID] and regB["sources"][0]["latest_seen"] == ba["latest_seen"])

    # apply-stamp: writes once, only the release entry, only when reachable
    writes = []
    reg = {"sources": [{"id": RELEASE_ENTRY_ID, "category": "creator-os-release"}]}
    res = apply_stamp(reg, r, saver=writes.append)
    ok("apply stamps the release entry", res["stamped"] == [RELEASE_ENTRY_ID])
    ok("apply flags drift when behind", res.get("drift_flagged") == [RELEASE_ENTRY_ID])
    ok("apply wrote once", len(writes) == 1)
    ok("stamp recorded latest_seen", reg["sources"][0]["latest_seen"] == "v0.2.0")

    # apply is a no-op when the entry is missing (never invents it)
    writes2 = []
    res2 = apply_stamp({"sources": []}, r, saver=writes2.append)
    ok("apply no-ops without the entry", res2["stamped"] == [] and len(writes2) == 0)

    # apply is a no-op when nothing was observed
    writes3 = []
    res3 = apply_stamp(reg, r3, saver=writes3.append)
    ok("apply no-ops when latest_seen is None", res3["stamped"] == [] and len(writes3) == 0)

    passed = sum(1 for _, c in checks if c)
    for name, c in checks:
        print(f"  [{'ok' if c else 'FAIL'}] {name}")
    total = len(checks)
    print(f"selftest: {'PASS' if passed == total else 'FAIL'} ({passed} of {total} checks)")
    return 0 if passed == total else 1


# ── CLI ───────────────────────────────────────────────────────────────────────

def main(argv):
    ap = argparse.ArgumentParser(description="Token-free self-update check for the Creator OS ecosystem.")
    ap.add_argument("command", nargs="?", choices=["report", "check"], help="report (read-only) or check (+apply hint)")
    ap.add_argument("--offline", action="store_true", help="skip the network; status 'unknown' (no update implied)")
    ap.add_argument("--apply", action="store_true", help="(check) stamp last_checked/latest_seen on the release entry")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)

    if args.selftest:
        return selftest()
    if not args.command:
        ap.print_help()
        return 2

    report = build_report(local_version(), offline=args.offline)

    if args.command == "check":
        report["apply_hint"] = (
            "python3 tools/update.py" if report["update_available"]
            else "up to date; nothing to apply" if report["status"] == "current"
            else "no action")
        if args.apply:
            registry = registry_io.load_registry()
            report["applied"] = apply_stamp(registry, report)

    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
