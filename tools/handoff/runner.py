#!/usr/bin/env python3
"""Job runner for the Drive-hub compute hand-off (P60).

Takes validated tickets from queue.py and executes them through the EXISTING tool CLIs as fixed
argv subprocesses (never a shell, never string interpolation into a shell). The safety properties
live HERE, structurally, so every transport inherits them:

  - allowlist-only: a job_type must be in queue.ALLOWED_JOB_TYPES AND have a builder below;
    publishing/posting/sending/credential access are not job types and must never become ones
    without an approval-gated change (tools/handoff/MAINTAINER_README.md).
  - idempotent: a job_id (or unparseable-ticket stem) that already has a result is never re-run,
    so duplicate deliveries, Drive conflict copies, and double watchers are harmless.
  - confined: input_refs must resolve inside the hub root (queue.resolve_input_refs).
  - bounded: every job type has a timeout; a failure writes an honest 'failed' result with a log
    tail, never a raw traceback and never a silent hang.
  - gated: run_pass() refuses to process anything unless the compute_handoff_enabled capability is
    on (or the caller passes an explicit override, used only by the selftest).

Usage:
  python3 tools/handoff/runner.py --hub <hub_root> --once
  python3 tools/handoff/runner.py --selftest
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import env_paths  # noqa: E402
from handoff import queue as q  # noqa: E402

_MINUTE = 60
_HOUR = 3600


def _tool(name: str) -> str:
    return str(ROOT / "tools" / name)


def _build_transcribe(params, inputs):
    if len(inputs) != 1:
        return None, "transcribe_media needs exactly one input_ref (the media file)"
    return [_tool("transcribe.py"), "run", inputs[0]], None


def _build_library_complete(params, inputs):
    command = params.get("command", "match")
    if command not in ("match", "complete"):
        return None, "library_complete params.command must be 'match' or 'complete'"
    argv = [_tool("library_complete.py"), command]
    argv.extend(inputs)
    return argv, None


def _build_library_analyze(params, inputs):
    return [_tool("video_library.py"), "analyze"], None


def _build_import_parse(params, inputs):
    kinds = ("youtube-studio-csv", "youtube-studio-zip", "youtube-takeout",
             "instagram-dyi", "tiktok-dyi", "tiktok-studio-csv", "pinterest")
    kind = params.get("kind")
    if kind not in kinds:
        return None, f"import_parse_preview params.kind must be one of {kinds}"
    if len(inputs) != 1:
        return None, "import_parse_preview needs exactly one input_ref (the export bundle)"
    return [_tool("import_parse.py"), kind, inputs[0]], None


def _build_finance_report(params, inputs):
    report = params.get("report")
    if report not in ("ar-scan", "cashflow"):
        return None, "finance_report params.report must be 'ar-scan' or 'cashflow' (read-only reports only)"
    return [_tool("finance.py"), f"--{report}"], None


def _build_competitor_refresh(params, inputs):
    # Offline parse of already-fetched snapshots only; the network fetch stays a deliberate
    # local action, never a queued job.
    return [_tool("competitor_snapshot.py"), "--parse"], None


# job_type -> (argv builder, timeout seconds). Builders return (argv, error). A job type that is
# allowlisted in the schema but not yet wired here is refused honestly (see run_job), so the
# schema can lead the implementation without ever silently no-opping.
JOB_BUILDERS = {
    "transcribe_media": (_build_transcribe, 4 * _HOUR),
    "library_complete": (_build_library_complete, 2 * _HOUR),
    "library_analyze": (_build_library_analyze, 10 * _MINUTE),
    "import_parse_preview": (_build_import_parse, 10 * _MINUTE),
    "finance_report": (_build_finance_report, 10 * _MINUTE),
    "competitor_snapshot_refresh": (_build_competitor_refresh, 30 * _MINUTE),
    # "keyword_offline", "project_docs", "inbox_scan": wired in later phases; refused until then.
}


def _tail(text, lines=12, limit=2000):
    if not text:
        return None
    tail = "\n".join(text.strip().splitlines()[-lines:])
    return tail[-limit:] or None


def _version() -> str:
    try:
        return (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    except OSError:
        return "unknown"


def capability_enabled(name: str, config=None) -> bool:
    """Read one capability flag from creator-os-config(.local).json; default OFF."""
    try:
        base = json.loads((ROOT / "creator-os-config.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        base = {}
    caps = dict(base.get("capabilities", {}))
    local = ROOT / "creator-os-config.local.json"
    if local.exists():
        try:
            caps.update(json.loads(local.read_text(encoding="utf-8")).get("capabilities", {}))
        except (OSError, ValueError):
            pass
    if isinstance(config, dict):
        caps.update(config.get("capabilities", {}))
    entry = caps.get(name, {})
    return bool(entry.get("enabled")) if isinstance(entry, dict) else bool(entry)


def handoff_enabled(config=None) -> bool:
    """The master gate for the compute hand-off; default OFF."""
    return capability_enabled("compute_handoff_enabled", config)


def run_job(hub_root, ticket_path, data, *, spawn=subprocess.run) -> dict:
    """Execute one parsed ticket. Returns the result dict written to Jobs/results/. Never raises
    on a bad ticket or failed tool; every path lands as an honest result file + archived ticket."""
    started = None
    errs = q.validate_ticket(data)
    key = data.get("job_id") if isinstance(data, dict) and not errs else None
    if errs:
        key = key or Path(ticket_path).stem
        q.write_result(hub_root, key, "refused", error="; ".join(errs), tool_version=_version())
        q.archive_ticket(hub_root, ticket_path)
        return {"job_id": key, "status": "refused"}

    if q.has_result(hub_root, key):
        # Idempotency: duplicate delivery / conflict copy. Archive the extra ticket, run nothing.
        q.archive_ticket(hub_root, ticket_path)
        return {"job_id": key, "status": "duplicate_skipped"}

    inputs, ref_errs = q.resolve_input_refs(hub_root, data.get("input_refs"))
    if ref_errs:
        q.write_result(hub_root, key, "refused", error="; ".join(ref_errs), tool_version=_version())
        q.archive_ticket(hub_root, ticket_path)
        return {"job_id": key, "status": "refused"}

    builder = JOB_BUILDERS.get(data["job_type"])
    if builder is None:
        q.write_result(hub_root, key, "refused", tool_version=_version(),
                       error=f"job type '{data['job_type']}' is not wired in this version")
        q.archive_ticket(hub_root, ticket_path)
        return {"job_id": key, "status": "refused"}

    build, timeout = builder
    argv, build_err = build(data.get("params", {}), inputs)
    if build_err:
        q.write_result(hub_root, key, "refused", error=build_err, tool_version=_version())
        q.archive_ticket(hub_root, ticket_path)
        return {"job_id": key, "status": "refused"}

    started = q._utcnow()
    out_file = q.hub_paths(hub_root)["results"] / f"{key}.out.txt"
    try:
        proc = spawn([env_paths.app_python(str(ROOT))] + argv, capture_output=True,
                     text=True, timeout=timeout, cwd=str(ROOT))
        stdout = proc.stdout or ""
        out_file.parent.mkdir(parents=True, exist_ok=True)
        out_file.write_text(stdout, encoding="utf-8")
        status = "done" if proc.returncode == 0 else "failed"
        q.write_result(hub_root, key, status, started_at=started, tool_version=_version(),
                       outputs=[f"{q.RESULTS_DIR}/{out_file.name}"],
                       error=None if status == "done" else f"exit code {proc.returncode}",
                       log_tail=_tail(stdout if status == "done" else (proc.stderr or stdout)))
    except subprocess.TimeoutExpired:
        q.write_result(hub_root, key, "failed", started_at=started, tool_version=_version(),
                       error=f"timed out after {timeout}s")
        status = "failed"
    except Exception as exc:  # noqa: BLE001 - honest failure result, never a traceback
        q.write_result(hub_root, key, "failed", started_at=started, tool_version=_version(),
                       error=str(exc))
        status = "failed"
    q.archive_ticket(hub_root, ticket_path)
    return {"job_id": key, "status": status}


def run_pass(hub_root, *, spawn=subprocess.run, allow=None) -> list:
    """One queue pass: gate -> read -> dedupe by job_id -> run in priority+name order."""
    enabled = handoff_enabled() if allow is None else bool(allow)
    if not enabled:
        return [{"status": "gated",
                 "error": "compute_handoff_enabled is off; no job was read or run."}]
    q.ensure_hub_dirs(hub_root)
    entries = q.read_queue(hub_root)
    seen_ids = set()
    ordered = sorted(entries, key=lambda e: (
        (e["data"] or {}).get("priority", "normal") != "normal", str(e["path"])))
    results = []
    for e in ordered:
        if e["error"]:
            key = e["path"].stem
            if not q.has_result(hub_root, key):
                q.write_result(hub_root, key, "refused", error=e["error"], tool_version=_version())
            q.archive_ticket(hub_root, e["path"])
            results.append({"job_id": key, "status": "refused"})
            continue
        jid = e["data"].get("job_id")
        if jid in seen_ids:
            q.archive_ticket(hub_root, e["path"])
            results.append({"job_id": jid, "status": "duplicate_skipped"})
            continue
        seen_ids.add(jid)
        results.append(run_job(hub_root, e["path"], e["data"], spawn=spawn))
    return results


def selftest() -> int:
    import tempfile
    import types
    checks = []

    def ok(name, cond):
        checks.append((name, bool(cond)))

    calls = []

    def fake_spawn(argv, **kw):
        calls.append(argv)
        return types.SimpleNamespace(returncode=0, stdout='{"ok": true}\n', stderr="")

    hub = Path(tempfile.mkdtemp())
    q.ensure_hub_dirs(hub)

    # done path: submit -> run -> result + archive, exactly one spawn.
    t = q.submit(hub, "library_analyze")
    res = run_pass(hub, spawn=fake_spawn, allow=True)
    ok("job runs to done", res and res[0]["status"] == "done")
    ok("result file exists", q.has_result(hub, t["job_id"]))
    ok("queue drained to archive", len(q.read_queue(hub)) == 0)
    ok("exactly one subprocess", len(calls) == 1)
    ok("argv is the real tool, not a shell", calls[0][1].endswith("video_library.py"))

    # idempotency: same job_id delivered again is never re-run.
    q._atomic_write_json(q.hub_paths(hub)["queue"] / "dup.json",
                         {**t})
    res = run_pass(hub, spawn=fake_spawn, allow=True)
    ok("duplicate job_id skipped", res[0]["status"] == "duplicate_skipped" and len(calls) == 1)

    # conflict copies: two files, one job_id -> one run.
    t2 = {**q.submit(hub, "library_analyze")}
    # remove the ticket submit wrote, then plant two copies of it (simulating a Drive conflict pair)
    for e in q.read_queue(hub):
        e["path"].unlink()
    q._atomic_write_json(q.hub_paths(hub)["queue"] / "job.a.json", t2)
    q._atomic_write_json(q.hub_paths(hub)["queue"] / "job.a (1).json", t2)
    res = run_pass(hub, spawn=fake_spawn, allow=True)
    ok("conflict pair runs once", len(calls) == 2 and
       sorted(r["status"] for r in res) == ["done", "duplicate_skipped"])

    # structural refusals: disallowed type, unwired type, escaping ref, malformed json, bad params.
    q._atomic_write_json(q.hub_paths(hub)["queue"] / "bad1.json", {**t2, "job_id": str(__import__("uuid").uuid4()), "job_type": "publish"})
    q._atomic_write_json(q.hub_paths(hub)["queue"] / "bad2.json", {**t2, "job_id": str(__import__("uuid").uuid4()), "job_type": "project_docs"})
    q._atomic_write_json(q.hub_paths(hub)["queue"] / "bad3.json", {**t2, "job_id": str(__import__("uuid").uuid4()), "input_refs": ["../../etc/passwd"]})
    (q.hub_paths(hub)["queue"] / "bad4.json").write_text("{nope", encoding="utf-8")
    q._atomic_write_json(q.hub_paths(hub)["queue"] / "bad5.json", {**t2, "job_id": str(__import__("uuid").uuid4()), "job_type": "finance_report", "params": {"report": "mark-paid"}})
    before = len(calls)
    res = run_pass(hub, spawn=fake_spawn, allow=True)
    ok("all five hostile tickets refused, zero spawns",
       len(calls) == before and all(r["status"] == "refused" for r in res) and len(res) == 5)

    # timeout -> honest failed result.
    def timeout_spawn(argv, **kw):
        raise subprocess.TimeoutExpired(cmd=argv, timeout=kw.get("timeout", 0))
    t3 = q.submit(hub, "library_analyze")
    res = run_pass(hub, spawn=timeout_spawn, allow=True)
    ok("timeout lands as failed", res[0]["status"] == "failed")
    ok("timeout result says so",
       "timed out" in json.loads(q.result_path(hub, t3["job_id"]).read_text())["error"])

    # the master gate: nothing is read or run while the capability is off.
    q.submit(hub, "library_analyze")
    res = run_pass(hub, spawn=fake_spawn, allow=False)
    ok("gate off -> gated, queue untouched",
       res[0]["status"] == "gated" and len(q.read_queue(hub)) == 1)

    failed = [n for n, c in checks if not c]
    for n, c in checks:
        print(("ok   " if c else "FAIL ") + n)
    print(f"handoff.runner selftest: {len(checks) - len(failed)}/{len(checks)} passed")
    return 1 if failed else 0


def main(argv) -> int:
    if "--selftest" in argv:
        return selftest()
    if "--once" in argv and "--hub" in argv:
        hub = argv[argv.index("--hub") + 1]
        results = run_pass(hub)
        print(json.dumps(results, indent=2, default=str))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
