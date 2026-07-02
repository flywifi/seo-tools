#!/usr/bin/env python3
"""Offline obligation date-math + register builder (P23 Phase 3).

This is the local compute lane: the deterministic arithmetic the LLM must NOT spend tokens on.
It takes obligation rows (produced by the obligation-extract atom) and computes, in pure Python,
each obligation's effective date, send-by date (with weekend and US-federal-holiday roll-backward),
and urgency band, then writes the obligation register. It also produces a scoop-style sha256 bucket
manifest so an offline machine's register can be verified before the online side trusts it (mirrors
tools/sync_editing.py). Register WRITES are gated behind the contract_obligations capability flag
(mirrors tools/videoedit_validate.py); the read-only --scan is always available.

Stdlib only. No network. Never invents a date: an obligation with no parseable deadline gets null
dates and a flag (protocols/no-fabrication.md). This tool does arithmetic and organization only; it
is not legal advice.

CLI:
  python3 tools/obligations.py --build rows.json [--today YYYY-MM-DD] [--lead-days N] [--write]
  python3 tools/obligations.py --scan [rows.json | register.local.json] [--today YYYY-MM-DD]
  python3 tools/obligations.py --status
  python3 tools/obligations.py --manifest [--write-manifest FILE]
  python3 tools/obligations.py --verify obligations-bucket.manifest.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path

# CREATOR_OS_ROOT redirects every path this tool touches (config, register) to another root.
# Same pattern as tools/mcp_server.py. Used by tools/handoff_sim.py to sandbox its write phases;
# leave it unset for normal runs.
ROOT = Path(os.environ.get("CREATOR_OS_ROOT", str(Path(__file__).resolve().parent.parent)))
CONFIG_PATH = ROOT / "creator-os-config.json"
CONFIG_LOCAL_PATH = ROOT / "creator-os-config.local.json"
REGISTER_PATH = ROOT / "pipeline" / "user-context" / "obligation-register.local.json"

DEFAULT_LEAD_DAYS = 3  # default days before a due date the creator should act (send-by lead)


# --------------------------------------------------------------------------- config / flag gate

def load_config() -> dict:
    """Object-form flag in committed config, bare-bool override in gitignored .local (repo pattern)."""
    base: dict = {}
    try:
        base = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        pass
    if CONFIG_LOCAL_PATH.exists():
        try:
            local = json.loads(CONFIG_LOCAL_PATH.read_text(encoding="utf-8"))
            for k, v in local.get("capabilities", {}).items():
                base.setdefault("capabilities", {})[k] = v
        except (OSError, json.JSONDecodeError):
            pass
    return base


def flag_enabled(config: dict, name: str) -> bool:
    caps = config.get("capabilities", {}) if isinstance(config, dict) else {}
    meta = caps.get(name)
    if isinstance(meta, dict):
        return bool(meta.get("enabled", False))
    return bool(meta)


# --------------------------------------------------------------------------- US federal holidays

def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    """The nth (1-based) `weekday` (Mon=0) of `month`."""
    d = date(year, month, 1)
    offset = (weekday - d.weekday()) % 7
    return d + timedelta(days=offset + 7 * (n - 1))


def _last_weekday(year: int, month: int, weekday: int) -> date:
    """The last `weekday` (Mon=0) of `month`."""
    if month == 12:
        d = date(year, 12, 31)
    else:
        d = date(year, month + 1, 1) - timedelta(days=1)
    return d - timedelta(days=(d.weekday() - weekday) % 7)


def us_federal_holidays(year: int) -> set[date]:
    """Deterministic US federal holidays for a year, including weekend-observed dates.

    Both the actual date and its observed date are returned so a deadline landing on either rolls
    backward. No external dependency.
    """
    fixed = [
        date(year, 1, 1),    # New Year's Day
        date(year, 6, 19),   # Juneteenth
        date(year, 7, 4),    # Independence Day
        date(year, 11, 11),  # Veterans Day
        date(year, 12, 25),  # Christmas Day
    ]
    floating = [
        _nth_weekday(year, 1, 0, 3),    # MLK Day: 3rd Monday Jan
        _nth_weekday(year, 2, 0, 3),    # Presidents' Day: 3rd Monday Feb
        _last_weekday(year, 5, 0),      # Memorial Day: last Monday May
        _nth_weekday(year, 9, 0, 1),    # Labor Day: 1st Monday Sep
        _nth_weekday(year, 10, 0, 2),   # Columbus / Indigenous Peoples' Day: 2nd Monday Oct
        _nth_weekday(year, 11, 3, 4),   # Thanksgiving: 4th Thursday Nov
    ]
    out: set[date] = set(floating)
    for h in fixed:
        out.add(h)
        if h.weekday() == 5:        # Saturday -> observed Friday
            out.add(h - timedelta(days=1))
        elif h.weekday() == 6:      # Sunday -> observed Monday
            out.add(h + timedelta(days=1))
    return out


_HOLIDAY_CACHE: dict[int, set[date]] = {}


def _holidays_for(d: date) -> set[date]:
    if d.year not in _HOLIDAY_CACHE:
        _HOLIDAY_CACHE[d.year] = us_federal_holidays(d.year)
    return _HOLIDAY_CACHE[d.year]


def is_business_day(d: date) -> bool:
    return d.weekday() < 5 and d not in _holidays_for(d)


def roll_backward(d: date) -> date:
    """Move a date earlier to the prior business day if it lands on a weekend or US holiday."""
    while not is_business_day(d):
        d -= timedelta(days=1)
    return d


# --------------------------------------------------------------------------- date parsing / bands

def _parse_date(value) -> date | None:
    if not value or not isinstance(value, str):
        return None
    text = value.strip()[:10]
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def urgency_band(action_date: date | None, today: date) -> str:
    """red 0 to 13, orange 14 to 44, yellow 45 to 89, out_of_band beyond 89, overdue if past."""
    if action_date is None:
        return "unknown"
    days = (action_date - today).days
    if days < 0:
        return "overdue"
    if days <= 13:
        return "red"
    if days <= 44:
        return "orange"
    if days <= 89:
        return "yellow"
    return "out_of_band"


# --------------------------------------------------------------------------- register build / scan

def _rows_from_input(data) -> tuple[list, str | None, str | None]:
    """Accept a bare list of rows, or an object with obligations/rows plus contract_ref/deal_id."""
    if isinstance(data, list):
        return data, None, None
    if isinstance(data, dict):
        rows = data.get("obligations") or data.get("rows") or []
        return rows, data.get("contract_ref"), data.get("deal_id")
    return [], None, None


def compute(rows: list, today: date, lead_days: int) -> list:
    """Compute the dated register rows. Never invents a date; null-and-flag when absent.

    Relative deadlines round-trip through the anchor fields: when a contract states a
    relative timing (for example "net 30 from delivery") the online side resolves the
    anchor from the deal record and passes `anchor_date` (ISO) + `offset_days` (int) on
    the row; the date arithmetic (anchor + offset, then roll-back and banding) happens
    HERE, offline, never in the model. Without a resolvable date or anchor pair, the
    row stays null and flagged.
    """
    computed = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        raw = _parse_date(row.get("timing_or_deadline"))
        derived_from = None
        if raw is None:
            anchor = _parse_date(row.get("anchor_date"))
            offset = row.get("offset_days")
            if anchor is not None and isinstance(offset, int) and not isinstance(offset, bool):
                raw = anchor + timedelta(days=offset)
                derived_from = {"anchor_date": anchor.isoformat(), "offset_days": offset,
                                "stated_as": row.get("timing_or_deadline")}
        gaps = []
        if raw is None:
            effective = send_by = None
            band = "unknown"
            if row.get("timing_or_deadline"):
                gaps.append("timing_or_deadline is not an ISO date and no anchor_date/offset_days "
                            "pair was supplied; left null, not inferred")
            else:
                gaps.append("no timing_or_deadline in the source row; deadline null")
        else:
            effective = roll_backward(raw)
            send_by = roll_backward(raw - timedelta(days=lead_days))
            band = urgency_band(send_by, today)
        computed.append({
            "required_action": row.get("required_action"),
            "obligated_party": row.get("obligated_party"),
            "clause_family": row.get("clause_family"),
            "trigger": row.get("trigger"),
            "raw_date": raw.isoformat() if raw else None,
            "effective_date": effective.isoformat() if effective else None,
            "send_by_date": send_by.isoformat() if send_by else None,
            "urgency_band": band,
            "consequence_if_stated": row.get("consequence_if_stated"),
            "evidence_text": row.get("evidence_text"),
            "confidence": row.get("confidence"),
            "provenance": {
                "source_row": {k: row.get(k) for k in ("document", "section", "obligation_type")},
                "lead_days": lead_days,
                "computed_by": "tools/obligations.py",
                **({"derived_from": derived_from} if derived_from else {}),
            },
            "gaps": gaps,
        })
    return computed


def build_register(data, today: date, lead_days: int) -> dict:
    rows, contract_ref, deal_id = _rows_from_input(data)
    obligations = compute(rows, today, lead_days)
    band_counts: dict[str, int] = {}
    for o in obligations:
        band_counts[o["urgency_band"]] = band_counts.get(o["urgency_band"], 0) + 1
    return {
        "_boundary": "RESEARCH NOTES. NOT LEGAL ADVICE. REVIEW WITH A LICENSED ATTORNEY IN YOUR JURISDICTION BEFORE ACTING.",
        "schema_version": "0.1.0",
        "contract_ref": contract_ref,
        "deal_id": deal_id,
        "computed_as_of": today.isoformat(),
        "lead_days": lead_days,
        "obligation_count": len(obligations),
        "band_counts": band_counts,
        "obligations": obligations,
        "human_review_required": True,
        "generated_by": "tools/obligations.py",
        "last_computed": today.isoformat(),
    }


def scan(data, today: date, lead_days: int) -> dict:
    """Read-only deadline scan: what to act on, sorted by urgency. Never writes."""
    reg = data if (isinstance(data, dict) and "obligations" in data and "band_counts" in data) \
        else build_register(data, today, lead_days)
    order = {"overdue": 0, "red": 1, "orange": 2, "yellow": 3, "out_of_band": 4, "unknown": 5}
    items = sorted(
        reg["obligations"],
        key=lambda o: (order.get(o["urgency_band"], 9), o.get("send_by_date") or "9999-12-31"),
    )
    return {
        "_boundary": reg.get("_boundary"),
        "computed_as_of": reg.get("computed_as_of", today.isoformat()),
        "band_counts": reg.get("band_counts", {}),
        "action_queue": [
            {
                "required_action": o["required_action"],
                "send_by_date": o["send_by_date"],
                "effective_date": o["effective_date"],
                "urgency_band": o["urgency_band"],
                "gaps": o["gaps"],
            }
            for o in items
        ],
        "note": "Read-only scan. Deterministic date math from tools/obligations.py; no tokens, no writes.",
    }


# --------------------------------------------------------------------------- scoop bucket manifest

def _sha256_file(p: Path) -> tuple[str, int]:
    data = p.read_bytes()
    return hashlib.sha256(data).hexdigest(), len(data)


def manifest() -> dict:
    resources = []
    if REGISTER_PATH.exists():
        digest, size = _sha256_file(REGISTER_PATH)
        resources.append({
            "path": REGISTER_PATH.relative_to(ROOT).as_posix(),
            "kind": "obligation_register",
            "sha256": digest,
            "bytes": size,
        })
    return {
        "name": "creator-os-obligations-bucket",
        "version": "0.1.0",
        "resource_count": len(resources),
        "resources": resources,
        "note": "Scoop-style obligation-register manifest. Portable and hash-verified; re-verify offline before trusting a synced copy.",
    }


def verify(manifest_path: str) -> dict:
    m = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    current = {r["path"]: r["sha256"] for r in manifest()["resources"]}
    ok, changed, missing = [], [], []
    for r in m.get("resources", []):
        cur = current.get(r["path"])
        if cur is None:
            missing.append(r["path"])
        elif cur == r["sha256"]:
            ok.append(r["path"])
        else:
            changed.append(r["path"])
    return {"ok": not changed and not missing, "verified": ok, "changed": changed, "missing": missing}


# --------------------------------------------------------------------------- selftest

def selftest() -> int:
    """Deterministic self-test of the date-math invariants. Offline, no writes, no deps.

    Run any time with: python3 tools/obligations.py --selftest
    """
    t = date(2026, 7, 2)
    failures = []

    def expect(name, cond):
        if not cond:
            failures.append(name)
        print(f"  [{'ok' if cond else 'FAIL'}] {name}")

    # roll-back: plain weekend, holiday, and holiday-chain (Jul 4 2026 is a Saturday;
    # Jul 3 is the observed holiday, so Sat 7/4 must roll all the way to Thu 7/2)
    expect("Saturday rolls to Friday", roll_backward(date(2026, 7, 11)) == date(2026, 7, 10))
    expect("Jul 4 (Sat) chains past observed Fri to Thu", roll_backward(date(2026, 7, 4)) == date(2026, 7, 2))
    expect("Labor Day Monday rolls to prior Friday", roll_backward(date(2026, 9, 7)) == date(2026, 9, 4))
    expect("Christmas (Fri) rolls to Thursday", roll_backward(date(2026, 12, 25)) == date(2026, 12, 24))
    expect("business day unchanged", roll_backward(date(2026, 8, 14)) == date(2026, 8, 14))

    # urgency bands (half-open: red 0 to 13, orange 14 to 44, yellow 45 to 89)
    expect("band red at 0 and 13", urgency_band(t, t) == "red" and urgency_band(t + timedelta(days=13), t) == "red")
    expect("band orange at 14 and 44", urgency_band(t + timedelta(days=14), t) == "orange" and urgency_band(t + timedelta(days=44), t) == "orange")
    expect("band yellow at 45 and 89", urgency_band(t + timedelta(days=45), t) == "yellow" and urgency_band(t + timedelta(days=89), t) == "yellow")
    expect("band out_of_band at 90", urgency_band(t + timedelta(days=90), t) == "out_of_band")
    expect("band overdue in the past", urgency_band(t - timedelta(days=1), t) == "overdue")
    expect("band unknown when dateless", urgency_band(None, t) == "unknown")

    # anchor round-trip: net 30 from a 2026-07-24 delivery = 08-23 (Sun) -> eff 08-21, send-by 08-20
    rows = [{"required_action": "invoice", "timing_or_deadline": "net 30 from delivery",
             "anchor_date": "2026-07-24", "offset_days": 30}]
    o = compute(rows, t, 3)[0]
    expect("anchor+offset derives 2026-08-23", o["raw_date"] == "2026-08-23")
    expect("derived date rolls Sunday to Friday", o["effective_date"] == "2026-08-21" and o["send_by_date"] == "2026-08-20")
    expect("derivation recorded in provenance", o["provenance"].get("derived_from", {}).get("offset_days") == 30)

    # null-and-flag discipline
    o = compute([{"required_action": "vague", "timing_or_deadline": "soonish"}], t, 3)[0]
    expect("unparseable date stays null + flagged", o["raw_date"] is None and o["gaps"])
    o = compute([{"required_action": "bool trap", "timing_or_deadline": None,
                  "anchor_date": "2026-07-24", "offset_days": True}], t, 3)[0]
    expect("boolean offset_days rejected (no sneaky True==1)", o["raw_date"] is None)
    expect("non-dict rows skipped", len(compute(["junk", 42], t, 3)) == 0)

    print(f"selftest: {'PASS' if not failures else 'FAIL'} "
          f"({15 - len(failures)} of 15 checks)")
    return 1 if failures else 0


# --------------------------------------------------------------------------- CLI

def _today(arg: str | None) -> date:
    d = _parse_date(arg) if arg else None
    return d or date.today()


def _load_json(path: str):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main(argv) -> int:
    ap = argparse.ArgumentParser(description="Offline obligation date-math + register builder.")
    ap.add_argument("--build", metavar="ROWS_JSON", help="obligation rows to compute into a register")
    ap.add_argument("--scan", nargs="?", const="__register__", metavar="ROWS_OR_REGISTER",
                    help="read-only deadline scan (defaults to the stored register)")
    ap.add_argument("--status", action="store_true", help="summarize the stored register")
    ap.add_argument("--manifest", action="store_true", help="print the sha256 bucket manifest")
    ap.add_argument("--write-manifest", metavar="FILE", help="write the manifest to FILE")
    ap.add_argument("--verify", metavar="MANIFEST", help="verify the register against a manifest")
    ap.add_argument("--today", metavar="YYYY-MM-DD", help="anchor date for urgency bands (reproducible)")
    ap.add_argument("--lead-days", type=int, default=DEFAULT_LEAD_DAYS, help="send-by lead in days")
    ap.add_argument("--write", action="store_true", help="write the register (gated by contract_obligations)")
    ap.add_argument("--selftest", action="store_true", help="run the deterministic date-math self-test")
    a = ap.parse_args(argv)
    today = _today(a.today)

    if a.selftest:
        return selftest()
    if a.verify:
        print(json.dumps(verify(a.verify), indent=2))
        return 0
    if a.manifest or a.write_manifest:
        m = manifest()
        if a.write_manifest:
            Path(a.write_manifest).write_text(json.dumps(m, indent=2) + "\n", encoding="utf-8")
            print(f"wrote {a.write_manifest} ({m['resource_count']} resource(s))")
        else:
            print(json.dumps(m, indent=2))
        return 0
    if a.scan:
        src = REGISTER_PATH if a.scan == "__register__" else Path(a.scan)
        if not src.exists():
            print(json.dumps({"error": "no_source",
                              "message": f"{src} not found; pass a rows file or build the register first"}))
            return 1
        print(json.dumps(scan(_load_json(str(src)), today, a.lead_days), indent=2, ensure_ascii=False))
        return 0
    if a.build:
        reg = build_register(_load_json(a.build), today, a.lead_days)
        cfg = load_config()
        if a.write:
            if not flag_enabled(cfg, "contract_obligations"):
                reg_out = dict(reg)
                reg_out["_gate"] = ("contract_obligations is off: register computed but NOT written. "
                                    "Enable contract_obligations to persist it (see degraded_behavior).")
                print(json.dumps(reg_out, indent=2, ensure_ascii=False))
                return 0
            REGISTER_PATH.parent.mkdir(parents=True, exist_ok=True)
            REGISTER_PATH.write_text(json.dumps(reg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            print(f"wrote {REGISTER_PATH.relative_to(ROOT).as_posix()} ({reg['obligation_count']} obligation(s))")
            return 0
        print(json.dumps(reg, indent=2, ensure_ascii=False))
        return 0
    if a.status:
        if not REGISTER_PATH.exists():
            print("no obligation register yet (pipeline/user-context/obligation-register.local.json)")
            return 0
        reg = _load_json(str(REGISTER_PATH))
        print(f"obligation register: {reg.get('obligation_count', 0)} obligation(s), "
              f"as of {reg.get('computed_as_of')}, bands {reg.get('band_counts')}")
        return 0
    ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
