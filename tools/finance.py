#!/usr/bin/env python3
"""Creator OS finance: offline, deterministic, zero-token money math.

The second instance of the offline compute lane (docs/LOCAL_CONTEXT.md), shaped like
tools/obligations.py and importing its date machinery (holidays, business-day roll-back,
urgency bands) rather than duplicating it. Everything here is arithmetic the model must never
do by hand: accounts-receivable aging, invoice assembly, due-date derivation from structured
net terms, late-penalty accrual, revenue-share and commission payouts, cost rollups, and
proposal price floors. All money is decimal.Decimal, ROUND_HALF_UP, quantized to cents once at
the end of each computation; every computed result carries computed_by. Numbers come only from
records and explicit inputs; a missing figure is null plus a gaps[] entry, never a guess
(protocols/no-fabrication.md, shared/finance-engine.md).

Contractual due dates are NOT rolled over weekends or holidays (the contract says what it
says); only derived ACTION dates (chase reminders) roll backward, via obligations.roll_backward.

Read-only commands (--ar-scan, --accrue, --revshare, --rollup, --price, --status) are always
available. Record writes are gated: --build-invoice --write requires the finance_management AND
invoice_generation flags. Real records live in pipeline/finance/*.local.json (gitignored);
CREATOR_OS_ROOT redirects all paths for sandboxed runs, exactly like obligations.py.

Usage:
  python3 tools/finance.py --ar-scan [INVOICES_JSON] [--today YYYY-MM-DD]
  python3 tools/finance.py --build-invoice PAYLOAD_JSON [--write] [--today YYYY-MM-DD]
  python3 tools/finance.py --accrue INVOICE_JSON [--today YYYY-MM-DD]
  python3 tools/finance.py --revshare PAYLOAD_JSON
  python3 tools/finance.py --rollup ESTIMATE_JSON
  python3 tools/finance.py --price PAYLOAD_JSON
  python3 tools/finance.py --status | --manifest | --write-manifest FILE | --verify FILE
  python3 tools/finance.py --selftest
"""
import argparse
import hashlib
import json
import os
import sys
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import obligations as _ob  # noqa: E402

ROOT = Path(os.environ.get("CREATOR_OS_ROOT", str(Path(__file__).resolve().parent.parent)))
FINANCE_DIR = ROOT / "pipeline" / "finance"
CENT = Decimal("0.01")
TOOL = "tools/finance.py"


# ── money primitives ─────────────────────────────────────────────────────────

def dec(x):
    """Parse a number into an exact Decimal without premature rounding. None stays None."""
    if x is None:
        return None
    return Decimal(str(x))


def money(x):
    """Final quantization: cents, ROUND_HALF_UP. Applied once at the end of a computation."""
    if x is None:
        return None
    return Decimal(str(x)).quantize(CENT, rounding=ROUND_HALF_UP)


def _mstr(x):
    """Serialize a money value exactly (string, two decimals) or None."""
    m = money(x)
    return None if m is None else str(m)


def _parse_date(s):
    if s is None:
        return None
    if isinstance(s, date):
        return s
    return date.fromisoformat(str(s))


def add_months(d, months):
    """Calendar-month stepping with end-of-month clamping (Jan 31 + 1 month = Feb 28/29)."""
    y = d.year + (d.month - 1 + months) // 12
    m = (d.month - 1 + months) % 12 + 1
    # clamp day to the target month's length
    for day in (d.day, 30, 29, 28):
        try:
            return date(y, m, day)
        except ValueError:
            continue
    raise ValueError(f"cannot step {d} by {months} months")


# ── due dates and aging ──────────────────────────────────────────────────────

def derive_due_date(anchor_date, net_days):
    """Contractual due date = anchor + net_days. NOT rolled: the contract's date stands.
    Chase/action dates derived from it roll backward separately (see ar_scan)."""
    return _parse_date(anchor_date) + timedelta(days=int(net_days))


def aging_bucket(due_date, today):
    """Accounting buckets from days past due. Edges inclusive on the left: day 31 is 31_to_60."""
    due = _parse_date(due_date)
    dpd = (today - due).days
    if dpd <= 0:
        return "current"
    if dpd <= 30:
        return "1_to_30"
    if dpd <= 60:
        return "31_to_60"
    if dpd <= 90:
        return "61_to_90"
    return "over_90"


def accrue_late_penalty(amount, late_penalty, due_date, today):
    """Penalty accrued so far under structured terms, or an honest zero/flag.

    flat: rate (an amount) added once, when today is past due_date + grace_days.
    percent_per_month: rate percent of the outstanding amount per FULL elapsed month past
    (due_date + grace_days); months advance on the day-of-month anniversary, no proration.
    Any structure these cannot express stays unaccrued and flagged; never approximated.
    """
    out = {"amount": None, "as_of": today.isoformat(),
           "computed_by": f"{TOOL} accrue_late_penalty", "detail": None, "gaps": []}
    lp = late_penalty or {}
    ptype = lp.get("type")
    if ptype in (None, "none"):
        out["amount"] = _mstr(0)
        out["detail"] = "no late penalty in terms"
        return out
    if amount is None or due_date is None:
        out["gaps"].append({"gap_type": "missing_input",
                            "description": "penalty needs the outstanding amount and due date",
                            "impact": "penalty not computed",
                            "recommended_next_step": "provide amount and payment_due_date"})
        return out
    rate = dec(lp.get("rate"))
    if rate is None:
        out["gaps"].append({"gap_type": "missing_rate",
                            "description": f"late_penalty.type is {ptype} but rate is null",
                            "impact": "penalty not computed",
                            "recommended_next_step": "normalize the rate from quoted contract text"})
        return out
    grace = int(lp.get("grace_days") or 0)
    start = _parse_date(due_date) + timedelta(days=grace)
    if today <= start:
        out["amount"] = _mstr(0)
        out["detail"] = f"within due date plus {grace} grace days"
        return out
    if ptype == "flat":
        out["amount"] = _mstr(rate)
        out["detail"] = "flat penalty, applied once past the grace period"
        return out
    if ptype == "percent_per_month":
        months = 0
        while add_months(start, months + 1) <= today:
            months += 1
        out["amount"] = _mstr(dec(amount) * rate / Decimal(100) * months)
        out["detail"] = (f"{rate} percent per full elapsed month past grace; "
                         f"{months} full month(s) elapsed, no proration")
        return out
    out["gaps"].append({"gap_type": "unsupported_penalty_type",
                        "description": f"late_penalty.type '{ptype}' is not a supported structure",
                        "impact": "penalty not computed; handle manually",
                        "recommended_next_step": "flat and percent_per_month are supported"})
    return out


# ── revenue share, commission ────────────────────────────────────────────────

def _clamp_payout(raw, floor, cap):
    bound = "none"
    payout = raw
    if floor is not None and payout < dec(floor):
        payout, bound = dec(floor), "floor"
    if cap is not None and payout > dec(cap):
        payout, bound = dec(cap), "cap"
    return payout, bound


def revenue_share(basis_amount, percent, floor=None, cap=None):
    """Payout from a REPORTED basis figure only (the system never estimates the basis)."""
    if basis_amount is None or percent is None:
        return {"payout": None, "computed_by": f"{TOOL} revenue_share",
                "gaps": [{"gap_type": "missing_input",
                          "description": "revenue share needs a reported basis amount and a percent",
                          "impact": "payout not computed",
                          "recommended_next_step": "provide the basis figure from the source_of_truth report"}]}
    raw = dec(basis_amount) * dec(percent) / Decimal(100)
    payout, bound = _clamp_payout(raw, floor, cap)
    return {"payout": _mstr(payout), "raw": _mstr(raw), "bound_applied": bound,
            "basis_amount": _mstr(basis_amount), "percent": str(dec(percent)),
            "computed_by": f"{TOOL} revenue_share", "gaps": []}


def commission_split(basis_amount, structure):
    """Commission payout: structure {rate_percent, floor, cap}. Same clamp math, same rules."""
    s = structure or {}
    r = revenue_share(basis_amount, s.get("rate_percent"), s.get("floor"), s.get("cap"))
    r["computed_by"] = f"{TOOL} commission_split"
    return r


# ── costs and pricing ────────────────────────────────────────────────────────

def cost_rollup(line_items, time=None):
    """Totals from cost-estimate line items plus optional time cost. Null amounts become gaps."""
    by_category = {}
    expense = Decimal(0)
    capex = Decimal(0)
    gaps = []
    for i, li in enumerate(line_items or []):
        amount = dec(li.get("amount"))
        if amount is None:
            qty, unit = dec(li.get("quantity")), dec(li.get("unit_cost"))
            amount = qty * unit if (qty is not None and unit is not None) else None
        if amount is None:
            gaps.append({"gap_type": "missing_amount",
                         "description": f"line {i} ({li.get('description', '')!r}) has no amount or unit_cost",
                         "impact": "excluded from totals",
                         "recommended_next_step": "provide a quote, cost-library entry, or labeled assumption"})
            continue
        cat = li.get("category") or "uncategorized"
        by_category[cat] = by_category.get(cat, Decimal(0)) + amount
        if li.get("is_capex"):
            capex += amount
        else:
            expense += amount
    time_cost = None
    t = time or {}
    hours, rate = dec(t.get("total_hours")), dec(t.get("hourly_rate"))
    if hours is not None and rate is not None:
        time_cost = hours * rate
    elif t:
        gaps.append({"gap_type": "missing_time_inputs",
                     "description": "time cost needs total_hours and hourly_rate",
                     "impact": "time cost excluded from the grand total",
                     "recommended_next_step": "supply hours and the rate card's effective_hourly or a labeled assumption"})
    grand = expense + capex + (time_cost or Decimal(0))
    return {"by_category": {k: _mstr(v) for k, v in sorted(by_category.items())},
            "totals": {"expense": _mstr(expense), "capex": _mstr(capex),
                       "time_cost": _mstr(time_cost), "grand": _mstr(grand)},
            "computed_by": f"{TOOL} cost_rollup", "gaps": gaps}


def proposal_price(cost_total, margin_percent, rate_floor=None, benchmark_range=None):
    """Price floor = max(cost floor, negotiation floor). Decision support, never the quote."""
    if cost_total is None or margin_percent is None:
        return {"price_floor": None, "computed_by": f"{TOOL} proposal_price",
                "gaps": [{"gap_type": "missing_input",
                          "description": "needs cost_total and margin_percent",
                          "impact": "no price floor computed",
                          "recommended_next_step": "run cost_rollup first and state a margin"}]}
    cost_floor = dec(cost_total) * (Decimal(100) + dec(margin_percent)) / Decimal(100)
    floors = {"cost_floor": cost_floor}
    if rate_floor is not None:
        floors["negotiation_floor"] = dec(rate_floor)
    bound = max(floors, key=lambda k: floors[k])
    price = floors[bound]
    flags = []
    br = benchmark_range or {}
    if br.get("high") is not None and price > dec(br["high"]):
        flags.append("price floor exceeds the benchmark range high; expect pushback or justify scope")
    if br.get("low") is not None and price < dec(br["low"]):
        flags.append("price floor is below the benchmark range low; the market may bear more")
    return {"price_floor": _mstr(price), "bound": bound,
            "cost_floor": _mstr(cost_floor),
            "negotiation_floor": _mstr(rate_floor),
            "benchmark_range": {k: _mstr(v) for k, v in br.items()} if br else None,
            "flags": flags, "computed_by": f"{TOOL} proposal_price", "gaps": []}


# ── invoice assembly ─────────────────────────────────────────────────────────

def build_invoice(payload, today):
    """Assemble a standalone invoice record. Numbers only from the payload; nulls become gaps.
    payload: {deal_id, brand_name, account_ref, contract_ref, seq, line_items[],
              adjustments[], terms (payment_terms_structured), anchor_date, invoice_date}."""
    gaps = []
    deal_id = payload.get("deal_id") or ""
    seq = int(payload.get("seq") or 1)
    subtotal = Decimal(0)
    items_out = []
    for i, li in enumerate(payload.get("line_items") or []):
        qty = dec(li.get("quantity") if li.get("quantity") is not None else 1)
        unit = dec(li.get("unit_price"))
        amount = dec(li.get("amount"))
        if amount is None and unit is not None:
            amount = qty * unit
        if amount is None:
            gaps.append({"gap_type": "missing_amount",
                         "description": f"line {i} ({li.get('description', '')!r}) has no amount or unit_price",
                         "impact": "excluded from the subtotal; invoice incomplete",
                         "recommended_next_step": "fill the figure from the deal record; never estimate"})
        else:
            subtotal += amount
        items_out.append({"description": li.get("description", ""),
                          "quantity": float(qty) if qty is not None else None,
                          "unit_price": _mstr(unit), "amount": _mstr(amount),
                          "deliverable_ref": li.get("deliverable_ref")})
    adjustments = []
    total = subtotal
    for adj in payload.get("adjustments") or []:
        a = dec(adj.get("amount"))
        if a is None:
            gaps.append({"gap_type": "missing_amount",
                         "description": f"adjustment ({adj.get('description', '')!r}) has no amount",
                         "impact": "excluded from the total",
                         "recommended_next_step": "state the adjustment amount"})
            continue
        total += a
        adjustments.append({"description": adj.get("description", ""), "amount": _mstr(a)})

    terms = payload.get("terms") or {}
    invoice_date = _parse_date(payload.get("invoice_date")) or today
    due = None
    net_days = terms.get("net_days")
    anchor = terms.get("anchor")
    anchor_date = payload.get("anchor_date")
    if net_days is not None:
        base = _parse_date(anchor_date) if anchor and anchor != "invoice_date" else None
        if anchor == "invoice_date" or (anchor is None and anchor_date is None):
            base = invoice_date
        if base is None:
            gaps.append({"gap_type": "missing_anchor_date",
                         "description": f"terms anchor is {anchor!r} but no anchor_date was provided",
                         "impact": "payment_due_date not derived",
                         "recommended_next_step": "supply the anchor event's date from the deal record"})
        else:
            due = derive_due_date(base, net_days)
    else:
        gaps.append({"gap_type": "missing_terms",
                     "description": "no structured net_days on the terms",
                     "impact": "payment_due_date not derived",
                     "recommended_next_step": "normalize payment terms per shared/finance-engine.md"})

    return {
        "_boundary": ("ARITHMETIC AND RESEARCH NOTES. NOT TAX, ACCOUNTING, OR INVESTMENT "
                      "ADVICE. REVIEW WITH A CPA OR TAX PROFESSIONAL BEFORE FILING OR RELYING "
                      "ON CATEGORIZATIONS."),
        "invoice_id": f"INV-{deal_id}-{seq:03d}",
        "deal_id": deal_id,
        "account_ref": payload.get("account_ref"),
        "brand_name": payload.get("brand_name"),
        "contract_ref": payload.get("contract_ref"),
        "status": "draft",
        "currency": "USD",
        "line_items": items_out,
        "subtotal": _mstr(subtotal),
        "adjustments": adjustments,
        "total": _mstr(total),
        "invoice_date": invoice_date.isoformat(),
        "terms_snapshot": terms,
        "payment_due_date": due.isoformat() if due else None,
        "payment_received_date": None,
        "payment_method": None,
        "accrued_penalty": {"amount": None, "as_of": None, "computed_by": None},
        "human_review_required": True,
        "gaps": gaps,
        "provenance": {"generated_by": TOOL, "computed_by": f"{TOOL} build_invoice"},
        "notes": "",
    }


def _write_allowed(config):
    """Invoice writes need finance_management AND invoice_generation. Returns (ok, reason)."""
    if not _ob.flag_enabled(config, "finance_management"):
        return False, ("finance_management is off; the invoice was computed but not written "
                       "(see degraded_behavior.finance_management_disabled)")
    if not _ob.flag_enabled(config, "invoice_generation"):
        return False, ("invoice_generation is off; the invoice was computed but not written "
                       "(see degraded_behavior.invoice_generation_disabled)")
    return True, "ok"


# ── accounts receivable ──────────────────────────────────────────────────────

def _load_local_invoices():
    invoices = []
    if FINANCE_DIR.exists():
        for f in sorted(FINANCE_DIR.glob("INV-*.local.json")):
            try:
                invoices.append(json.loads(f.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError):
                continue
    return invoices


def ar_scan(invoices=None, today=None):
    """Read-only accounts-receivable view. Always available, never writes.
    Buckets by days past due; disputed invoices are excluded from penalty accrual and listed
    separately; paid invoices are excluded from outstanding totals."""
    today = today or date.today()
    if invoices is None:
        invoices = _load_local_invoices()
    buckets = {"current": [], "1_to_30": [], "31_to_60": [], "61_to_90": [], "over_90": []}
    disputed = []
    total_outstanding = Decimal(0)
    per_brand = {}
    action_queue = []
    gaps = []
    for inv in invoices:
        status = inv.get("status")
        if status == "paid":
            continue
        amount = dec(inv.get("total") if inv.get("total") is not None else inv.get("amount"))
        due = inv.get("payment_due_date")
        row = {"invoice_id": inv.get("invoice_id"), "deal_id": inv.get("deal_id"),
               "brand_name": inv.get("brand_name"), "amount": _mstr(amount),
               "payment_due_date": due, "status": status}
        if status == "disputed":
            disputed.append(row)
            continue
        if amount is not None:
            total_outstanding += amount
            brand = inv.get("brand_name") or "unknown"
            per_brand[brand] = per_brand.get(brand, Decimal(0)) + amount
        if due is None:
            gaps.append({"gap_type": "missing_due_date",
                         "description": f"{row['invoice_id']} has no payment_due_date",
                         "impact": "cannot age or band this invoice",
                         "recommended_next_step": "derive the due date from structured terms"})
            continue
        due_d = _parse_date(due)
        bucket = aging_bucket(due_d, today)
        row["days_past_due"] = max(0, (today - due_d).days)
        row["urgency_band"] = _ob.urgency_band(due_d, today)
        # Chase action date: contractual due date stands; the ACTION date rolls backward.
        chase = today if due_d <= today else _ob.roll_backward(due_d)
        row["chase_send_by"] = chase.isoformat()
        lp = (inv.get("terms_snapshot") or {}).get("late_penalty")
        acc = accrue_late_penalty(amount, lp, due_d, today)
        row["accrued_penalty"] = acc["amount"]
        buckets[bucket].append(row)
        if bucket != "current":
            action_queue.append(row)
    action_queue.sort(key=lambda r: -r.get("days_past_due", 0))
    return {"as_of": today.isoformat(),
            "buckets": {k: v for k, v in buckets.items()},
            "bucket_totals": {k: _mstr(sum((dec(r["amount"]) or Decimal(0)) for r in v))
                              for k, v in buckets.items()},
            "total_outstanding": _mstr(total_outstanding),
            "per_brand": {k: _mstr(v) for k, v in sorted(per_brand.items())},
            "action_queue": action_queue,
            "disputed": disputed,
            "computed_by": f"{TOOL} ar_scan", "gaps": gaps}


# ── manifest ─────────────────────────────────────────────────────────────────

def manifest(directory=None):
    d = Path(directory) if directory else FINANCE_DIR
    files = sorted(d.glob("*.local.json")) if d.exists() else []
    entries = [{"file": f.name,
                "sha256": hashlib.sha256(f.read_bytes()).hexdigest(),
                "bytes": f.stat().st_size} for f in files]
    return {"bucket": "finance", "root": str(d), "files": entries, "count": len(entries)}


def verify(manifest_path, directory=None):
    want = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    have = {e["file"]: e["sha256"] for e in manifest(directory)["files"]}
    problems = []
    for e in want.get("files", []):
        actual = have.get(e["file"])
        if actual is None:
            problems.append(f"missing: {e['file']}")
        elif actual != e["sha256"]:
            problems.append(f"hash mismatch: {e['file']}")
    return {"ok": not problems, "problems": problems, "checked": len(want.get("files", []))}


# ── selftest ─────────────────────────────────────────────────────────────────

def _check(label, cond, failures):
    print(f"  [{'ok' if cond else 'FAIL'}] {label}")
    if not cond:
        failures.append(label)


def selftest():
    import tempfile
    f = []
    t = date(2026, 7, 3)

    _check("half-up rounding: 2.675 -> 2.68", str(money("2.675")) == "2.68", f)
    _check("half-up rounding: 2.674 -> 2.67", str(money("2.674")) == "2.67", f)
    _check("money quantizes to cents: 10 -> 10.00", str(money(10)) == "10.00", f)
    _check("dec preserves precision pre-quantize", dec("0.1") + dec("0.2") == dec("0.3"), f)

    _check("net-30 plain addition", derive_due_date(date(2026, 1, 30), 30) == date(2026, 3, 1), f)
    _check("net-30 across Feb 29 (leap year)",
           derive_due_date(date(2024, 1, 30), 30) == date(2024, 2, 29), f)
    _check("contractual due date is NOT weekend-rolled",
           derive_due_date(date(2026, 6, 5), 30) == date(2026, 7, 5)
           and date(2026, 7, 5).weekday() == 6, f)

    _check("aging: due today is current", aging_bucket(t, t) == "current", f)
    _check("aging: 1 day past due", aging_bucket(t - timedelta(days=1), t) == "1_to_30", f)
    _check("aging edge: 30 -> 1_to_30", aging_bucket(t - timedelta(days=30), t) == "1_to_30", f)
    _check("aging edge: 31 -> 31_to_60", aging_bucket(t - timedelta(days=31), t) == "31_to_60", f)
    _check("aging edge: 60 -> 31_to_60", aging_bucket(t - timedelta(days=60), t) == "31_to_60", f)
    _check("aging edge: 61 -> 61_to_90", aging_bucket(t - timedelta(days=61), t) == "61_to_90", f)
    _check("aging edge: 90 -> 61_to_90", aging_bucket(t - timedelta(days=90), t) == "61_to_90", f)
    _check("aging edge: 91 -> over_90", aging_bucket(t - timedelta(days=91), t) == "over_90", f)

    _check("penalty: type none accrues 0.00",
           accrue_late_penalty(1000, {"type": "none"}, t - timedelta(days=99), t)["amount"] == "0.00", f)
    lp_flat = {"type": "flat", "rate": 50, "grace_days": 5}
    _check("penalty: flat within grace is 0.00",
           accrue_late_penalty(1000, lp_flat, t - timedelta(days=5), t)["amount"] == "0.00", f)
    _check("penalty: flat past grace is 50.00",
           accrue_late_penalty(1000, lp_flat, t - timedelta(days=6), t)["amount"] == "50.00", f)
    lp_pm = {"type": "percent_per_month", "rate": 1.5, "grace_days": 0}
    _check("penalty: percent_per_month with no full month is 0.00",
           accrue_late_penalty(1000, lp_pm, date(2026, 6, 4), t)["amount"] == "0.00", f)
    _check("penalty: 1 full month is 15.00",
           accrue_late_penalty(1000, lp_pm, date(2026, 6, 3), t)["amount"] == "15.00", f)
    _check("penalty: 2 full months is 30.00",
           accrue_late_penalty(1000, lp_pm, date(2026, 5, 3), t)["amount"] == "30.00", f)
    _check("penalty: month-end clamp (Jan 31 start, Feb 28 anniversary = 1 month)",
           accrue_late_penalty(1000, lp_pm, date(2026, 1, 31), date(2026, 2, 28))["amount"] == "15.00", f)
    _check("penalty: null rate flags instead of guessing",
           accrue_late_penalty(1000, {"type": "flat", "rate": None}, t - timedelta(days=9), t)
           ["gaps"][0]["gap_type"] == "missing_rate", f)
    _check("penalty: unsupported type refused honestly",
           accrue_late_penalty(1000, {"type": "compound_daily", "rate": 1}, t - timedelta(days=9), t)
           ["gaps"][0]["gap_type"] == "unsupported_penalty_type", f)

    _check("revshare: 10 percent of 1000 is 100.00",
           revenue_share(1000, 10)["payout"] == "100.00", f)
    _check("revshare: floor binds", revenue_share(1000, 10, floor=150)["payout"] == "150.00"
           and revenue_share(1000, 10, floor=150)["bound_applied"] == "floor", f)
    _check("revshare: cap binds", revenue_share(1000, 10, cap=80)["payout"] == "80.00"
           and revenue_share(1000, 10, cap=80)["bound_applied"] == "cap", f)
    _check("revshare: missing basis flags, never estimates",
           revenue_share(None, 10)["payout"] is None, f)
    _check("commission clamp math matches",
           commission_split(2000, {"rate_percent": 5, "cap": 90})["payout"] == "90.00", f)

    items = [{"category": "production_materials", "amount": 120.50},
             {"category": "equipment_capex", "amount": 800, "is_capex": True},
             {"category": "production_materials", "quantity": 3, "unit_cost": 9.99},
             {"category": "travel", "description": "gas", "amount": None}]
    ru = cost_rollup(items, time={"total_hours": 10, "hourly_rate": 45})
    _check("rollup: category sums (materials 150.47)",
           ru["by_category"]["production_materials"] == "150.47", f)
    _check("rollup: expense/capex split", ru["totals"]["expense"] == "150.47"
           and ru["totals"]["capex"] == "800.00", f)
    _check("rollup: time cost 10h x 45 = 450.00", ru["totals"]["time_cost"] == "450.00", f)
    _check("rollup: grand total", ru["totals"]["grand"] == "1400.47", f)
    _check("rollup: null amount becomes a gap, not a guess",
           ru["gaps"][0]["gap_type"] == "missing_amount", f)

    pp = proposal_price(500, 30)
    _check("price: cost floor 500 x 1.30 = 650.00", pp["price_floor"] == "650.00"
           and pp["bound"] == "cost_floor", f)
    pp = proposal_price(500, 30, rate_floor=800)
    _check("price: negotiation floor binds at 800.00", pp["price_floor"] == "800.00"
           and pp["bound"] == "negotiation_floor", f)
    pp = proposal_price(500, 30, rate_floor=800, benchmark_range={"low": 200, "high": 700})
    _check("price: above-benchmark flag raised", len(pp["flags"]) == 1, f)

    payload = {"deal_id": "hearthline-2026-001", "brand_name": "Hearthline", "seq": 1,
               "line_items": [{"description": "dedicated video", "quantity": 1, "unit_price": 2500},
                              {"description": "usage rights addon", "amount": 500}],
               "adjustments": [{"description": "early-commit discount", "amount": -250}],
               "terms": {"net_days": 30, "anchor": "delivery",
                         "late_penalty": {"type": "percent_per_month", "rate": 1.5, "grace_days": 5}},
               "anchor_date": "2026-07-01"}
    inv = build_invoice(payload, t)
    _check("invoice: deterministic id", inv["invoice_id"] == "INV-hearthline-2026-001-001", f)
    _check("invoice: subtotal 3000.00, total 2750.00 after adjustment",
           inv["subtotal"] == "3000.00" and inv["total"] == "2750.00", f)
    _check("invoice: due date derived net-30 from delivery",
           inv["payment_due_date"] == "2026-07-31", f)
    _check("invoice: drafted status + human review",
           inv["status"] == "draft" and inv["human_review_required"] is True, f)
    _check("invoice: boundary line present", inv["_boundary"].startswith("ARITHMETIC"), f)
    inv2 = build_invoice({"deal_id": "d", "line_items": [{"description": "x"}]}, t)
    _check("invoice: missing figures become gaps, never estimates",
           any(g["gap_type"] == "missing_amount" for g in inv2["gaps"])
           and any(g["gap_type"] == "missing_terms" for g in inv2["gaps"]), f)

    ok, _ = _write_allowed({"capabilities": {}})
    _check("write gate: refused with finance_management off", ok is False, f)
    ok, reason = _write_allowed({"capabilities": {"finance_management": {"enabled": True}}})
    _check("write gate: invoice_generation also required",
           ok is False and "invoice_generation" in reason, f)
    ok, _ = _write_allowed({"capabilities": {"finance_management": {"enabled": True},
                                             "invoice_generation": {"enabled": True}}})
    _check("write gate: both flags on allows the write", ok is True, f)

    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "INV-test-001.local.json"
        p.write_text(json.dumps(inv), encoding="utf-8")
        m = manifest(td)
        mp = Path(td) / "m.json"
        mp.write_text(json.dumps(m), encoding="utf-8")
        _check("manifest/verify round-trip", verify(mp, td)["ok"] is True, f)
        p.write_text(json.dumps(inv2), encoding="utf-8")
        _check("verify detects tampering", verify(mp, td)["ok"] is False, f)

    invs = [dict(inv, payment_due_date="2026-06-01", status="sent"),
            dict(inv, invoice_id="INV-x-002", payment_due_date="2026-07-10", status="sent"),
            dict(inv, invoice_id="INV-x-003", status="paid"),
            dict(inv, invoice_id="INV-x-004", status="disputed")]
    scan = ar_scan(invs, t)
    _check("ar: 32 days past due lands in 31_to_60",
           scan["buckets"]["31_to_60"][0]["days_past_due"] == 32, f)
    _check("ar: invoice due in 7 days is current with a red band",
           scan["buckets"]["current"][0]["urgency_band"] == "red", f)
    _check("ar: paid excluded and disputed excluded from outstanding (5500.00)",
           len(scan["disputed"]) == 1 and scan["total_outstanding"] == "5500.00", f)
    _check("ar: penalty accrued on the overdue invoice (past grace, <1 month: 0.00)",
           scan["buckets"]["31_to_60"][0]["accrued_penalty"] == "0.00", f)
    _check("ar: chase action date never on a weekend",
           _parse_date(scan["buckets"]["current"][0]["chase_send_by"]).weekday() < 5, f)
    _check("ar: empty state is honest",
           ar_scan([], t)["total_outstanding"] == "0.00" and ar_scan([], t)["gaps"] == [], f)

    n = 44
    print(f"selftest: {'PASS' if not f else 'FAIL'} ({n - len(f)} of {n} checks)")
    return 0 if not f else 1


# ── CLI ──────────────────────────────────────────────────────────────────────

def _read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main(argv):
    ap = argparse.ArgumentParser(description="Creator OS offline finance math")
    ap.add_argument("--ar-scan", nargs="?", const="__local__", metavar="INVOICES_JSON")
    ap.add_argument("--build-invoice", metavar="PAYLOAD_JSON")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--accrue", metavar="INVOICE_JSON")
    ap.add_argument("--revshare", metavar="PAYLOAD_JSON")
    ap.add_argument("--rollup", metavar="ESTIMATE_JSON")
    ap.add_argument("--price", metavar="PAYLOAD_JSON")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--manifest", action="store_true")
    ap.add_argument("--write-manifest", metavar="FILE")
    ap.add_argument("--verify", metavar="FILE")
    ap.add_argument("--today", metavar="YYYY-MM-DD")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)
    today = _parse_date(args.today) if args.today else date.today()

    if args.selftest:
        return selftest()
    if args.ar_scan:
        invoices = None if args.ar_scan == "__local__" else _read_json(args.ar_scan)
        print(json.dumps(ar_scan(invoices, today), indent=2))
        return 0
    if args.build_invoice:
        inv = build_invoice(_read_json(args.build_invoice), today)
        if args.write:
            ok, reason = _write_allowed(_ob.load_config())
            if not ok:
                inv["_gate"] = reason
            else:
                FINANCE_DIR.mkdir(parents=True, exist_ok=True)
                out = FINANCE_DIR / f"{inv['invoice_id']}.local.json"
                out.write_text(json.dumps(inv, indent=2) + "\n", encoding="utf-8")
                inv["_written_to"] = str(out)
        print(json.dumps(inv, indent=2))
        return 0
    if args.accrue:
        inv = _read_json(args.accrue)
        lp = (inv.get("terms_snapshot") or inv.get("terms") or {}).get("late_penalty")
        amount = inv.get("total") if inv.get("total") is not None else inv.get("amount")
        print(json.dumps(accrue_late_penalty(amount, lp,
                                             _parse_date(inv.get("payment_due_date")), today),
                         indent=2))
        return 0
    if args.revshare:
        p = _read_json(args.revshare)
        print(json.dumps(revenue_share(p.get("basis_amount"), p.get("percent"),
                                       p.get("floor"), p.get("cap")), indent=2))
        return 0
    if args.rollup:
        p = _read_json(args.rollup)
        print(json.dumps(cost_rollup(p.get("line_items"), p.get("time")), indent=2))
        return 0
    if args.price:
        p = _read_json(args.price)
        print(json.dumps(proposal_price(p.get("cost_total"), p.get("margin_percent"),
                                        p.get("rate_floor"), p.get("benchmark_range")), indent=2))
        return 0
    if args.status:
        m = manifest()
        cfg = _ob.load_config()
        print(json.dumps({"records": m["count"], "root": m["root"],
                          "finance_management": _ob.flag_enabled(cfg, "finance_management"),
                          "invoice_generation": _ob.flag_enabled(cfg, "invoice_generation")},
                         indent=2))
        return 0
    if args.manifest:
        print(json.dumps(manifest(), indent=2))
        return 0
    if args.write_manifest:
        Path(args.write_manifest).write_text(json.dumps(manifest(), indent=2) + "\n",
                                             encoding="utf-8")
        print(f"wrote {args.write_manifest}")
        return 0
    if args.verify:
        result = verify(args.verify)
        print(json.dumps(result, indent=2))
        return 0 if result["ok"] else 1
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
