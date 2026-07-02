#!/usr/bin/env python3
"""Handoff stress simulation: online (account Q&A / extraction) <-> offline (obligations math).

The deepest end-to-end test of the contract-obligations seam, runnable offline on any machine
with bare Python. Ten phases, 38 checks:

  A. Multi-deal extraction rows -> offline register build (3 fictional brands)
  B. Account Q&A answered FROM offline outputs (no model arithmetic)
  C. Trigger-based deadline ("net 30 from delivery") anchor round-trip
  D. Amendment mid-deal -> rebuild -> offline diff
  E. Machine-to-machine sync: manifest -> verify -> tamper -> verify must fail
  F. Flag toggles mid-workflow (write gated; scan always available)
  G. Time progression: same data at three 'today' anchors; bands must shift
  H. Real MCP-layer code paths (FastMCP stubbed; actual mcp_server functions called)
  I. Malformed / adversarial inputs
  J. Real-machine safety: your local files untouched, privacy invariant still holds

SANDBOX GUARANTEE. Phases that write (E, F, H) run against a throwaway temp directory, never
your real files: the tool sets CREATOR_OS_ROOT to the sandbox before loading the obligations
stack, so the config it flips and the register it writes live only there, and the sandbox is
deleted at the end. A preflight assertion REFUSES to run any write phase if the redirect did
not take. Phase J then proves it against reality: your real creator-os-config.local.json and
obligation-register.local.json (if they exist) are byte-identical to before the run, git tracks
no personal .local file, and the drift guard still passes. Everything is fictional fixture data;
no network; stdlib only.

CLI:
  python3 tools/handoff_sim.py [--json]
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import types
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OB = None  # the obligations module, imported AFTER the sandbox env is set

PASS, FAIL, SKIP = [], [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({detail})" if detail and not cond else ""))


def skip(name, why):
    SKIP.append(name)
    print(f"  [SKIP] {name} ({why})")


def _sha(p: Path):
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None


def _run_cli(args, env):
    return subprocess.run([sys.executable, str(REPO / "tools" / "obligations.py"), *args],
                          capture_output=True, text=True, cwd=str(REPO), env=env)


# --------------------------------------------------------------------------- fixtures (fictional)

ROWS_A = [
    {"required_action": "Deliver dedicated video to Hearthline", "obligated_party": "creator", "clause_family": "deliverables_and_revisions", "trigger": "signature", "timing_or_deadline": "2026-07-24", "evidence_text": "Creator delivers the video by 2026-07-24.", "confidence": "explicit", "document": "Hearthline MSA (fixture)", "section": "3.1"},
    {"required_action": "Publish Hearthline integration post", "obligated_party": "creator", "clause_family": "deliverables_and_revisions", "trigger": "delivery approval", "timing_or_deadline": "2026-09-07", "evidence_text": "Post goes live no later than 2026-09-07.", "confidence": "explicit", "document": "Hearthline MSA (fixture)", "section": "3.2"},
    {"required_action": "Invoice Hearthline (net 30 from delivery)", "obligated_party": "creator", "clause_family": "payment_terms_and_kill_fee", "trigger": "delivery", "timing_or_deadline": "net 30 from delivery", "evidence_text": "Payment due net 30 from delivery.", "confidence": "explicit", "document": "Hearthline MSA (fixture)", "section": "5"},
]
ROWS_B = [
    {"required_action": "Deliver Vintique shorts bundle", "obligated_party": "creator", "clause_family": "deliverables_and_revisions", "trigger": "signature", "timing_or_deadline": "2026-07-11", "evidence_text": "Three shorts due 2026-07-11.", "confidence": "explicit", "document": "Vintique SOW (fixture)", "section": "2"},
    {"required_action": "Send Vintique year-end usage report", "obligated_party": "creator", "clause_family": "usage_licensing_rights", "trigger": "calendar", "timing_or_deadline": "2026-12-25", "evidence_text": "Usage report due 2026-12-25.", "confidence": "explicit", "document": "Vintique SOW (fixture)", "section": "6"},
    {"required_action": "Vintique kill fee if cancelled", "obligated_party": "brand", "clause_family": "payment_terms_and_kill_fee", "trigger": "cancellation", "timing_or_deadline": None, "evidence_text": "25 percent kill fee applies on cancellation.", "confidence": "explicit", "document": "Vintique SOW (fixture)", "section": "5"},
]
ROWS_C_V1 = [
    {"required_action": "Deliver Fernway studio tour segment", "obligated_party": "creator", "clause_family": "deliverables_and_revisions", "trigger": "signature", "timing_or_deadline": "2026-08-14", "evidence_text": "Segment due 2026-08-14.", "confidence": "explicit", "document": "Fernway Agreement v1 (fixture)", "section": "2"},
]
ROWS_C_V2 = [
    {"required_action": "Deliver Fernway studio tour segment", "obligated_party": "creator", "clause_family": "deliverables_and_revisions", "trigger": "signature", "timing_or_deadline": "2026-09-05", "evidence_text": "Amendment 1: segment due date moved to 2026-09-05.", "confidence": "explicit", "document": "Fernway Amendment 1 (fixture)", "section": "1"},
]
TODAY = "2026-07-02"


def build(rows, today, lead=3):
    return OB.build_register(rows, OB._today(today), lead)


def scan(data, today, lead=3):
    return OB.scan(data, OB._today(today), lead)


def by_action(reg, needle):
    return next(o for o in reg["obligations"] if needle in (o["required_action"] or ""))


# --------------------------------------------------------------------------- main

def main(argv) -> int:
    ap = argparse.ArgumentParser(description="Offline handoff stress simulation (sandboxed).")
    ap.add_argument("--json", action="store_true", help="machine-readable summary")
    a = ap.parse_args(argv)

    global OB

    # Snapshot the REAL local files this sim must never touch (Phase J proves it).
    real_cfg_local = REPO / "creator-os-config.local.json"
    real_register = REPO / "pipeline" / "user-context" / "obligation-register.local.json"
    before = {p: _sha(p) for p in (real_cfg_local, real_register)}

    # Sandbox: every write goes here, never to the real repo.
    sandbox = Path(tempfile.mkdtemp(prefix="creator-os-sim-"))
    try:
        (sandbox / "pipeline" / "user-context").mkdir(parents=True)
        shutil.copy2(REPO / "creator-os-config.json", sandbox / "creator-os-config.json")
        os.environ["CREATOR_OS_ROOT"] = str(sandbox)
        env = dict(os.environ)

        sys.path.insert(0, str(REPO / "tools"))
        OB = importlib.import_module("obligations")

        # Preflight: REFUSE to run write phases unless the redirect took.
        redirected = str(OB.REGISTER_PATH).startswith(str(sandbox)) and str(OB.CONFIG_LOCAL_PATH).startswith(str(sandbox))
        if not redirected:
            print("ABORT: sandbox redirect failed; refusing to run write phases against real paths.")
            print(f"  REGISTER_PATH resolved to {OB.REGISTER_PATH}")
            return 2

        sandbox_cfg_local = sandbox / "creator-os-config.local.json"
        rows_file = sandbox / "merged-rows.json"
        merged = {"contract_ref": "multi", "deal_id": "portfolio", "obligations": ROWS_A + ROWS_B + ROWS_C_V1}
        rows_file.write_text(json.dumps(merged, indent=2), encoding="utf-8")

        print(f"sandbox: {sandbox} (all writes land here; removed at the end)")

        print("\n=== PHASE A: multi-deal extraction -> offline build (merged register) ===")
        regA = build(merged, TODAY)
        check("A1 seven rows in, seven obligations out", regA["obligation_count"] == 7)
        o = by_action(regA, "Deliver dedicated video")
        check("A2 Fri 2026-07-24 stays 07-24, send_by 07-21 (Tue)", o["effective_date"] == "2026-07-24" and o["send_by_date"] == "2026-07-21", f"got {o['effective_date']}/{o['send_by_date']}")
        o = by_action(regA, "Publish Hearthline")
        check("A3 Labor Day 09-07 rolls to 09-04 (Fri), send_by 09-04", o["effective_date"] == "2026-09-04" and o["send_by_date"] == "2026-09-04", f"got {o['effective_date']}/{o['send_by_date']}")
        o = by_action(regA, "shorts bundle")
        check("A4 Sat 07-11 rolls to 07-10, send_by 07-08 (Wed)", o["effective_date"] == "2026-07-10" and o["send_by_date"] == "2026-07-08", f"got {o['effective_date']}/{o['send_by_date']}")
        o = by_action(regA, "year-end usage")
        check("A5 Christmas Fri 12-25 rolls to 12-24 (Thu), send_by 12-22", o["effective_date"] == "2026-12-24" and o["send_by_date"] == "2026-12-22", f"got {o['effective_date']}/{o['send_by_date']}")
        o = by_action(regA, "net 30 from delivery")
        check("A6 phrase deadline -> null + gap (never inferred)", o["raw_date"] is None and o["gaps"], f"got {o['raw_date']}/{o['gaps']}")
        o = by_action(regA, "kill fee")
        check("A7 no-date duty -> unknown band + gap", o["urgency_band"] == "unknown" and o["gaps"])

        print("\n=== PHASE B: account Q&A answered from offline outputs ===")
        sc = scan(merged, TODAY)
        q1 = [x for x in sc["action_queue"] if x["urgency_band"] in ("red", "overdue")]
        check("B1 'what needs action in 14 days' = exactly the shorts bundle (red band = 0 to 13 days)",
              len(q1) == 1 and q1[0]["urgency_band"] == "red" and "shorts" in q1[0]["required_action"],
              f"got {[(x['required_action'], x['urgency_band']) for x in q1]}")
        check("B2 queue ordering: red items first, then orange/yellow, unknowns last",
              sc["action_queue"][0]["urgency_band"] == "red" and sc["action_queue"][-1]["urgency_band"] == "unknown")
        hearthline = [x for x in regA["obligations"] if "Hearthline" in (x["required_action"] or "")]
        check("B3 per-account filter (Hearthline) yields its 3 duties", len(hearthline) == 3)
        check("B4 'when do I invoice Hearthline' honestly answers 'unknown, anchor needed'",
              by_action(regA, "Invoice Hearthline")["send_by_date"] is None)

        print("\n=== PHASE C: trigger-based deadline round-trip (online supplies anchor; offline computes) ===")
        resolved = dict(ROWS_A[2]); resolved["anchor_date"] = "2026-07-24"; resolved["offset_days"] = 30
        regC = build({"obligations": [resolved]}, TODAY)
        oc = regC["obligations"][0]
        check("C1 anchor+offset computed OFFLINE: 07-24 + 30 = 08-23 (Sun) -> effective 08-21, send_by 08-20",
              oc["raw_date"] == "2026-08-23" and oc["effective_date"] == "2026-08-21" and oc["send_by_date"] == "2026-08-20",
              f"got raw={oc['raw_date']} eff={oc['effective_date']} send={oc['send_by_date']} gaps={oc['gaps']}")
        check("C2 provenance records the anchor derivation", oc["provenance"].get("derived_from", {}).get("offset_days") == 30)

        print("\n=== PHASE D: amendment arrives -> rebuild -> offline diff ===")
        reg_v1 = build({"obligations": ROWS_C_V1}, TODAY)
        reg_v2 = build({"obligations": ROWS_C_V2}, TODAY)
        d1, d2 = reg_v1["obligations"][0], reg_v2["obligations"][0]
        check("D1 v1: Fri 08-14 send_by 08-11 (Tue)", d1["send_by_date"] == "2026-08-11", f"got {d1['send_by_date']}")
        check("D2 v2 amendment: Sat 09-05 -> effective 09-04, send_by 09-02 (Wed)",
              d2["effective_date"] == "2026-09-04" and d2["send_by_date"] == "2026-09-02", f"got {d2['effective_date']}/{d2['send_by_date']}")
        check("D3 register diff detects the moved deadline (v1 vs v2)",
              d1["required_action"] == d2["required_action"] and d1["raw_date"] != d2["raw_date"])
        check("D4 band shifts with the amendment (orange -> yellow)",
              d1["urgency_band"] == "orange" and d2["urgency_band"] == "yellow", f"got {d1['urgency_band']}->{d2['urgency_band']}")

        print("\n=== PHASE E: machine-to-machine sync (manifest -> verify -> tamper) ===")
        sandbox_cfg_local.write_text(json.dumps({"capabilities": {"contract_obligations": True}}), encoding="utf-8")
        r = _run_cli(["--build", str(rows_file), "--today", TODAY, "--write"], env)
        check("E1 offline write succeeds with flag on (sandboxed)", "wrote" in r.stdout and OB.REGISTER_PATH.exists(), r.stdout[:120] + r.stderr[:120])
        man = sandbox / "bucket.manifest.json"
        _run_cli(["--write-manifest", str(man)], env)
        v = json.loads(_run_cli(["--verify", str(man)], env).stdout)
        check("E2 'online' side verifies the untouched register", v["ok"] is True)
        tampered = json.loads(OB.REGISTER_PATH.read_text(encoding="utf-8"))
        tampered["obligations"][0]["send_by_date"] = "2027-01-01"
        OB.REGISTER_PATH.write_text(json.dumps(tampered, indent=2), encoding="utf-8")
        v2 = json.loads(_run_cli(["--verify", str(man)], env).stdout)
        check("E3 tampered register FAILS verification (changed path reported)", v2["ok"] is False and v2["changed"])

        print("\n=== PHASE F: flag toggles mid-workflow ===")
        sandbox_cfg_local.unlink()
        r = _run_cli(["--build", str(rows_file), "--today", TODAY, "--write"], env)
        gate = json.loads(r.stdout)
        check("F1 flag off: write refused, register still computed + gate note", "_gate" in gate and gate["obligation_count"] == 7)
        r = _run_cli(["--scan", str(rows_file), "--today", TODAY], env)
        check("F2 flag off: read-only scan still fully available", json.loads(r.stdout)["band_counts"].get("red") == 1)

        print("\n=== PHASE G: time progression (same data, three 'today' anchors) ===")
        def band_of(today, needle):
            return by_action(build(merged, today), needle)["urgency_band"]
        check("G1 shorts bundle: red on 07-02 -> overdue on 08-25", band_of("2026-07-02", "shorts") == "red" and band_of("2026-08-25", "shorts") == "overdue")
        check("G2 Hearthline publish: yellow on 07-02 -> red on 08-25", band_of("2026-07-02", "Publish") == "yellow" and band_of("2026-08-25", "Publish") == "red")
        check("G3 year-end report: out_of_band on 07-02 -> red on 12-20", band_of("2026-07-02", "year-end") == "out_of_band" and band_of("2026-12-20", "year-end") == "red")

        print("\n=== PHASE H: real MCP-layer code paths (FastMCP stubbed) ===")
        fake_fast = types.ModuleType("mcp.server.fastmcp")
        class FastMCP:
            def __init__(self, *a, **k): pass
            def tool(self, *a, **k):
                def deco(f):
                    return f
                return deco
            def run(self, *a, **k): pass
        fake_fast.FastMCP = FastMCP
        fake_srv = types.ModuleType("mcp.server"); fake_srv.fastmcp = fake_fast
        fake_mcp = types.ModuleType("mcp"); fake_mcp.server = fake_srv
        sys.modules.update({"mcp": fake_mcp, "mcp.server": fake_srv, "mcp.server.fastmcp": fake_fast})
        ms = importlib.import_module("mcp_server")
        out = json.loads(ms.obligation_build({"obligations": ROWS_A}, today=TODAY))
        check("H1 MCP obligation_build returns computed register (no write by default)", out["obligation_count"] == 3 and "_written" not in out)
        out = json.loads(ms.obligation_build({"obligations": ROWS_A}, today=TODAY, write=True))
        check("H2 MCP write=True with flag off: gate note, nothing persisted", "_gate" in out)
        sandbox_cfg_local.write_text(json.dumps({"capabilities": {"contract_obligations": True}}), encoding="utf-8")
        out = json.loads(ms.obligation_build(merged, today=TODAY, write=True))
        check("H3 MCP write=True with flag on: persisted (sandboxed)", out.get("_written", "").endswith("obligation-register.local.json"))
        sc2 = json.loads(ms.obligation_scan(today=TODAY))
        check("H4 MCP obligation_scan reads stored register", len(sc2["action_queue"]) == 7)
        imp = json.loads(ms.import_obligations())
        check("H5 MCP import_obligations: 7 calendar deadlines + payment obligations isolated + human_review",
              len(imp["handoff"]["calendar_deadlines"]) == 7 and imp["human_review_required"] is True
              and any("Invoice" in (p["required_action"] or "") for p in imp["handoff"]["payment_obligations"]))

        print("\n=== PHASE I: malformed / adversarial inputs ===")
        regI = build({"obligations": [{"required_action": "ok", "timing_or_deadline": "2026-08-14"}, "garbage-string", 42, {"required_action": "bad date", "timing_or_deadline": "soonish"}]}, TODAY)
        check("I1 non-dict rows skipped; garbage date -> null + gap", regI["obligation_count"] == 2 and regI["obligations"][1]["raw_date"] is None and regI["obligations"][1]["gaps"])
        regE = build({"obligations": []}, TODAY)
        check("I2 empty rows -> empty register, no crash", regE["obligation_count"] == 0)
        r = _run_cli(["--scan", str(sandbox / "does-not-exist.json")], env)
        check("I3 missing file -> structured no_source error, exit 1", r.returncode == 1 and "no_source" in r.stdout)
        stale = json.loads(man.read_text(encoding="utf-8")); stale["resources"][0]["sha256"] = "0" * 64
        stale_p = sandbox / "stale.manifest.json"; stale_p.write_text(json.dumps(stale), encoding="utf-8")
        v3 = json.loads(_run_cli(["--verify", str(stale_p)], env).stdout)
        check("I4 stale/foreign manifest -> verify fails cleanly", v3["ok"] is False)

    finally:
        os.environ.pop("CREATOR_OS_ROOT", None)
        shutil.rmtree(sandbox, ignore_errors=True)

    print("\n=== PHASE J: real-machine safety (reality untouched; privacy still holds) ===")
    after = {p: _sha(p) for p in before}
    check("J1 your real local config and register are byte-identical (or still absent)", before == after,
          f"changed: {[str(p) for p in before if before[p] != after[p]]}")
    check("J2 sandbox removed (no lingering test data)", not sandbox.exists())
    clean_env = {k: v for k, v in os.environ.items() if k != "CREATOR_OS_ROOT"}
    try:
        ls = subprocess.run(["git", "ls-files"], capture_output=True, text=True, cwd=str(REPO), timeout=30)
        if ls.returncode == 0:
            check("J3 git tracks no personal .local file", ".local." not in ls.stdout)
        else:
            skip("J3 git tracks no personal .local file", "not a git checkout")
    except (OSError, subprocess.SubprocessError):
        skip("J3 git tracks no personal .local file", "git unavailable")
    guard = REPO / "tools" / "sync_check.py"
    if guard.exists():
        r = subprocess.run([sys.executable, str(guard)], capture_output=True, text=True, cwd=str(REPO), env=clean_env)
        check("J4 drift guard still exits 0 (all invariants)", r.returncode == 0, r.stdout[-200:])
    else:
        skip("J4 drift guard still exits 0", "sync_check.py not present")

    total = len(PASS) + len(FAIL)
    print(f"\n{'=' * 60}\nRESULT: {len(PASS)} passed, {len(FAIL)} failed, {len(SKIP)} skipped (of {total + len(SKIP)})")
    if FAIL:
        print("FAILED:"); [print("  -", f) for f in FAIL]
    if a.json:
        print(json.dumps({"passed": len(PASS), "failed": len(FAIL), "skipped": len(SKIP), "failures": FAIL}))
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
