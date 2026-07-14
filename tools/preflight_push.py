#!/usr/bin/env python3
"""preflight_push.py -- read-only push-blocker predictor (P47).

Before you push, this reports every condition that would fail CI or be rejected by the commit
hygiene hooks, in one place, WITHOUT changing anything. It does not reimplement the checkers; it
imports/invokes the existing ones and aggregates their verdicts:

  - drift          : the drift guard (tools/sync_check.py) -- the CI `guard` job.
  - version        : VERSION == versions.json.ecosystem == .claude-plugin/plugin.json (version.py --check).
  - freshness      : the knowledge-bundle projection is not un-restamped (build_freshness_bundle.check).
  - commit-hygiene : no claude.ai session link / personal email in the pending commit range or its
                     author emails (the #1 push landmine; mirrors the CI commit-message backstop).
  - staged-hygiene : no staged secret content or forbidden file type (the pre-commit surface).
  - tracked-hygiene: no secret content in tracked files (invariant 21).

Each class reports {class, status, problems, fix_hint}. status is pass / fail / skip (skip when git
is unavailable, e.g. a bare export). This tool is ADVISORY: it exits 0 by default so it can never
itself block a push. `--strict` exits 1 when any class fails (for an opt-in gate); `--json` prints
the machine-readable report; `--selftest` runs offline.

  python3 tools/preflight_push.py            # human summary, exit 0
  python3 tools/preflight_push.py --json      # JSON report, exit 0
  python3 tools/preflight_push.py --strict    # exit 1 if any class fails
  python3 tools/preflight_push.py --selftest   # offline self-test

Pure stdlib, read-only, no network. Never writes, commits, pushes, or restamps.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import build_freshness_bundle as freshness  # noqa: E402
import secret_scan  # noqa: E402
import version as versionmod  # noqa: E402


def _result(cls, problems, fix_hint, status=None):
    problems = list(problems or [])
    if status is None:
        status = "pass" if not problems else "fail"
    return {"class": cls, "status": status, "problems": problems, "fix_hint": fix_hint}


# --------------------------------------------------------------------------- #
# Individual predictors (each takes an injectable dependency so --selftest is offline).
# --------------------------------------------------------------------------- #
def _run_sync_check():
    """Return (returncode, [problem lines]). Subprocess keeps preflight decoupled from
    sync_check's PROBLEMS module global (the coupling the P47 design flagged as a risk)."""
    out = subprocess.run([sys.executable, str(ROOT / "tools" / "sync_check.py")],
                         capture_output=True, text=True, timeout=120)
    problems = [ln.strip()[2:] for ln in out.stdout.splitlines() if ln.startswith("  - ")]
    return out.returncode, problems


def check_drift(runner=_run_sync_check):
    rc, problems = runner()
    return _result("drift", [] if rc == 0 else (problems or ["drift guard reported drift"]),
                   "run `python3 tools/sync_check.py` and resolve each reported invariant")


def check_version(reader=versionmod.read_versions):
    vf, vj, plugin = reader()
    eco = vj.get("ecosystem")
    problems = []
    if vf != eco:
        problems.append(f"VERSION ({vf}) != versions.json ecosystem ({eco})")
    if plugin.get("version") != eco:
        problems.append(f"plugin.json version ({plugin.get('version')}) != ecosystem ({eco})")
    return _result("version", problems,
                   "align VERSION, versions.json.ecosystem, and .claude-plugin/plugin.json")


def check_freshness(checker=freshness.check):
    ok, problems = checker()
    return _result("freshness", [] if ok else problems,
                   "python3 tools/build_freshness_bundle.py --apply  (stamps the baseline; no GitHub)")


def _resolve_commit_range():
    """The range CI's backstop scans (origin/main..HEAD) when resolvable, else a local fallback.
    Read-only: never fetches. Returns None when no usable range exists."""
    for base in ("origin/main", "main"):
        r = subprocess.run(["git", "rev-parse", "--verify", "--quiet", base],
                           cwd=str(ROOT), capture_output=True, text=True)
        if r.returncode == 0 and r.stdout.strip():
            return f"{base}..HEAD"
    r = subprocess.run(["git", "rev-parse", "--verify", "--quiet", "HEAD~20"],
                       cwd=str(ROOT), capture_output=True, text=True)
    if r.returncode == 0:
        return "HEAD~20..HEAD"
    return "HEAD"


def _findings_to_problems(findings):
    return [f"{f['path']}: {f['pattern_id']}: {f['match']}" for f in findings]


def check_commit_hygiene(rng=None, scanner=secret_scan.scan_commit_messages, allowlist=None):
    """Predict the CI commit-message backstop: a claude.ai session-link trailer (the environment
    appends one by default) or a personal author email in the pending, not-yet-pushed range would
    be rejected. This is the single highest-frequency push failure."""
    allowlist = allowlist if allowlist is not None else secret_scan._load_allowlist()
    rng = rng or _resolve_commit_range()
    if rng is None:
        return _result("commit-hygiene", [], "n/a", status="skip")
    findings = scanner(rng, allowlist)
    if findings is None:
        return _result("commit-hygiene", [], "git unavailable; cannot scan the commit range",
                       status="skip")
    return _result("commit-hygiene", _findings_to_problems(findings),
                   "rewrite the offending commit message(s) to drop the claude.ai session trailer / "
                   "personal email before pushing (repo hygiene, CLAUDE.md)")


def check_staged_hygiene(scanner=secret_scan.scan_staged, allowlist=None):
    allowlist = allowlist if allowlist is not None else secret_scan._load_allowlist()
    findings = scanner(allowlist)
    if findings is None:
        return _result("staged-hygiene", [], "git unavailable; cannot scan staged changes",
                       status="skip")
    return _result("staged-hygiene", _findings_to_problems(findings),
                   "unstage the flagged secret/file (or exempt a verified false positive in "
                   "tools/secret-scan-allowlist.json)")


def check_tracked_hygiene(scanner=secret_scan.scan_tracked, allowlist=None):
    allowlist = allowlist if allowlist is not None else secret_scan._load_allowlist()
    findings = scanner(allowlist)
    if findings is None:
        return _result("tracked-hygiene", [], "git unavailable; cannot scan tracked content",
                       status="skip")
    return _result("tracked-hygiene", _findings_to_problems(findings),
                   "remove the secret content from the tracked file (invariant 21)")


CHECKS = (check_drift, check_version, check_freshness, check_commit_hygiene,
          check_staged_hygiene, check_tracked_hygiene)


def run_all(checks=CHECKS):
    results = []
    for fn in checks:
        try:
            results.append(fn())
        except Exception as exc:  # a predictor must never crash the reporter
            results.append(_result(fn.__name__.replace("check_", ""),
                                    [f"predictor error: {exc}"], "investigate the predictor",
                                    status="skip"))
    return results


def overall_exit(results, strict):
    return 1 if (strict and any(r["status"] == "fail" for r in results)) else 0


def _print_human(results):
    icon = {"pass": "ok", "fail": "FAIL", "skip": "skip"}
    n_fail = sum(1 for r in results if r["status"] == "fail")
    print("PREFLIGHT (read-only push-blocker prediction):\n")
    for r in results:
        print(f"  [{icon[r['status']]}] {r['class']}")
        for p in r["problems"]:
            print(f"        - {p}")
        if r["status"] == "fail":
            print(f"        fix: {r['fix_hint']}")
    verdict = "clean" if n_fail == 0 else f"{n_fail} class(es) would block a push"
    print(f"\nPREFLIGHT: {verdict}")


# --------------------------------------------------------------------------- #
def selftest():
    checks = []

    def ok(name, cond):
        checks.append((name, bool(cond)))

    # Fixture strings concatenated so this file carries no real-looking token at rest
    # (scan_tracked reads preflight_push.py content; only secret_scan.py is exempt).
    sess = "https://claude." + "ai/code/session_" + "selftestXYZ"
    al = {"entries": []}

    # 1. version predictor: consistent triple passes, drifted triple fails.
    ok("version pass on consistent triple",
       check_version(reader=lambda: ("0.1.0", {"ecosystem": "0.1.0"}, {"version": "0.1.0"}))["status"] == "pass")
    vres = check_version(reader=lambda: ("0.1.0", {"ecosystem": "0.2.0"}, {"version": "0.1.0"}))
    ok("version fail on drifted ecosystem", vres["status"] == "fail" and len(vres["problems"]) == 2)

    # 2. freshness predictor maps (ok, problems) -> pass/fail.
    ok("freshness pass", check_freshness(checker=lambda: (True, []))["status"] == "pass")
    fres = check_freshness(checker=lambda: (False, ["re-run --apply"]))
    ok("freshness fail carries problem + fix", fres["status"] == "fail"
       and "build_freshness_bundle" in fres["fix_hint"])

    # 3. drift predictor maps returncode -> status.
    ok("drift pass on rc0", check_drift(runner=lambda: (0, []))["status"] == "pass")
    ok("drift fail on rc1", check_drift(runner=lambda: (1, ["catalog: x"]))["status"] == "fail")

    # 4. commit-hygiene: a session-link trailer in the range is caught (the real landmine).
    #    Prove detection through the actual secret_scan pattern, via an injected scanner that
    #    routes the fixture body through scan_text exactly as scan_commit_messages would.
    def fake_commit_scanner(rng, allowlist):
        return secret_scan.scan_text(f"Subject\n\nClaude-Session: {sess}\n", "commit:deadbeef", allowlist)
    hres = check_commit_hygiene(rng="x..y", scanner=fake_commit_scanner, allowlist=al)
    ok("commit-hygiene flags a session-link trailer", hres["status"] == "fail"
       and any("session_link" in p for p in hres["problems"]))
    clean = check_commit_hygiene(rng="x..y", scanner=lambda r, a: [], allowlist=al)
    ok("commit-hygiene clean range passes", clean["status"] == "pass")
    skipped = check_commit_hygiene(rng="x..y", scanner=lambda r, a: None, allowlist=al)
    ok("commit-hygiene skips when git unavailable", skipped["status"] == "skip")

    # 5. staged/tracked predictors map None -> skip, findings -> fail.
    ok("staged skip on None", check_staged_hygiene(scanner=lambda a: None)["status"] == "skip")
    ok("tracked fail on finding",
       check_tracked_hygiene(scanner=lambda a: [{"path": "x.md", "pattern_id": "session_link",
                                                 "match": "y"}])["status"] == "fail")

    # 6. report shape + exit-code logic.
    shaped = [check_version(reader=lambda: ("0.1.0", {"ecosystem": "0.1.0"}, {"version": "0.1.0"}))]
    ok("every result has the 4 keys",
       all(set(r) == {"class", "status", "problems", "fix_hint"} for r in shaped))
    ok("strict exits 1 when a class fails",
       overall_exit([_result("x", ["p"], "h")], strict=True) == 1)
    ok("strict exits 0 when only skips/passes",
       overall_exit([_result("x", [], "h"), _result("y", [], "h", status="skip")], strict=True) == 0)
    ok("non-strict always exits 0", overall_exit([_result("x", ["p"], "h")], strict=False) == 0)

    passed = sum(1 for _, c in checks if c)
    for name, c in checks:
        print(f"  [{'ok' if c else 'FAIL'}] {name}")
    total = len(checks)
    print(f"selftest: {'PASS' if passed == total else 'FAIL'} ({passed} of {total} checks)")
    return 0 if passed == total else 1


def main(argv):
    if "--selftest" in argv:
        return selftest()
    strict = "--strict" in argv
    results = run_all()
    if "--json" in argv:
        print(json.dumps({"results": results,
                          "would_block": [r["class"] for r in results if r["status"] == "fail"]},
                         indent=2))
    else:
        _print_human(results)
    return overall_exit(results, strict)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
