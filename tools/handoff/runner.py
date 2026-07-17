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
import os
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


def _build_transcribe(params, inputs, hub_root):
    if len(inputs) != 1:
        return None, "transcribe_media needs exactly one input_ref (the media file)"
    # P61 D4: write the SRT under the hub results, not next to the input inside Inbox/Processed.
    out_dir = str(Path(hub_root) / "Jobs" / "results")
    return [_tool("transcribe.py"), "run", inputs[0], "--out-dir", out_dir], None


def _build_transcript_normalize(params, inputs, hub_root):
    # P61 C9: a dropped transcript has no library record to attach to (R3); normalizing it into
    # segments + silence gaps + suggested chapters is the useful, fully-offline follow-up. Attaching
    # to a library video_key stays session work.
    if len(inputs) != 1:
        return None, "transcript_normalize needs exactly one input_ref (the transcript file)"
    return [str(ROOT / "shared" / "docintel" / "transcripts.py"), inputs[0],
            "--json", "--gap-metrics", "--suggest-chapters"], None


def _build_library_complete(params, inputs, hub_root):
    # P61 C10 (R1 fix): the real CLI is `match|complete --export-dir DIR [--write]`, NOT positional
    # inputs (the shipped builder produced an argparse error on every run). --write is appended ONLY
    # when the ticket asks (params.apply) AND the LOCAL job_store_writes_enabled capability is on
    # (decision WRITE-OPTIN); a forged ticket flag alone can never enable a store write.
    command = params.get("command", "match")
    if command not in ("match", "complete"):
        return None, "library_complete params.command must be 'match' or 'complete'"
    if len(inputs) != 1:
        return None, "library_complete needs exactly one input_ref (the export directory)"
    argv = [_tool("library_complete.py"), command, "--export-dir", inputs[0]]
    if command == "complete" and params.get("apply") and capability_enabled("job_store_writes_enabled"):
        argv.append("--write")
    return argv, None


def _build_library_analyze(params, inputs, hub_root):
    return [_tool("video_library.py"), "analyze"], None


def _build_import_parse(params, inputs, hub_root):
    kinds = ("youtube-studio-csv", "youtube-studio-zip", "youtube-takeout",
             "instagram-dyi", "tiktok-dyi", "tiktok-studio-csv", "pinterest")
    kind = params.get("kind")
    if kind not in kinds:
        return None, f"import_parse_preview params.kind must be one of {kinds}"
    if len(inputs) != 1:
        return None, "import_parse_preview needs exactly one input_ref (the export bundle)"
    return [_tool("import_parse.py"), kind, inputs[0]], None


def _build_finance_report(params, inputs, hub_root):
    report = params.get("report")
    if report not in ("ar-scan", "cashflow"):
        return None, "finance_report params.report must be 'ar-scan' or 'cashflow' (read-only reports only)"
    return [_tool("finance.py"), f"--{report}"], None


def _build_competitor_refresh(params, inputs, hub_root):
    # Offline parse of already-fetched snapshots only; the network fetch stays a deliberate
    # local action, never a queued job.
    return [_tool("competitor_snapshot.py"), "--parse"], None


def _build_inbox_scan(params, inputs, hub_root):
    # Read-only scan of the hub's own Inbox; the proposal lands in the job's stdout result for
    # review from any surface. Approval stays a human step (wizard /inbox).
    return [str(ROOT / "tools" / "handoff" / "inbox.py"), "scan", "--hub", str(hub_root)], None


def _build_project_docs(params, inputs, hub_root):
    # Local projection lane only: copies the knowledge pack into <hub>/Knowledge/ (stamps
    # preserved). The Google-Docs API lane needs the drive_api_polling credential and stays a
    # deliberate local action (wizard /drive-hub or the CLI), never a queued job.
    return [_tool("project_docs.py"), "project", "--hub", str(hub_root)], None


def _build_keyword_offline(params, inputs, hub_root):
    # P61 C16 (decision KW-FULL): the offline keyword report over the committed library + the
    # scoop cache. Zero network, honesty envelope structural (search_volumes always null).
    query = params.get("query")
    if not isinstance(query, str) or not query.strip():
        return None, "keyword_offline params.query must be a non-empty string"
    if len(query) > 500:
        return None, "keyword_offline params.query too long (max 500 chars)"
    return [_tool("keyword_offline.py"), "report", "--query", query, "--json"], None


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
    "inbox_scan": (_build_inbox_scan, 10 * _MINUTE),
    "project_docs": (_build_project_docs, 10 * _MINUTE),
    "transcript_normalize": (_build_transcript_normalize, 10 * _MINUTE),
    "keyword_offline": (_build_keyword_offline, 10 * _MINUTE),
}


# P61 C18 (R7): report-style job types whose done result is ALSO delivered to <hub>/Outbox/ --
# the documented "deliverables for the human" area that nothing wrote until now. transcribe_media
# stays out (its artifact is the SRT under Jobs/results, C11); failed jobs never deliver.
OUTBOX_TYPES = {"library_analyze", "finance_report", "inbox_scan", "import_parse_preview",
                "keyword_offline", "transcript_normalize"}


def _deliver_outbox(hub_root, job_type, stdout):
    """Atomically write a done job's stdout JSON to <hub>/Outbox/<job_type>.<UTC>Z.mac.json (the
    P60 dated naming rule). Returns the created name, or None when stdout is not valid JSON (the
    Jobs/results .out.txt capture still holds it either way)."""
    try:
        json.loads(stdout)
    except (ValueError, TypeError):
        return None
    stamp = q._utcnow().replace(":", "")
    outbox = Path(hub_root) / "Outbox"
    outbox.mkdir(parents=True, exist_ok=True)
    name = f"{job_type}.{stamp}.mac.json"
    n = 1
    while (outbox / name).exists():
        n += 1
        name = f"{job_type}.{stamp}.{n}.mac.json"
    tmp = outbox / (name + ".tmp")
    tmp.write_text(stdout, encoding="utf-8")
    os.replace(tmp, outbox / name)
    return name


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
    argv, build_err = build(data.get("params", {}), inputs, hub_root)
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
        outputs = [f"{q.RESULTS_DIR}/{out_file.name}"]
        if status == "done" and data.get("job_type") in OUTBOX_TYPES:
            delivered = _deliver_outbox(hub_root, data["job_type"], stdout)
            if delivered:
                outputs.append(f"Outbox/{delivered}")
        q.write_result(hub_root, key, status, started_at=started, tool_version=_version(),
                       outputs=outputs,
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

    # P61 C18 (R7): a done report-type job ALSO delivers its stdout JSON to <hub>/Outbox/.
    ob_files = sorted((hub / "Outbox").glob("library_analyze.*.mac.json"))
    result_doc = json.loads(q.result_path(hub, t["job_id"]).read_text())
    ok("done outbox-type job delivers to Outbox",
       len(ob_files) == 1 and json.loads(ob_files[0].read_text()) == {"ok": True})
    ok("result outputs list both files",
       len(result_doc["outputs"]) == 2 and result_doc["outputs"][1] == f"Outbox/{ob_files[0].name}")

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
    # P61 C16: every schema type now has a builder, so the unwired-refusal branch (kept for
    # future types) is exercised by temporarily popping a wired key -- coverage without a
    # permanently-unwired vehicle.
    q._atomic_write_json(q.hub_paths(hub)["queue"] / "bad1.json", {**t2, "job_id": str(__import__("uuid").uuid4()), "job_type": "publish"})
    q._atomic_write_json(q.hub_paths(hub)["queue"] / "bad2.json", {**t2, "job_id": str(__import__("uuid").uuid4()), "job_type": "keyword_offline", "params": {"query": "decor"}})
    q._atomic_write_json(q.hub_paths(hub)["queue"] / "bad3.json", {**t2, "job_id": str(__import__("uuid").uuid4()), "input_refs": ["../../etc/passwd"]})
    (q.hub_paths(hub)["queue"] / "bad4.json").write_text("{nope", encoding="utf-8")
    q._atomic_write_json(q.hub_paths(hub)["queue"] / "bad5.json", {**t2, "job_id": str(__import__("uuid").uuid4()), "job_type": "finance_report", "params": {"report": "mark-paid"}})
    before = len(calls)
    popped = JOB_BUILDERS.pop("keyword_offline")
    try:
        res = run_pass(hub, spawn=fake_spawn, allow=True)
    finally:
        JOB_BUILDERS["keyword_offline"] = popped
    ok("all five hostile tickets refused, zero spawns",
       len(calls) == before and all(r["status"] == "refused" for r in res) and len(res) == 5)
    _result_errs = [json.loads(p.read_text()).get("error") or ""
                    for p in q.hub_paths(hub)["results"].glob("*.status.json")]
    ok("unwired type refused honestly (popped-copy vehicle)",
       any("not wired" in e for e in _result_errs))

    # timeout -> honest failed result.
    def timeout_spawn(argv, **kw):
        raise subprocess.TimeoutExpired(cmd=argv, timeout=kw.get("timeout", 0))
    t3 = q.submit(hub, "library_analyze")
    res = run_pass(hub, spawn=timeout_spawn, allow=True)
    ok("timeout lands as failed", res[0]["status"] == "failed")
    ok("timeout result says so",
       "timed out" in json.loads(q.result_path(hub, t3["job_id"]).read_text())["error"])

    # P61 C18: a failed job never delivers to Outbox, and non-JSON stdout is never delivered.
    def fail_spawn(argv, **kw):
        return types.SimpleNamespace(returncode=3, stdout='{"ok": false}', stderr="boom")
    before_ob = len(list((hub / "Outbox").glob("*.json")))
    q.submit(hub, "library_analyze")
    res = run_pass(hub, spawn=fail_spawn, allow=True)
    ok("failed job never delivers to Outbox",
       res[0]["status"] == "failed" and
       len(list((hub / "Outbox").glob("*.json"))) == before_ob)

    def nonjson_spawn(argv, **kw):
        return types.SimpleNamespace(returncode=0, stdout="plain text", stderr="")
    t_nj = q.submit(hub, "library_analyze")
    run_pass(hub, spawn=nonjson_spawn, allow=True)
    r_nj = json.loads(q.result_path(hub, t_nj["job_id"]).read_text())
    ok("non-JSON stdout: done, no Outbox delivery, single output",
       r_nj["status"] == "done" and len(r_nj["outputs"]) == 1 and
       len(list((hub / "Outbox").glob("*.json"))) == before_ob)

    # the master gate: nothing is read or run while the capability is off.
    q.submit(hub, "library_analyze")
    res = run_pass(hub, spawn=fake_spawn, allow=False)
    ok("gate off -> gated, queue untouched",
       res[0]["status"] == "gated" and len(q.read_queue(hub)) == 1)

    # P61 C11: the transcribe builder points the SRT at the hub results, not next to the input.
    argv_t, _ = _build_transcribe({}, ["Inbox/Processed/2026-07-17/clip.mp4"], hub)
    ok("transcribe writes under Jobs/results",
       "--out-dir" in argv_t and argv_t[argv_t.index("--out-dir") + 1].endswith("Jobs/results"))

    # P61 C9: transcript_normalize builds the real transcripts.py argv.
    argv_n, err_n = _build_transcript_normalize({}, ["Inbox/Processed/2026-07-17/talk.srt"], hub)
    ok("transcript_normalize builds the transcripts CLI argv",
       err_n is None and argv_n[0].endswith("transcripts.py") and "--suggest-chapters" in argv_n)

    # P61 C10 (R1 fix): the library_complete builder now passes --export-dir (the shipped builder
    # produced an argparse error). Run the built argv against an empty temp dir: argparse must accept.
    export_dir = tempfile.mkdtemp()
    argv_lc, err_lc = _build_library_complete({"command": "match"}, [export_dir], hub)
    ok("library_complete builds --export-dir argv", err_lc is None and "--export-dir" in argv_lc)
    proc_lc = subprocess.run([env_paths.app_python(str(ROOT))] + argv_lc,
                             capture_output=True, text=True, timeout=60, cwd=str(ROOT))
    ok("library_complete argv is argparse-accepted (R1 can't recur)", proc_lc.returncode == 0)

    # P61 C10 WRITE-OPTIN: --write appears only when the ticket asks AND the local capability is on.
    _orig_cap = globals()["capability_enabled"]
    try:
        globals()["capability_enabled"] = lambda name, config=None: False
        argv_off, _ = _build_library_complete({"command": "complete", "apply": True}, [export_dir], hub)
        ok("apply without the local capability stays proposal-only", "--write" not in argv_off)
        globals()["capability_enabled"] = lambda name, config=None: True
        argv_on, _ = _build_library_complete({"command": "complete", "apply": True}, [export_dir], hub)
        ok("apply with the local capability adds --write", "--write" in argv_on)
    finally:
        globals()["capability_enabled"] = _orig_cap

    # P61 C16: keyword_offline builds the real report argv; params are validated at the builder.
    argv_k, err_k = _build_keyword_offline({"query": "dresser makeover"}, [], hub)
    ok("keyword_offline builds the report argv",
       err_k is None and argv_k[0].endswith("keyword_offline.py") and
       argv_k[1] == "report" and "--json" in argv_k)
    ok("keyword_offline refuses an empty query",
       _build_keyword_offline({}, [], hub)[1] is not None and
       _build_keyword_offline({"query": "  "}, [], hub)[1] is not None)
    ok("keyword_offline refuses an oversize query",
       _build_keyword_offline({"query": "x" * 501}, [], hub)[1] is not None)
    # and the built argv actually runs clean against the committed library (zero network).
    proc_k = subprocess.run([env_paths.app_python(str(ROOT))] + argv_k,
                            capture_output=True, text=True, timeout=120, cwd=str(ROOT))
    rep_k = json.loads(proc_k.stdout) if proc_k.returncode == 0 else {}
    ok("keyword_offline argv runs clean with the honesty envelope",
       proc_k.returncode == 0 and rep_k.get("search_volumes") is None and
       rep_k.get("data_basis", "").startswith("local keyword library"))

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
