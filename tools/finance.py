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

Read-only commands (--ar-scan, --accrue, --revshare, --rollup, --price, --price-package, --status)
are always available. Record writes are gated: --build-invoice --write requires the finance_management AND
invoice_generation flags. Real records live in pipeline/finance/*.local.json (gitignored);
CREATOR_OS_ROOT redirects all paths for sandboxed runs, exactly like obligations.py.

Usage:
  python3 tools/finance.py --ar-scan [INVOICES_JSON] [--today YYYY-MM-DD]
  python3 tools/finance.py --build-invoice PAYLOAD_JSON [--write] [--today YYYY-MM-DD]
  python3 tools/finance.py --accrue INVOICE_JSON [--today YYYY-MM-DD]
  python3 tools/finance.py --revshare PAYLOAD_JSON
  python3 tools/finance.py --rollup ESTIMATE_JSON
  python3 tools/finance.py --price PAYLOAD_JSON
  python3 tools/finance.py --price-package PAYLOAD_JSON
  python3 tools/finance.py --status | --manifest | --write-manifest FILE | --verify FILE
  python3 tools/finance.py --selftest
"""
import argparse
import hashlib
import json
import os
import re
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


def proposal_price(cost_total=None, margin_percent=None, rate_floor=None, benchmark_range=None):
    """Price floor = max(available floors). Floors: cost_floor (cost_total + margin) when BOTH cost
    inputs are supplied; negotiation_floor when rate_floor is supplied. At least one floor is
    required; missing inputs become named gaps, never zeros. Decision support, never the quote."""
    gaps = []
    floors = {}
    have_cost = cost_total is not None and margin_percent is not None
    if have_cost:
        floors["cost_floor"] = dec(cost_total) * (Decimal(100) + dec(margin_percent)) / Decimal(100)
    elif cost_total is not None or margin_percent is not None:
        gaps.append({"gap_type": "partial_cost_inputs",
                     "description": "only one of cost_total/margin_percent supplied; cost floor not computed",
                     "impact": "cost floor missing from the comparison",
                     "recommended_next_step": "supply both cost_total and margin_percent (run cost_rollup)"})
    if rate_floor is not None:
        floors["negotiation_floor"] = dec(rate_floor)
    if not floors:
        return {"price_floor": None, "computed_by": f"{TOOL} proposal_price",
                "gaps": gaps + [{"gap_type": "missing_input",
                                 "description": "needs cost_total+margin_percent and/or rate_floor",
                                 "impact": "no price floor computed",
                                 "recommended_next_step": "run cost_rollup first and state a margin, "
                                                          "or supply the rate-card negotiation floor"}]}
    if "cost_floor" not in floors:
        gaps.append({"gap_type": "no_cost_basis",
                     "description": "cost floor not computed; true margin at this price is unknown",
                     "impact": "the floor rests on the negotiation floor alone",
                     "recommended_next_step": "run cost-estimate and re-price to confirm margin"})
    bound = max(floors, key=lambda k: floors[k])
    price = floors[bound]
    flags = []
    br = benchmark_range or {}
    if br.get("high") is not None and price > dec(br["high"]):
        flags.append("price floor exceeds the benchmark range high; expect pushback or justify scope")
    if br.get("low") is not None and price < dec(br["low"]):
        flags.append("price floor is below the benchmark range low; the market may bear more")
    return {"price_floor": _mstr(price), "bound": bound,
            "cost_floor": _mstr(floors.get("cost_floor")),
            "negotiation_floor": _mstr(rate_floor),
            "benchmark_range": {k: _mstr(v) for k, v in br.items()} if br else None,
            "flags": flags, "computed_by": f"{TOOL} proposal_price", "gaps": gaps}


def load_rate_card(root=None):
    """Load the personal rate card: pipeline/finance/rate-card.local.json if present (real rates,
    gitignored), else the committed template (all-null). Returns (card, source) with source
    'local' | 'template_defaults'. Honors CREATOR_OS_ROOT via ROOT. Never fabricates a rate."""
    base = Path(root) if root else ROOT
    local = base / "pipeline" / "finance" / "rate-card.local.json"
    tmpl = base / "pipeline" / "finance" / "rate-card.template.json"
    for path, source in ((local, "local"), (tmpl, "template_defaults")):
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8")), source
            except (OSError, json.JSONDecodeError):
                continue
    return {"rates": [], "uplifts": [], "subscriber_tier": None}, "template_defaults"


def rate_floor_for(card, fmt):
    """Resolve a format's base rate from the rate card. Returns (base_rate_or_None, gap_or_None);
    a missing or null entry is a named gap, never a guessed number."""
    for r in (card or {}).get("rates", []):
        if r.get("format") == fmt:
            if r.get("base_rate") is not None:
                return r["base_rate"], None
            break
    return None, {"gap_type": "no_rate_card_entry",
                  "description": f"no base_rate for format '{fmt}' in the rate card",
                  "impact": "negotiation floor missing for this format",
                  "recommended_next_step": "fill the format's base_rate in rate-card.local.json "
                                           "(copy pipeline/finance/rate-card.template.json)"}


def _tier_gaps(card, benchmark_range, benchmark_tier=None):
    """F8: benchmark comparisons need a known subscriber tier. Returns a list of gap/flag dicts:
    tier unknown while a benchmark is attached -> benchmark_tier_assumed gap; tier known and the
    payload declares the benchmark's tier and they differ -> benchmark_tier_mismatch gap."""
    if not benchmark_range:
        return []
    tier = (card or {}).get("subscriber_tier")
    if tier is None:
        return [{"gap_type": "benchmark_tier_assumed",
                 "description": "benchmark range applied without a known subscriber tier",
                 "impact": "the range may belong to a different audience size",
                 "recommended_next_step": "set subscriber_tier in rate-card.local.json"}]
    if benchmark_tier is not None and str(benchmark_tier) != str(tier):
        return [{"gap_type": "benchmark_tier_mismatch",
                 "description": f"rate card tier '{tier}' differs from the benchmark's tier "
                                f"'{benchmark_tier}'",
                 "impact": "the comparison range does not match the creator's tier",
                 "recommended_next_step": "use the benchmark rows for the creator's own tier"}]
    return []


def price_package(payload):
    """Multi-deliverable package floor. payload: {line_items: [{label, rate_floor?, cost_total?,
    margin_percent?, benchmark_range?}, ...], package_benchmark_range?: {low, high}}.
    Runs proposal_price per item, sums per-item floors into package_floor (quantized once), unions
    per-item gaps tagged with the item label, and flags the SUM against package_benchmark_range.
    Items with no computable floor are listed in unpriceable_items and EXCLUDED from the sum with a
    package-level gap (an unpriceable item is never treated as costing 0)."""
    items_in = payload.get("line_items") or []
    if not items_in:
        return {"package_floor": None, "items": [], "unpriceable_items": [],
                "computed_by": f"{TOOL} price_package",
                "gaps": [{"gap_type": "missing_input", "description": "line_items is empty",
                          "impact": "no package floor computed",
                          "recommended_next_step": "supply one line item per deliverable"}]}
    card = None
    if any(li.get("format") and li.get("rate_floor") is None for li in items_in) \
            or payload.get("package_benchmark_range"):
        card, card_source = load_rate_card()
    items_out, unpriceable, gaps = [], [], []
    total = Decimal(0)
    for i, li in enumerate(items_in):
        label = li.get("label") or f"item_{i + 1}"
        rate_floor = li.get("rate_floor")
        rate_floor_source = "payload" if rate_floor is not None else None
        format_missed = False
        if rate_floor is None and li.get("format"):
            rate_floor, rc_gap = rate_floor_for(card, li["format"])
            if rate_floor is not None:
                rate_floor_source = "rate_card"
            elif rc_gap:
                gaps.append({**rc_gap, "item": label})
                format_missed = True
        res = proposal_price(cost_total=li.get("cost_total"), margin_percent=li.get("margin_percent"),
                             rate_floor=rate_floor, benchmark_range=li.get("benchmark_range"))
        if format_missed:
            # no_rate_card_entry already names the exact fix; the generic missing_input gap for the
            # same item is noise, not information.
            res["gaps"] = [g for g in res.get("gaps", []) if g.get("gap_type") != "missing_input"]
        for g in res.get("gaps", []):
            gaps.append({**g, "item": label})
        for tg in _tier_gaps(card, li.get("benchmark_range"), li.get("benchmark_tier")):
            gaps.append({**tg, "item": label})
        items_out.append({"label": label, "price_floor": res["price_floor"],
                          "bound": res.get("bound"), "rate_floor_source": rate_floor_source,
                          "flags": res.get("flags", []),
                          "gaps": res.get("gaps", [])})
        if res["price_floor"] is None:
            unpriceable.append(label)
        else:
            total += dec(res["price_floor"])
    if unpriceable:
        gaps.append({"gap_type": "unpriceable_items",
                     "description": f"no floor computable for: {', '.join(unpriceable)}",
                     "impact": "package floor UNDERSTATES the package (these items are excluded, not zero)",
                     "recommended_next_step": "supply a rate_floor or cost inputs for each listed item"})
    package_flags = []
    br = payload.get("package_benchmark_range") or {}
    if br.get("high") is not None and total > dec(br["high"]):
        package_flags.append("package floor exceeds the benchmark range high; expect pushback or justify scope")
    if br.get("low") is not None and total < dec(br["low"]):
        package_flags.append("package floor is below the benchmark range low; the market may bear more")
    gaps.extend(_tier_gaps(card, br or None, payload.get("package_benchmark_tier")))
    return {"package_floor": _mstr(total) if len(unpriceable) < len(items_in) else None,
            "items": items_out, "unpriceable_items": unpriceable,
            "package_benchmark_range": {k: _mstr(v) for k, v in br.items()} if br else None,
            "package_flags": package_flags,
            "computed_by": f"{TOOL} price_package", "gaps": gaps}


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


# ── cash flow ────────────────────────────────────────────────────────────────

def cashflow(invoices=None, scheduled=None, estimates=None, horizon_days=90, today=None):
    """Deterministic cash view over the horizon: expected inflows from open invoice due dates,
    planned inflows from scheduled invoice rows (deal-resourcing triggers already mapped to
    dates), and outflows from cost estimates. Weekly buckets. This is MOVEMENT, not a bank
    balance (no opening balance is known here); overdue receivables and undated outflows are
    reported separately with gaps, never guessed into a week."""
    today = today or date.today()
    horizon_days = max(7, int(horizon_days))
    if invoices is None:
        invoices = _load_local_invoices()
    weeks = []
    n_weeks = (horizon_days + 6) // 7
    for i in range(n_weeks):
        weeks.append({"week_start": (today + timedelta(days=7 * i)).isoformat(),
                      "inflow": Decimal(0), "outflow": Decimal(0)})
    end = today + timedelta(days=7 * n_weeks)
    gaps = []
    overdue_total = Decimal(0)
    beyond_horizon = Decimal(0)
    undated_outflows = Decimal(0)

    def _bucket(d):
        idx = (d - today).days // 7
        return weeks[idx] if 0 <= idx < n_weeks else None

    for inv in invoices:
        status = inv.get("status")
        if status in ("paid", "disputed"):
            continue
        amount = dec(inv.get("total") if inv.get("total") is not None else inv.get("amount"))
        due = inv.get("payment_due_date")
        if amount is None or due is None:
            gaps.append({"gap_type": "unbucketable_invoice",
                         "description": f"{inv.get('invoice_id')} lacks an amount or due date",
                         "impact": "excluded from the cash view",
                         "recommended_next_step": "complete the invoice record"})
            continue
        due_d = _parse_date(due)
        if due_d < today:
            overdue_total += amount
            continue
        w = _bucket(due_d)
        if w is None:
            beyond_horizon += amount
            continue
        w["inflow"] += amount
    for row in scheduled or []:
        amount = dec(row.get("amount"))
        d = row.get("due_date") or row.get("expected_date")
        if amount is None or d is None:
            gaps.append({"gap_type": "unbucketable_scheduled",
                         "description": f"scheduled row {row.get('label') or row.get('invoice_id') or ''} "
                                        "lacks an amount or date",
                         "impact": "excluded from the cash view",
                         "recommended_next_step": "date the trigger via deal-resourcing first"})
            continue
        d = _parse_date(d)
        w = _bucket(d)
        if w is None:
            if d < today:
                gaps.append({"gap_type": "scheduled_in_past",
                             "description": f"scheduled inflow dated {d.isoformat()} is in the past",
                             "impact": "excluded from the cash view",
                             "recommended_next_step": "invoice it (invoice-generate) or re-date the trigger"})
            else:
                beyond_horizon += amount
            continue
        w["inflow"] += amount
    for est in estimates or []:
        totals = est.get("totals") or {}
        amount = dec(totals.get("grand") if totals.get("grand") is not None else est.get("amount"))
        d = est.get("expected_date")
        if amount is None:
            continue
        if d is None:
            undated_outflows += amount
            gaps.append({"gap_type": "undated_outflow",
                         "description": f"estimate {est.get('estimate_id') or ''} has no expected_date",
                         "impact": "outflow totaled separately, not bucketed",
                         "recommended_next_step": "date the spend to place it in a week"})
            continue
        w = _bucket(_parse_date(d))
        if w is not None:
            w["outflow"] += amount
    running = Decimal(0)
    out_weeks = []
    for w in weeks:
        net = w["inflow"] - w["outflow"]
        running += net
        out_weeks.append({"week_start": w["week_start"], "inflow": _mstr(w["inflow"]),
                          "outflow": _mstr(w["outflow"]), "net": _mstr(net),
                          "running_net": _mstr(running)})
    if overdue_total:
        gaps.append({"gap_type": "overdue_receivables",
                     "description": f"overdue invoices total {_mstr(overdue_total)} and have no "
                                    "predictable week",
                     "impact": "not counted in any bucket",
                     "recommended_next_step": "run ar-review and chase; collection timing is unknown"})
    return {"as_of": today.isoformat(), "horizon_days": 7 * n_weeks,
            "horizon_end": end.isoformat(), "weeks": out_weeks,
            "totals": {"inflow": _mstr(sum((dec(w["inflow"]) for w in out_weeks), Decimal(0))),
                       "outflow": _mstr(sum((dec(w["outflow"]) for w in out_weeks), Decimal(0))),
                       "net_movement": _mstr(running)},
            "overdue_receivables": _mstr(overdue_total),
            "beyond_horizon": _mstr(beyond_horizon),
            "undated_outflows": _mstr(undated_outflows),
            "note": "cash MOVEMENT over the horizon, not a bank balance",
            "computed_by": f"{TOOL} cashflow", "gaps": gaps}


# ── redaction (for anything that leaves this machine) ────────────────────────

REDACT_AMOUNT_KEYS = {"amount", "total", "subtotal", "payout", "raw", "price_floor",
                      "cost_floor", "negotiation_floor", "total_outstanding", "accrued_penalty",
                      "inflow", "outflow", "net", "running_net", "net_movement",
                      "overdue_receivables", "beyond_horizon", "undated_outflows",
                      "unit_price", "grand", "expense", "capex", "time_cost"}
REDACT_NAME_KEYS = {"brand_name", "account_ref", "vendor"}
_BANDS = [(100, "under 100"), (500, "100 to 500"), (1000, "500 to 1k"), (5000, "1k to 5k"),
          (10000, "5k to 10k"), (50000, "10k to 50k")]


def _band(value):
    try:
        v = Decimal(str(value))
    except Exception:
        return value
    if v == 0:
        return "0"
    neg = v < 0
    v = abs(v)
    label = "over 50k"
    for edge, name in _BANDS:
        if v < edge:
            label = name
            break
    return f"minus {label}" if neg else label


def _initials(name):
    if not isinstance(name, str) or not name.strip():
        return name
    return ".".join(part[0].upper() for part in name.split() if part) + "."


def redact(obj):
    """Mask money figures into bands and counterparty names into initials for any output that
    leaves this machine (screenshots, shared text, transcripts). The raw record is untouched;
    this returns a copy. Redacted output is for sharing, never for bookkeeping."""
    if isinstance(obj, list):
        return [redact(x) for x in obj]
    if not isinstance(obj, dict):
        return obj
    out = {}
    for k, v in obj.items():
        if k in REDACT_NAME_KEYS and isinstance(v, str):
            out[k] = _initials(v)
        elif k == "per_brand" and isinstance(v, dict):
            out[k] = {_initials(b): _band(a) for b, a in v.items()}
        elif k == "bucket_totals" and isinstance(v, dict):
            out[k] = {b: _band(a) for b, a in v.items()}
        elif k in REDACT_AMOUNT_KEYS:
            if isinstance(v, dict):
                out[k] = redact(v)
            elif isinstance(v, list):
                out[k] = [redact(x) for x in v]
            else:
                out[k] = _band(v)
        else:
            out[k] = redact(v)
    if "computed_by" in out:
        out["_redacted"] = True
    return out


# ── payment reconciliation ───────────────────────────────────────────────────

def _csv_rows(source):
    """Rows from a CSV path or an already-parsed list of dicts.

    STRUCTURAL SAFETY: a CSV path inside the repo tree is refused unless its filename contains
    `.local.` — bank exports live at pipeline/finance/<name>.local.csv (gitignored by the
    allowlist-invert rules) or outside the repo entirely. This makes 'accidentally committed the
    bank export' structurally impossible via this tool."""
    import csv
    if isinstance(source, list):
        return source
    p = Path(source).resolve()
    try:
        inside = p.is_relative_to(ROOT.resolve())
    except AttributeError:  # Python < 3.9 fallback (not expected)
        inside = str(p).startswith(str(ROOT.resolve()))
    if inside and ".local." not in p.name:
        raise PermissionError(
            f"refusing to read a CSV inside the repo without a .local. name: {p.name}. "
            "Save bank exports as pipeline/finance/<name>.local.csv (gitignored) or keep them "
            "outside the repo entirely (shared/finance-engine.md privacy boundary).")
    with open(p, newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def _pick_columns(rows, mapping=None):
    """Column names for date/amount/description: explicit mapping wins, else heuristics."""
    mapping = mapping or {}
    if not rows:
        return mapping.get("date"), mapping.get("amount"), mapping.get("description")
    headers = list(rows[0].keys())
    lower = {h.lower(): h for h in headers}

    def _by_names(names):
        for n in names:
            if n in lower:
                return lower[n]
        return None

    date_col = mapping.get("date") or _by_names(["date", "posted", "transaction date", "posting date"])
    amount_col = mapping.get("amount") or _by_names(["amount", "gross", "credit", "deposit"])
    desc_col = mapping.get("description") or _by_names(["description", "memo", "name", "payee", "details"])
    if date_col is None:  # first column whose first value parses as a date
        for h in headers:
            try:
                _flex_date(rows[0].get(h))
                date_col = h
                break
            except (ValueError, TypeError):
                continue
    if amount_col is None:  # rightmost column whose first value parses as a Decimal
        for h in reversed(headers):
            try:
                _flex_amount(rows[0].get(h))
                amount_col = h
                break
            except (ValueError, TypeError, ArithmeticError):
                continue
    if desc_col is None and headers:  # longest text value in the first row
        desc_col = max(headers, key=lambda h: len(str(rows[0].get(h) or "")))
    return date_col, amount_col, desc_col


def _flex_date(value):
    """ISO or US-style date."""
    s = str(value or "").strip()
    try:
        return date.fromisoformat(s[:10])
    except ValueError:
        pass
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{2,4})$", s)
    if m:
        mth, day, yr = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if yr < 100:
            yr += 2000
        return date(yr, mth, day)
    raise ValueError(f"unparseable date: {value!r}")


def _flex_amount(value):
    s = str(value or "").strip().replace("$", "").replace(",", "")
    if s.startswith("(") and s.endswith(")"):
        s = "-" + s[1:-1]
    return Decimal(s)


def reconcile(csv_rows_or_path, invoices=None, window_days=5, amount_tolerance="0.00",
              mapping=None, today=None):
    """Match bank/PayPal export rows to open invoices. PROPOSAL-ONLY: nothing is marked paid
    here; the human confirms each proposal and mark_paid() does the gated write.

    Confidence tiers per CSV row against open (not paid/disputed) invoices:
      exact    -- amount equal, date within window, and the brand name appears in the description
      probable -- amount equal and date within window
      uncertain-- amount within tolerance, or brand match alone
    Each invoice is matched at most once (greedy: best tier first, then smallest date delta).
    Unmatched rows and unmatched invoices are listed, never force-paired."""
    if invoices is None:
        invoices = _load_local_invoices()
    open_invoices = [i for i in invoices if i.get("status") not in ("paid", "disputed")]
    rows = _csv_rows(csv_rows_or_path)
    date_col, amount_col, desc_col = _pick_columns(rows, mapping)
    gaps = []
    if not rows:
        gaps.append({"gap_type": "empty_csv", "description": "no rows to reconcile",
                     "impact": "nothing proposed", "recommended_next_step": "check the export"})
    tol = dec(amount_tolerance) or Decimal(0)
    candidates = []  # (tier_rank, date_delta, row_idx, invoice_id, detail)
    parsed_rows = []
    for idx, row in enumerate(rows):
        try:
            r_date = _flex_date(row.get(date_col))
            r_amount = _flex_amount(row.get(amount_col))
        except (ValueError, TypeError, ArithmeticError) as exc:
            gaps.append({"gap_type": "unparseable_row",
                         "description": f"row {idx}: {exc}",
                         "impact": "excluded from matching",
                         "recommended_next_step": "pass an explicit column mapping"})
            parsed_rows.append(None)
            continue
        desc = str(row.get(desc_col) or "")
        parsed_rows.append({"index": idx, "date": r_date, "amount": r_amount,
                            "description": desc})
    for pr in parsed_rows:
        if pr is None:
            continue
        for inv in open_invoices:
            inv_amount = dec(inv.get("total") if inv.get("total") is not None else inv.get("amount"))
            if inv_amount is None:
                continue
            due = inv.get("payment_due_date")
            date_delta = abs((pr["date"] - _parse_date(due)).days) if due else 9999
            brand = str(inv.get("brand_name") or "")
            brand_hit = bool(brand) and brand.lower() in pr["description"].lower()
            amount_exact = pr["amount"] == inv_amount
            amount_close = abs(pr["amount"] - inv_amount) <= tol
            if amount_exact and date_delta <= window_days and brand_hit:
                tier = ("exact", 0)
            elif amount_exact and date_delta <= window_days:
                tier = ("probable", 1)
            elif amount_close or brand_hit:
                tier = ("uncertain", 2)
            else:
                continue
            candidates.append((tier[1], date_delta, pr["index"], inv.get("invoice_id"),
                               {"row_index": pr["index"], "row_date": pr["date"].isoformat(),
                                "row_amount": _mstr(pr["amount"]),
                                "row_description": pr["description"][:120],
                                "invoice_id": inv.get("invoice_id"),
                                "invoice_amount": _mstr(inv_amount),
                                "brand_name": brand, "date_delta_days": date_delta,
                                "confidence": tier[0]}))
    candidates.sort(key=lambda c: (c[0], c[1]))
    used_rows, used_invoices = set(), set()
    proposals = []
    for _, _, row_idx, inv_id, detail in candidates:
        if row_idx in used_rows or inv_id in used_invoices:
            continue
        used_rows.add(row_idx)
        used_invoices.add(inv_id)
        proposals.append(detail)
    unmatched_rows = [{"row_index": pr["index"], "row_date": pr["date"].isoformat(),
                       "row_amount": _mstr(pr["amount"]),
                       "row_description": pr["description"][:120]}
                      for pr in parsed_rows if pr and pr["index"] not in used_rows]
    unmatched_invoices = [{"invoice_id": i.get("invoice_id"), "brand_name": i.get("brand_name"),
                           "amount": _mstr(dec(i.get("total") if i.get("total") is not None
                                               else i.get("amount")))}
                          for i in open_invoices if i.get("invoice_id") not in used_invoices]
    return {"proposals": proposals, "unmatched_rows": unmatched_rows,
            "unmatched_invoices": unmatched_invoices,
            "human_review_required": True,
            "note": "proposal only; confirm each match, then mark_paid does the gated write",
            "computed_by": f"{TOOL} reconcile", "gaps": gaps}


def mark_paid(invoice_id, paid_date, method=None, config=None):
    """Mark one invoice paid AFTER the human confirms a reconciliation proposal. Gated on
    finance_management; edits the standalone record in place and reports what changed."""
    cfg = config if config is not None else _ob.load_config()
    if not _ob.flag_enabled(cfg, "finance_management"):
        return {"updated": False,
                "reason": ("finance_management is off; the record was not modified "
                           "(see degraded_behavior.finance_management_disabled)")}
    path = FINANCE_DIR / f"{invoice_id}.local.json"
    if not path.exists():
        return {"updated": False, "reason": f"no record at pipeline/finance/{invoice_id}.local.json"}
    record = json.loads(path.read_text(encoding="utf-8"))
    record["status"] = "paid"
    record["payment_received_date"] = _parse_date(paid_date).isoformat()
    if method:
        record["payment_method"] = method
    path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return {"updated": True, "invoice_id": invoice_id, "status": "paid",
            "payment_received_date": record["payment_received_date"],
            "payment_method": record.get("payment_method"),
            "computed_by": f"{TOOL} mark_paid"}


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
    _check.count = getattr(_check, "count", 0) + 1
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

    # P40-1 (F4): rate-floor-only pricing works, with the honest no-cost-basis gap
    pp = proposal_price(rate_floor=600, benchmark_range={"low": 500, "high": 3000})
    _check("price: rate-floor-only computes 600.00", pp["price_floor"] == "600.00"
           and pp["bound"] == "negotiation_floor", f)
    _check("price: rate-floor-only carries no_cost_basis gap",
           any(g["gap_type"] == "no_cost_basis" for g in pp["gaps"]), f)
    pp = proposal_price()
    _check("price: no floors at all -> missing_input gap, null floor",
           pp["price_floor"] is None
           and any(g["gap_type"] == "missing_input" for g in pp["gaps"]), f)
    pp = proposal_price(cost_total=500, rate_floor=600)
    _check("price: partial cost inputs -> partial_cost_inputs gap, floor still 600.00",
           pp["price_floor"] == "600.00"
           and any(g["gap_type"] == "partial_cost_inputs" for g in pp["gaps"]), f)

    # P40-1 (F6): package pricing
    pk = price_package({"line_items": [
        {"label": "long_form", "rate_floor": 600},
        {"label": "tiktok", "rate_floor": 200}]})
    _check("package: two items sum to 800.00", pk["package_floor"] == "800.00"
           and not pk["unpriceable_items"], f)
    pk = price_package({"line_items": [
        {"label": "long_form", "rate_floor": 600},
        {"label": "tiktok"}]})
    _check("package: unpriceable item excluded from sum, not zeroed",
           pk["package_floor"] == "600.00" and pk["unpriceable_items"] == ["tiktok"]
           and any(g["gap_type"] == "unpriceable_items" for g in pk["gaps"]), f)
    pk = price_package({"line_items": [{"label": "long_form", "rate_floor": 600},
                                       {"label": "tiktok", "rate_floor": 200}],
                        "package_benchmark_range": {"low": 900, "high": 5000}})
    _check("package: below-benchmark package flag raised",
           any("below the benchmark" in x for x in pk["package_flags"]), f)
    pk = price_package({"line_items": [{"label": "a", "rate_floor": "99.999"}]})
    _check("package: sum quantized to cents once", pk["package_floor"] == "100.00", f)

    # P40-2 (F5): rate card load + format resolution (temp-dir sandbox, never the real repo files)
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        fin = Path(td) / "pipeline" / "finance"
        fin.mkdir(parents=True)
        card, src = load_rate_card(root=td)
        _check("ratecard: no files -> empty defaults, template_defaults source",
               src == "template_defaults" and card.get("subscriber_tier") is None, f)
        (fin / "rate-card.local.json").write_text(json.dumps({
            "subscriber_tier": "50k_to_100k",
            "rates": [{"format": "youtube_dedicated_long_form", "base_rate": 600},
                      {"format": "tiktok_dedicated", "base_rate": None}]}), encoding="utf-8")
        card, src = load_rate_card(root=td)
        _check("ratecard: local card wins", src == "local"
               and card["subscriber_tier"] == "50k_to_100k", f)
        rf, gap = rate_floor_for(card, "youtube_dedicated_long_form")
        _check("ratecard: format resolves to 600", rf == 600 and gap is None, f)
        rf, gap = rate_floor_for(card, "tiktok_dedicated")
        _check("ratecard: null base_rate -> no_rate_card_entry gap, never a guess",
               rf is None and gap["gap_type"] == "no_rate_card_entry", f)
    # P40-2 (F8): tier gaps
    tg = _tier_gaps({"subscriber_tier": None}, {"low": 500, "high": 3000})
    _check("tier: unknown tier + benchmark -> benchmark_tier_assumed",
           tg and tg[0]["gap_type"] == "benchmark_tier_assumed", f)
    tg = _tier_gaps({"subscriber_tier": "50k_to_100k"}, {"low": 500, "high": 3000},
                    benchmark_tier="10k_to_50k")
    _check("tier: declared benchmark tier mismatch flagged",
           tg and tg[0]["gap_type"] == "benchmark_tier_mismatch", f)
    tg = _tier_gaps({"subscriber_tier": "50k_to_100k"}, {"low": 500, "high": 3000},
                    benchmark_tier="50k_to_100k")
    _check("tier: matching tier -> no gap", tg == [], f)

    # P41: the specific no_rate_card_entry gap suppresses the generic missing_input twin, and a
    # mixed open-vocabulary package (video + script + ideation) prices item by item.
    with tempfile.TemporaryDirectory() as td:
        fin = Path(td) / "pipeline" / "finance"
        fin.mkdir(parents=True)
        (fin / "rate-card.local.json").write_text(json.dumps({
            "subscriber_tier": None,
            "rates": [{"format": "youtube_dedicated_long_form", "base_rate": 600}]}),
            encoding="utf-8")
        _old_root = ROOT
        try:
            globals()["ROOT"] = Path(td)
            pk = price_package({"line_items": [
                {"label": "long-form video", "format": "youtube_dedicated_long_form"},
                {"label": "script only", "format": "script_only"},
                {"label": "video concept ideas"}]})
        finally:
            globals()["ROOT"] = _old_root
        script_gaps = [g["gap_type"] for g in pk["gaps"] if g.get("item") == "script only"]
        _check("gaps: format miss emits no_rate_card_entry and suppresses missing_input",
               "no_rate_card_entry" in script_gaps and "missing_input" not in script_gaps, f)
        ideas_gaps = [g["gap_type"] for g in pk["gaps"] if g.get("item") == "video concept ideas"]
        _check("gaps: no-format no-input item still emits missing_input",
               "missing_input" in ideas_gaps and "no_rate_card_entry" not in ideas_gaps, f)
        _check("package: mixed deliverables price item by item, only the priced item sums",
               pk["package_floor"] == "600.00"
               and pk["unpriceable_items"] == ["script only", "video concept ideas"], f)

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

    cf_invoices = [
        {"invoice_id": "INV-a-001", "brand_name": "Hearthline", "total": "2750.00",
         "payment_due_date": "2026-07-10", "status": "sent"},
        {"invoice_id": "INV-a-002", "brand_name": "Lumen Co", "total": "1200.00",
         "payment_due_date": "2026-06-01", "status": "overdue"},
        {"invoice_id": "INV-a-003", "brand_name": "Fictionalia", "total": "900.00",
         "payment_due_date": "2027-01-15", "status": "sent"},
        {"invoice_id": "INV-a-004", "total": "10.00", "payment_due_date": "2026-07-05",
         "status": "paid"},
    ]
    cf = cashflow(cf_invoices,
                  scheduled=[{"amount": 500, "due_date": "2026-07-20", "label": "deposit"},
                             {"amount": 100, "label": "undated trigger"}],
                  estimates=[{"estimate_id": "e1", "totals": {"grand": "300.00"},
                              "expected_date": "2026-07-08"},
                             {"estimate_id": "e2", "totals": {"grand": "50.00"}}],
                  horizon_days=90, today=t)
    _check("cashflow: due-in-7-days lands in week 1", cf["weeks"][1]["inflow"] == "2750.00", f)
    _check("cashflow: scheduled deposit lands in week 3", cf["weeks"][2]["inflow"] == "500.00", f)
    _check("cashflow: dated estimate is a week-1 outflow", cf["weeks"][0]["outflow"] == "300.00", f)
    _check("cashflow: overdue receivable excluded with a gap",
           cf["overdue_receivables"] == "1200.00"
           and any(g["gap_type"] == "overdue_receivables" for g in cf["gaps"]), f)
    _check("cashflow: beyond-horizon inflow totaled separately",
           cf["beyond_horizon"] == "900.00", f)
    _check("cashflow: undated outflow totaled separately with a gap",
           cf["undated_outflows"] == "50.00"
           and any(g["gap_type"] == "undated_outflow" for g in cf["gaps"]), f)
    _check("cashflow: undated scheduled row is a gap, never bucketed",
           any(g["gap_type"] == "unbucketable_scheduled" for g in cf["gaps"]), f)
    _check("cashflow: paid invoices are ignored",
           all(w["inflow"] != "10.00" for w in cf["weeks"]), f)
    _check("cashflow: net movement adds up",
           cf["totals"]["net_movement"] == "2950.00", f)
    _check("cashflow: movement-not-balance note present", "not a bank balance" in cf["note"], f)

    _check("redact: band edges (999.99 -> 500 to 1k, 1000 -> 1k to 5k)",
           _band("999.99") == "500 to 1k" and _band("1000") == "1k to 5k", f)
    _check("redact: zero and negative bands", _band("0") == "0"
           and _band("-250") == "minus 100 to 500", f)
    _check("redact: brand becomes initials", _initials("Hearthline Home Co") == "H.H.C.", f)
    red = redact(ar_scan(cf_invoices, t))
    _check("redact: ar amounts banded and brands masked",
           red["total_outstanding"] in ("1k to 5k", "5k to 10k")
           and all("." in b for b in red["per_brand"]), f)
    _check("redact: marks itself and never mutates the original",
           red.get("_redacted") is True and cf_invoices[0]["total"] == "2750.00", f)

    # Reconciliation fixtures: INLINE and obviously fictional (no CSV file is ever committed).
    rec_invoices = [
        {"invoice_id": "INV-hearthline-2026-001-001", "brand_name": "Hearthline",
         "total": "2750.00", "payment_due_date": "2026-07-31", "status": "sent"},
        {"invoice_id": "INV-lumen-2026-002-001", "brand_name": "Lumen Co",
         "total": "1200.00", "payment_due_date": "2026-07-15", "status": "sent"},
        {"invoice_id": "INV-x-old", "brand_name": "Fictionalia", "total": "500.00",
         "payment_due_date": "2026-05-01", "status": "paid"},
    ]
    rec_rows = [
        {"Date": "2026-07-30", "Description": "ACH HEARTHLINE HOME LLC", "Amount": "2,750.00"},
        {"Date": "07/16/2026", "Description": "DEPOSIT TRANSFER", "Amount": "$1,200.00"},
        {"Date": "2026-07-02", "Description": "COFFEE SHOP", "Amount": "(4.50)"},
    ]
    rec = reconcile(rec_rows, rec_invoices, window_days=5)
    _check("reconcile: exact tier (amount + window + brand substring)",
           rec["proposals"][0]["confidence"] == "exact"
           and rec["proposals"][0]["invoice_id"] == "INV-hearthline-2026-001-001", f)
    _check("reconcile: probable tier (amount + window, US date and $ comma parsing)",
           any(p["confidence"] == "probable" and p["invoice_id"] == "INV-lumen-2026-002-001"
               for p in rec["proposals"]), f)
    _check("reconcile: unrelated row stays unmatched",
           any(r["row_description"].startswith("COFFEE") for r in rec["unmatched_rows"]), f)
    _check("reconcile: paid invoices never proposed",
           all(p["invoice_id"] != "INV-x-old" for p in rec["proposals"]), f)
    _check("reconcile: proposal-only with human review",
           rec["human_review_required"] is True and "proposal only" in rec["note"], f)
    two_rows = [{"Date": "2026-07-30", "Description": "wire", "Amount": "2750.00"},
                {"Date": "2026-07-31", "Description": "HEARTHLINE payment", "Amount": "2750.00"}]
    rec2 = reconcile(two_rows, rec_invoices[:1], window_days=5)
    _check("reconcile: each invoice matched at most once, best tier wins",
           len(rec2["proposals"]) == 1 and rec2["proposals"][0]["confidence"] == "exact"
           and rec2["proposals"][0]["row_index"] == 1, f)
    _check("reconcile: negative parenthesized amounts parse",
           _flex_amount("(4.50)") == Decimal("-4.50"), f)
    _check("reconcile: tolerance promotes near-miss to uncertain",
           any(p["confidence"] == "uncertain" for p in
               reconcile([{"Date": "2026-07-31", "Description": "wire", "Amount": "2749.00"}],
                         rec_invoices[:1], amount_tolerance="1.00")["proposals"]), f)
    _check("reconcile: unparseable row becomes a gap, not a guess",
           any(g["gap_type"] == "unparseable_row" for g in
               reconcile([{"Date": "not a date", "Description": "x", "Amount": "??"}],
                         rec_invoices[:1])["gaps"]), f)
    try:
        _csv_rows(str(ROOT / "pipeline" / "finance" / "bank.csv"))
        refused = False
    except PermissionError:
        refused = True
    _check("reconcile: in-repo CSV without .local. is REFUSED (structural boundary)", refused, f)
    import tempfile as _tf
    with _tf.TemporaryDirectory() as td:
        outside = Path(td) / "export.csv"
        outside.write_text("Date,Description,Amount\n2026-07-30,HEARTHLINE,2750.00\n",
                           encoding="utf-8")
        ok_outside = len(reconcile(str(outside), rec_invoices[:1])["proposals"]) == 1
    _check("reconcile: CSV outside the repo is allowed", ok_outside, f)
    mp = mark_paid("INV-hearthline-2026-001-001", "2026-07-30",
                   config={"capabilities": {}})
    _check("mark_paid: refused with finance_management off, record untouched",
           mp["updated"] is False and "finance_management" in mp["reason"], f)

    n = getattr(_check, "count", 0)
    print(f"selftest: {'PASS' if not f else 'FAIL'} ({n - len(f)} of {n} checks)")
    return 0 if not f else 1


# ── CLI ──────────────────────────────────────────────────────────────────────

def _read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main(argv):
    ap = argparse.ArgumentParser(description="Creator OS offline finance math")
    ap.add_argument("--ar-scan", nargs="?", const="__local__", metavar="INVOICES_JSON")
    ap.add_argument("--cashflow", nargs="?", const="__local__", metavar="INPUTS_JSON")
    ap.add_argument("--reconcile", metavar="CSV_PATH")
    ap.add_argument("--window-days", type=int, default=5)
    ap.add_argument("--amount-tolerance", default="0.00")
    ap.add_argument("--mark-paid", metavar="INVOICE_ID")
    ap.add_argument("--paid-date", metavar="YYYY-MM-DD")
    ap.add_argument("--method", metavar="PAYMENT_METHOD")
    ap.add_argument("--horizon-days", type=int, default=90)
    ap.add_argument("--redacted", action="store_true",
                    help="band amounts and initial names for output that leaves this machine")
    ap.add_argument("--build-invoice", metavar="PAYLOAD_JSON")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--accrue", metavar="INVOICE_JSON")
    ap.add_argument("--revshare", metavar="PAYLOAD_JSON")
    ap.add_argument("--rollup", metavar="ESTIMATE_JSON")
    ap.add_argument("--price", metavar="PAYLOAD_JSON")
    ap.add_argument("--price-package", dest="price_package", metavar="PAYLOAD_JSON")
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
        result = ar_scan(invoices, today)
        print(json.dumps(redact(result) if args.redacted else result, indent=2))
        return 0
    if args.cashflow:
        inputs = {} if args.cashflow == "__local__" else _read_json(args.cashflow)
        result = cashflow(inputs.get("invoices"), inputs.get("scheduled"),
                          inputs.get("estimates"), args.horizon_days, today)
        print(json.dumps(redact(result) if args.redacted else result, indent=2))
        return 0
    if args.reconcile:
        result = reconcile(args.reconcile, None, args.window_days, args.amount_tolerance,
                           today=today)
        print(json.dumps(redact(result) if args.redacted else result, indent=2))
        return 0
    if args.mark_paid:
        if not args.paid_date:
            print(json.dumps({"error": "--mark-paid requires --paid-date YYYY-MM-DD"}))
            return 1
        print(json.dumps(mark_paid(args.mark_paid, args.paid_date, args.method), indent=2))
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
        rate_floor = p.get("rate_floor")
        rate_floor_source = "payload" if rate_floor is not None else None
        extra_gaps = []
        card = None
        if rate_floor is None and p.get("format") or p.get("benchmark_range"):
            card, _src = load_rate_card()
        if rate_floor is None and p.get("format"):
            rate_floor, rc_gap = rate_floor_for(card, p["format"])
            if rate_floor is not None:
                rate_floor_source = "rate_card"
            elif rc_gap:
                extra_gaps.append(rc_gap)
        res = proposal_price(p.get("cost_total"), p.get("margin_percent"),
                             rate_floor, p.get("benchmark_range"))
        res["rate_floor_source"] = rate_floor_source
        if extra_gaps:
            # no_rate_card_entry already names the exact fix; drop the generic missing_input twin.
            res["gaps"] = [g for g in res.get("gaps", []) if g.get("gap_type") != "missing_input"]
        res["gaps"] = res.get("gaps", []) + extra_gaps + _tier_gaps(
            card, p.get("benchmark_range"), p.get("benchmark_tier"))
        print(json.dumps(res, indent=2))
        return 0
    if args.price_package:
        p = _read_json(args.price_package)
        print(json.dumps(price_package(p), indent=2))
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
