#!/usr/bin/env python3
"""Creator income ledger: money and product RECEIVED for the content business (P103).

The third instance of the offline money lane beside tools/finance.py (invoices, AR, cash flow) and
tools/obligations.py (dated duties): stdlib only, exact Decimal arithmetic, CREATOR_OS_ROOT sandbox
override, read-only reports always on, writes gated by finance_management, a selftest, and the
verbatim boundary on every report. It owns ONE record, pipeline/finance/income-ledger.local.json
(blank schema: income-ledger.template.json), and reads the paid invoices finance.py keeps so a
payment already tracked there becomes a ledger entry without retyping.

What it does: propose, confirm and void entries; per-payer and per-month summaries for a tax year;
the gift register (every product entry with its price source and where it was featured); a check of
each 1099 the human enters against the ledger's cash total for that payer; a CSV export at a
gitignored .local. path under pipeline/finance/; a set-aside figure (year-to-date net times a
percentage the human sets).
What it never does: estimate a product's value, decide deductibility, name a tax line, or send
anything anywhere. Every figure comes from a record, a receipt the human approved, or the human.

CLI (a relative --out path is read from the repository root):
  python3 tools/books.py --summary --year 2026 [--redacted]
  python3 tools/books.py --gifts --year 2026
  python3 tools/books.py --form-check --year 2026
  python3 tools/books.py --propose-from-invoices [--write]
  python3 tools/books.py --add entry.json [--write]
  python3 tools/books.py --add-cost entry.json [--write]   # a spending entry (cost actuals)
  python3 tools/books.py --confirm <entry_id> | --void <entry_id>
  python3 tools/books.py --export --year 2026 [--out pipeline/finance/exports/2026-books.local.csv]
  python3 tools/books.py --set-aside --year 2026 --percent 27.5
  python3 tools/books.py --selftest
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import sys
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import finance as _fin  # noqa: E402  (money(), redact(), _band, _initials, _load_local_invoices)
import obligations as _ob  # noqa: E402  (load_config, flag_enabled)
import env_paths  # noqa: E402  (utf8_stdio for the CLI's output)
from atomic_io import atomic_write_text as _atomic_write_text, locked as _locked  # noqa: E402

TOOL = "tools/books.py"
BOUNDARY = ("ARITHMETIC AND RESEARCH NOTES. NOT TAX, ACCOUNTING, OR INVESTMENT ADVICE. REVIEW WITH "
            "A CPA OR TAX PROFESSIONAL BEFORE FILING OR RELYING ON CATEGORIZATIONS.")
KINDS = ("cash", "product", "affiliate", "ad_revenue", "revenue_share", "refund")
PAYER_TYPES = ("brand", "platform", "affiliate_network", "agency", "other")
PRICE_SOURCES = ("brand_page", "retailer_page", "user_stated")
STATUSES = ("proposed", "confirmed", "void")
SOURCES = ("invoice_paid", "receipt_extract", "user_entry", "platform_statement")
CASH_KINDS = ("cash", "affiliate", "ad_revenue", "revenue_share", "refund")
_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}\Z")
# The ledger's money keys that redact() bands; finance.redact bands its own (amount, net, ...).
_LEDGER_AMOUNT_KEYS = ("cash", "product_value", "retail_price", "value", "form_amount", "ledger_cash",
                       "difference", "income", "cost_actuals", "set_aside")


def _root():
    return Path(os.environ.get("CREATOR_OS_ROOT", str(HERE.parent)))


def ledger_path():
    return _root() / "pipeline" / "finance" / "income-ledger.local.json"


def _empty():
    return {"_schema_version": "0.1.0", "currency": "USD", "entries": [], "forms_received": [],
            "human_review_required": True, "last_updated": None}


def load_ledger(path=None):
    """The ledger, or an empty one when the file is missing. A file that does not parse (an empty
    file included) or is not the ledger's shape raises ValueError: the caller must not overwrite a
    record it could not read (the inbox ledger's rule)."""
    p = Path(path) if path else ledger_path()
    if not p.exists():
        return _empty()
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise ValueError(f"{p} does not parse as JSON ({exc}); it was left as it is") from None
    if not isinstance(data, dict) or not isinstance(data.get("entries"), list):
        raise ValueError(f"{p} is not an income ledger (an object with an entries list)")
    if not isinstance(data.setdefault("forms_received", []), list):
        raise ValueError(f"{p} is not an income ledger (forms_received is not a list)")
    return data


def _save(data, path=None):
    p = Path(path) if path else ledger_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    data["last_updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    _atomic_write_text(p, json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def _write_allowed(config=None):
    cfg = config if config is not None else _ob.load_config()
    if not _ob.flag_enabled(cfg, "finance_management"):
        return False, ("finance_management is off; the entry was validated but not written "
                       "(see degraded_behavior.finance_management_disabled)")
    return True, "ok"


def write_flag(value):
    """True only for True or the text "true" (any case): the MCP tool's write argument, where a
    string "false" must not read as a write."""
    return value is True or (isinstance(value, str) and value.strip().lower() == "true")


def _num(x, field):
    """x as an exact Decimal, or ValueError naming the field (never the value, so a redacted
    report that carries the message carries no figure): None, an empty string, a bool, text
    Decimal cannot read ("$100", "27,5"), NaN or infinity, and a number too large to hold in
    cents are refused, never guessed."""
    if x is None or x == "" or isinstance(x, bool):
        raise ValueError(f"{field} is required and must be a number")
    try:
        d = Decimal(str(x).strip())
    except InvalidOperation:
        raise ValueError(f"{field} must be a number (digits, with an optional decimal point)") from None
    if not d.is_finite():
        raise ValueError(f"{field} must be a finite number")
    try:
        d.quantize(_fin.CENT)
    except InvalidOperation:
        raise ValueError(f"{field} is too large") from None
    return d


def _iso_date(x):
    """A date written exactly YYYY-MM-DD, else ValueError (date.fromisoformat alone also takes
    20260304 and week dates)."""
    s = x if isinstance(x, str) else ""
    if not _DATE_RE.match(s):
        raise ValueError(f"not YYYY-MM-DD: {x!r}")
    return date.fromisoformat(s)


def _name_key(x):
    """A payer or item name compared without case or extra spaces."""
    return " ".join(str(x or "").split()).casefold()


def _quantity(prod):
    """A product's quantity as a whole number of 1 or more; 1 when it is not given; None when a
    hand-written entry stores something else (the item then counts as unpriced, never valued)."""
    q = prod.get("quantity", 1)
    if q is None:
        q = 1
    return q if isinstance(q, int) and not isinstance(q, bool) and q >= 1 else None


def entry_id_for(entry):
    """Deterministic id: BK-<yyyymmdd>-<8 hex of the fields that make an entry the same event>, so
    the same receipt or invoice proposed twice is one entry, never two. Payer and item are compared
    without case or extra spaces; a second identical payment on the same day is told apart by its
    evidence reference or by sequence 2, 3 and so on."""
    parts = [str(entry.get(k) or "") for k in ("date", "payer", "kind", "amount", "invoice_id",
                                                "evidence_sha256", "evidence_ref", "sequence")]
    parts[1] = _name_key(entry.get("payer"))
    if entry.get("kind") == "product":
        prod = entry.get("product") or {}
        parts += [_name_key(prod.get("item")), str(prod.get("quantity") or ""), str(prod.get("retail_price") or "")]
    key = "|".join(parts)
    d = str(entry.get("date") or "00000000").replace("-", "")
    return f"BK-{d}-{hashlib.sha256(key.encode('utf-8')).hexdigest()[:8]}"


def validate_entry(entry, today=None):
    """Problems with a proposed entry; empty means it may be written. The product rule: a retail
    price needs a source and a capture date, and a brand or retailer source needs its reference
    (the page), else the price is refused (no-fabrication). An amount is refused on a product
    entry (the value lives in product.retail_price) and required on every cash kind: positive,
    and negative for a refund. Dates are YYYY-MM-DD and not after today."""
    today = today or date.today()
    p = []
    if not isinstance(entry, dict):
        return ["entry is not an object"]
    try:
        if _iso_date(entry.get("date")) > today:
            p.append("date is after today; an entry is recorded once the payment or product arrived")
    except ValueError:
        p.append("date must be YYYY-MM-DD")
    payer = entry.get("payer")
    if not isinstance(payer, str) or not payer.strip():
        p.append("payer is required (the name of who paid or sent it)")
    if entry.get("payer_type") not in PAYER_TYPES:
        p.append(f"payer_type must be one of {PAYER_TYPES}")
    kind = entry.get("kind")
    if kind not in KINDS:
        p.append(f"kind must be one of {KINDS}")
    if entry.get("source") not in SOURCES:
        p.append(f"source must be one of {SOURCES}")
    seq = entry.get("sequence")
    if seq is not None and (isinstance(seq, bool) or not isinstance(seq, int) or seq < 2):
        p.append("sequence must be a whole number of 2 or more (the second identical payment that day is 2)")
    if kind in CASH_KINDS:
        try:
            amt = _num(entry.get("amount"), "amount")
            if kind == "refund" and amt >= 0:
                p.append("a refund's amount must be negative (it subtracts from the payer's cash)")
            elif kind != "refund" and amt <= 0:
                p.append("amount must be positive for a cash kind")
        except ValueError as exc:
            p.append(str(exc))
    if kind == "product":
        if entry.get("amount") not in (None, ""):
            p.append("a product entry carries its value in product.retail_price, not amount")
        prod = entry.get("product")
        if not isinstance(prod, dict):
            prod = {}
        item = prod.get("item")
        if not isinstance(item, str) or not item.strip():
            p.append("product.item is required")
        q = prod.get("quantity")
        if q is not None and (isinstance(q, bool) or not isinstance(q, int) or q < 1):
            p.append("product.quantity must be a whole number of 1 or more when given")
        price = prod.get("retail_price")
        if price not in (None, ""):
            try:
                if _num(price, "product.retail_price") <= 0:
                    p.append("product.retail_price must be positive")
            except ValueError as exc:
                p.append(str(exc))
            src = prod.get("price_source")
            if src not in PRICE_SOURCES:
                p.append(f"product.price_source must be one of {PRICE_SOURCES} when a price is given")
            elif src != "user_stated" and not prod.get("price_source_ref"):
                p.append("product.price_source_ref (the page) is required for a brand or retailer price")
            try:
                cap = _iso_date(prod.get("price_captured_at"))
                if cap > today:
                    p.append("product.price_captured_at is after today")
            except ValueError:
                p.append("product.price_captured_at must be YYYY-MM-DD when a price is given")
    return p


def normalize(entry):
    """A validated entry in its stored shape: payer and item with single spaces, quantized amounts
    as strings, tax_year from the date, deterministic id, status proposed (a confirm is the
    human's own step, whatever the input says), quantity 1 when not given, and a gap for a product
    with no price."""
    e = json.loads(json.dumps(entry))
    e["payer"] = " ".join(e["payer"].split())
    e["tax_year"] = int(e["date"][:4])
    e["amount"] = str(_fin.money(_num(e["amount"], "amount"))) if e.get("kind") in CASH_KINDS else None
    if e.get("kind") == "product":
        prod = dict(e.get("product") or {})
        prod["item"] = " ".join(prod["item"].split())
        if prod.get("retail_price") not in (None, ""):
            prod["retail_price"] = str(_fin.money(_num(prod["retail_price"], "product.retail_price")))
        else:
            prod["retail_price"] = None
            e.setdefault("gaps", []).append(
                "retail_price: provide the brand or retailer page for this item, or state the price")
        if prod.get("quantity") is None:
            prod["quantity"] = 1
        prod.setdefault("disposition", "kept")
        e["product"] = prod
    else:
        e["product"] = None
    e["status"] = "proposed"
    e.setdefault("confidence", "exact" if e.get("source") in ("invoice_paid", "user_entry") else "probable")
    e.setdefault("gaps", [])
    e.setdefault("content_refs", [])
    e.setdefault("notes", "")
    e["entry_id"] = entry_id_for(e)
    return e


def add_entry(entry, write=False, config=None, path=None):
    """Validate, normalize and (with write and the gate open) append one entry. A duplicate id is
    reported, not appended. Returns the normalized entry plus what happened."""
    problems = validate_entry(entry)
    if problems:
        return {"boundary": BOUNDARY, "written": False, "problems": problems, "human_review_required": True}
    e = normalize(entry)
    out = {"boundary": BOUNDARY, "entry": e, "written": False, "human_review_required": True,
           "computed_by": f"{TOOL} add_entry"}
    if not write:
        out["reason"] = "dry run; pass write=True to persist"
        return out
    ok, why = _write_allowed(config)
    if not ok:
        out["reason"] = why
        return out
    p = Path(path) if path else ledger_path()
    with _locked(p):
        data = load_ledger(p)
        if any(x.get("entry_id") == e["entry_id"] for x in data["entries"]):
            out["reason"] = (f"duplicate: {e['entry_id']} is already in the ledger (a second identical "
                             f"payment that day needs its evidence_ref or sequence 2)")
            return out
        data["entries"].append(e)
        _save(data, p)
    out["written"] = True
    return out


def set_status(entry_id, status, config=None, path=None):
    """confirm or void one entry (the human's click). Gated like every write."""
    if status not in ("confirmed", "void"):
        return {"updated": False, "reason": "status must be confirmed or void"}
    ok, why = _write_allowed(config)
    if not ok:
        return {"updated": False, "reason": why}
    p = Path(path) if path else ledger_path()
    with _locked(p):
        data = load_ledger(p)
        for e in data["entries"]:
            if e.get("entry_id") == entry_id:
                e["status"] = status
                _save(data, p)
                return {"updated": True, "entry_id": entry_id, "status": status,
                        "computed_by": f"{TOOL} set_status"}
    return {"updated": False, "reason": f"no entry {entry_id}"}


COST_CATEGORIES = ("production_materials", "equipment_capex", "software_subscriptions", "contractor_labor",
                   "travel", "shipping_and_fees")


def cost_actuals_path():
    return _root() / "pipeline" / "finance" / "cost-actuals.local.json"


def add_cost_actual(entry, write=False, config=None, path=None, today=None):
    """Validate and (with write and finance_management on) append one spending entry to
    pipeline/finance/cost-actuals.local.json under its lock, written atomically. The fields are the
    template's (date, vendor, description, category, amount, is_capex, project_ref, deal_id,
    receipt_ref, notes) plus receipt_sha256; an entry whose receipt_sha256 is already recorded is
    refused as a duplicate. category is one of COST_CATEGORIES or null; it is the person's choice."""
    p_ = []
    e = dict(entry) if isinstance(entry, dict) else None
    if e is None:
        return {"boundary": BOUNDARY, "written": False, "problems": ["entry is not an object"],
                "human_review_required": True}
    try:
        if _iso_date(e.get("date")) > (today or date.today()):
            p_.append("date is after today; an entry is recorded once the money was spent")
    except ValueError:
        p_.append("date must be YYYY-MM-DD")
    if not isinstance(e.get("vendor"), str) or not e["vendor"].strip():
        p_.append("vendor is required (who was paid)")
    try:
        if _num(e.get("amount"), "amount") <= 0:
            p_.append("amount must be positive")
    except ValueError as exc:
        p_.append(str(exc))
    if e.get("category") not in (None, "") + COST_CATEGORIES:
        p_.append(f"category must be one of {COST_CATEGORIES} or empty")
    if not isinstance(e.get("is_capex", False), bool):
        p_.append("is_capex must be true or false")
    if p_:
        return {"boundary": BOUNDARY, "written": False, "problems": p_, "human_review_required": True}
    e["vendor"] = " ".join(e["vendor"].split())
    e["amount"] = str(_fin.money(_num(e["amount"], "amount")))
    e["category"] = e.get("category") or None
    e.setdefault("is_capex", False)
    for k in ("description", "notes"):
        e[k] = str(e.get(k) or "")
    for k in ("project_ref", "deal_id", "receipt_ref", "receipt_sha256"):
        e.setdefault(k, None)
    out = {"boundary": BOUNDARY, "entry": e, "written": False, "human_review_required": True,
           "computed_by": f"{TOOL} add_cost_actual"}
    if not write:
        out["reason"] = "dry run; pass write=True to persist"
        return out
    ok, why = _write_allowed(config)
    if not ok:
        out["reason"] = why.replace("entry was validated", "spending entry was validated")
        return out
    p = Path(path) if path else cost_actuals_path()
    with _locked(p):
        try:
            data = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
        except ValueError:
            out["reason"] = f"{p.name} does not parse as JSON; it was left as it is"
            return out
        if not isinstance(data, dict) or not isinstance(data.get("entries", []), list):
            out["reason"] = f"{p.name} is not an object with an entries list; it was left as it is"
            return out
        data.setdefault("currency", "USD")
        data.setdefault("entries", [])
        data.setdefault("human_review_required", True)
        if e["receipt_sha256"] and any(isinstance(x, dict) and x.get("receipt_sha256") == e["receipt_sha256"]
                                       for x in data["entries"]):
            out["reason"] = "duplicate: this receipt is already recorded in cost actuals"
            return out
        data["entries"].append(e)
        _save(data, p)
    out["written"] = True
    return out


def propose_from_invoices(invoices=None, ledger=None, skipped=None):
    """Proposed entries for paid invoices the ledger does not hold yet (keyed by invoice_id). Pure:
    the caller decides whether to write them. The payment date and method come from the invoice
    record finance.mark_paid wrote; the amount is its total. A paid invoice that does not make a
    valid entry (no date, no total, no payer name) is appended to `skipped` with its problems."""
    invoices = _fin._load_local_invoices() if invoices is None else invoices
    ledger = load_ledger() if ledger is None else ledger
    seen = {e.get("invoice_id") for e in ledger["entries"] if e.get("invoice_id")}
    out = []
    for inv in invoices:
        if inv.get("status") != "paid" or inv.get("invoice_id") in seen:
            continue
        e = {"date": inv.get("payment_received_date"), "payer": inv.get("brand_name") or inv.get("account_ref"),
             "payer_type": "brand", "kind": "cash", "amount": inv.get("total"),
             "deal_id": inv.get("deal_id"), "invoice_id": inv.get("invoice_id"),
             "payment_method": inv.get("payment_method"), "source": "invoice_paid",
             "notes": f"from paid invoice {inv.get('invoice_id')}"}
        problems = validate_entry(e)
        if problems:
            if skipped is not None:
                skipped.append({"invoice_id": inv.get("invoice_id"), "problems": problems})
            continue
        out.append(normalize(e))
    return out


def _live(entries, year):
    return [e for e in entries if e.get("status") != "void" and e.get("tax_year") == year]


def _dec(x, field="amount"):
    return _fin.money(_num(x, field)) if x not in (None, "") else Decimal("0.00")


def _product_value(e):
    prod = e.get("product") or {}
    q = _quantity(prod)
    if prod.get("retail_price") in (None, "") or q is None:
        return None
    return _fin.money(_num(prod["retail_price"], "product.retail_price") * q)


def payer_summary(year, ledger=None):
    """Per payer (names compared without case or extra spaces, shown as first written): cash
    received (refunds subtract), product value received (priced items only), the count of
    unpriced items, entries awaiting confirmation; plus per-month cash and the year totals.
    Confirmed and proposed entries both count, each flagged; void ones never."""
    ledger = load_ledger() if ledger is None else ledger
    live = _live(ledger["entries"], year)
    payers, months, shown = {}, {}, {}
    totals = {"cash": Decimal("0.00"), "product_value": Decimal("0.00"), "unpriced_items": 0,
              "proposed": 0, "confirmed": 0}
    for e in live:
        name = shown.setdefault(_name_key(e.get("payer")), e.get("payer") or "(no payer)")
        row = payers.setdefault(name, {"payer_type": e.get("payer_type"), "cash": Decimal("0.00"),
                                       "product_value": Decimal("0.00"), "items": 0,
                                       "unpriced_items": 0, "proposed": 0, "entries": 0})
        row["entries"] += 1
        row["proposed"] += e.get("status") == "proposed"
        totals["proposed" if e.get("status") == "proposed" else "confirmed"] += 1
        if e.get("kind") in CASH_KINDS:
            amt = _dec(e.get("amount"))
            row["cash"] += amt
            totals["cash"] += amt
            m = str(e.get("date") or "undated")[:7]
            months[m] = months.get(m, Decimal("0.00")) + amt
        elif e.get("kind") == "product":
            row["items"] += _quantity(e.get("product") or {}) or 0
            v = _product_value(e)
            if v is None:
                row["unpriced_items"] += 1
                totals["unpriced_items"] += 1
            else:
                row["product_value"] += v
                totals["product_value"] += v
    for row in payers.values():
        row["cash"], row["product_value"] = str(row["cash"]), str(row["product_value"])
    return {"boundary": BOUNDARY, "tax_year": year, "currency": ledger.get("currency", "USD"),
            "payers": dict(sorted(payers.items())),
            "by_month": {k: str(v) for k, v in sorted(months.items())},
            "totals": {k: (str(v) if isinstance(v, Decimal) else v) for k, v in totals.items()},
            "human_review_required": True, "computed_by": f"{TOOL} payer_summary"}


def gift_register(year, ledger=None):
    """Every product entry for the year with its price, price source and where it was featured;
    unpriced items listed first so the human sees what still needs a source."""
    ledger = load_ledger() if ledger is None else ledger
    rows = []
    for e in _live(ledger["entries"], year):
        if e.get("kind") != "product":
            continue
        prod = e.get("product") or {}
        v = _product_value(e)
        rows.append({"entry_id": e.get("entry_id"), "date": e.get("date"), "payer": e.get("payer"),
                     "item": prod.get("item"), "quantity": prod.get("quantity"),
                     "retail_price": prod.get("retail_price"), "value": str(v) if v is not None else None,
                     "price_source": prod.get("price_source") if v is not None else None,
                     "price_source_ref": prod.get("price_source_ref") if v is not None else None,
                     "disposition": prod.get("disposition"), "content_refs": e.get("content_refs", []),
                     "status": e.get("status"), "gaps": e.get("gaps", [])})
    rows.sort(key=lambda r: (r["value"] is not None, str(r["date"])))
    return {"boundary": BOUNDARY, "tax_year": year, "items": rows,
            "unpriced": sum(1 for r in rows if r["value"] is None),
            "human_review_required": True, "computed_by": f"{TOOL} gift_register"}


def _form_year(f):
    try:
        return int(f.get("tax_year"))
    except (TypeError, ValueError):
        return None


def form_check(year, ledger=None):
    """Each form in forms_received for the year against the ledger's cash total for that payer
    (names compared without case or extra spaces), plus payers with cash and no form. A difference
    is reported, never explained: the usual causes (a form shows gross before platform fees; a
    payment processor's 1099-K repeats a brand's own 1099-NEC) are for the human and the CPA to
    resolve. A form whose amount is not a number is listed with the problem, not compared."""
    ledger = load_ledger() if ledger is None else ledger
    summary = payer_summary(year, ledger)
    by_key = {_name_key(p): r for p, r in summary["payers"].items()}
    forms = [f for f in ledger.get("forms_received", []) if _form_year(f) == year]
    rows, covered = [], set()
    for f in forms:
        payer = f.get("payer")
        covered.add(_name_key(payer))
        ledger_cash = Decimal(by_key.get(_name_key(payer), {}).get("cash", "0.00"))
        try:
            form_amt = _fin.money(_num(f.get("amount"), f"the {f.get('form') or 'form'} amount"))
        except ValueError as exc:
            rows.append({"payer": payer, "form": f.get("form"), "ledger_cash": str(ledger_cash),
                         "matches": None, "problem": str(exc)})
            continue
        rows.append({"payer": payer, "form": f.get("form"), "form_amount": str(form_amt),
                     "ledger_cash": str(ledger_cash), "difference": str(_fin.money(form_amt - ledger_cash)),
                     "matches": form_amt == ledger_cash})
    missing = [{"payer": p, "ledger_cash": r["cash"]} for p, r in summary["payers"].items()
               if _name_key(p) not in covered and Decimal(r["cash"]) != 0]
    return {"boundary": BOUNDARY, "tax_year": year, "forms": rows, "payers_without_form": missing,
            "human_review_required": True, "computed_by": f"{TOOL} form_check"}


def _percent(x):
    """The human's percentage: a number, optionally followed by %; "27,5" is refused, not read."""
    s = str(x).strip() if isinstance(x, (str, int, float, Decimal)) and not isinstance(x, bool) else ""
    if s.endswith("%"):
        s = s[:-1].strip()
    return _num(s, "percent")


def set_aside(year, percent, ledger=None, cost_actuals=None):
    """Year-to-date net (ledger cash plus priced product value, minus cost actuals for the year)
    times the percentage the human gives. Arithmetic only: no default percentage exists, the
    boundary line travels with the result, and the human chose the rate."""
    pct = _percent(percent)
    if pct <= 0 or pct >= 100:
        raise ValueError("percent must be between 0 and 100, chosen by the human")
    summary = payer_summary(year, ledger)
    if cost_actuals is None:
        ca_path = _root() / "pipeline" / "finance" / "cost-actuals.local.json"
        cost_actuals = json.loads(ca_path.read_text(encoding="utf-8")) if ca_path.exists() else {"entries": []}
    spend = sum((_dec(e.get("amount"), f"the cost-actuals amount dated {e.get('date')}")
                 for e in cost_actuals.get("entries", [])
                 if str(e.get("date") or "")[:4] == str(year) and e.get("amount") not in (None, "")),
                Decimal("0.00"))
    income = Decimal(summary["totals"]["cash"]) + Decimal(summary["totals"]["product_value"])
    net = _fin.money(income - spend)
    return {"boundary": BOUNDARY, "tax_year": year, "income": str(_fin.money(income)),
            "cost_actuals": str(_fin.money(spend)), "net": str(net), "percent": str(pct),
            "set_aside": str(_fin.money(max(net, Decimal(0)) * pct / Decimal(100))),
            "note": "the percentage is the human's choice; this is not a tax computation",
            "human_review_required": True, "computed_by": f"{TOOL} set_aside"}


def _gifts_name(name):
    """The gift register's file name beside an income export: -income becomes -gifts, else -gifts
    goes before the first dot (books.local.csv gives books-gifts.local.csv)."""
    if "-income" in name:
        return name.replace("-income", "-gifts", 1)
    head, dot, rest = name.partition(".")
    return f"{head}-gifts.{rest}" if dot else f"{name}-gifts"


def _under(path, top, samefile=os.path.samefile):
    """True when path, resolved, lies in top: by its name, or by the identity of a folder on its
    way up that exists (so a path spelled in another case on a filesystem that ignores case, as
    macOS does by default, still counts as inside)."""
    p, t = Path(path).resolve(), Path(top).resolve()
    if p.is_relative_to(t):
        return True
    for a in (p, *p.parents):
        try:
            if a.exists() and samefile(a, t):
                return True
        except OSError:
            continue
    return False


def _export_refusal(path, root):
    """Why an export may not be written at path, or None. Inside the repo it must be a .local.csv
    file under pipeline/finance/, where git ignores it (judged on the resolved path, so a link
    cannot point it elsewhere). Anywhere, an existing file is replaced only when it is an earlier
    export (its first line is the boundary line), so a ledger, an invoice or any other file is
    never overwritten."""
    real = Path(path).resolve()
    if _under(real, root):
        if not (real.name.endswith(".csv") and ".local." in real.name):
            return f"an export inside the repo must be a .local.csv file ({real.name})"
        if not _under(real, Path(root) / "pipeline" / "finance"):
            return f"an export inside the repo goes under pipeline/finance/, where git ignores it ({real})"
    if real.exists():
        try:
            with open(real, encoding="utf-8", errors="replace") as fh:
                first = fh.readline().rstrip("\r\n")
        except OSError as exc:
            return f"{real.name} could not be read to check that it is an earlier export ({exc})"
        if first != BOUNDARY:
            return f"{real.name} exists and is not an earlier export; it was left as it is"
    return None


def export_csv(year, out_path=None, ledger=None):
    """Two CSV files for the CPA: <year>-income.local.csv (every live entry) and
    <year>-gifts.local.csv (the register), by default under pipeline/finance/exports/. A relative
    out path is read from the repository root. Each file passes _export_refusal before either is
    written: inside the repo a .local.csv file under pipeline/finance/, and anywhere a file that
    already exists only when it is an earlier export."""
    ledger = load_ledger() if ledger is None else ledger
    root = _root()
    base = Path(out_path) if out_path else root / "pipeline" / "finance" / "exports" / f"{year}-income.local.csv"
    if not base.is_absolute():
        base = root / base
    gifts = base.with_name(_gifts_name(base.name))
    for target in (base, gifts):
        why = _export_refusal(target, root)
        if why:
            raise ValueError(f"refused: {why}")
    base.parent.mkdir(parents=True, exist_ok=True)
    cols = ["entry_id", "status", "date", "payer", "payer_type", "kind", "amount", "item", "quantity",
            "retail_price", "price_source", "price_source_ref", "deal_id", "invoice_id", "evidence_ref",
            "payment_method", "source", "confidence", "notes"]
    live = sorted(_live(ledger["entries"], year), key=lambda e: str(e.get("date")))
    with open(base, "w", newline="", encoding="utf-8") as fh:
        fh.write(BOUNDARY + "\n")  # the first line, unquoted, so a reader sees it before any figure
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for e in live:
            prod = e.get("product") or {}
            w.writerow({**e, "item": prod.get("item"), "quantity": prod.get("quantity"),
                        "retail_price": prod.get("retail_price"), "price_source": prod.get("price_source"),
                        "price_source_ref": prod.get("price_source_ref")})
    reg = gift_register(year, ledger)
    gcols = ["entry_id", "date", "payer", "item", "quantity", "retail_price", "value", "price_source",
             "price_source_ref", "disposition", "status"]
    with open(gifts, "w", newline="", encoding="utf-8") as fh:
        fh.write(BOUNDARY + "\n")
        w = csv.DictWriter(fh, fieldnames=gcols, extrasaction="ignore")
        w.writeheader()
        for r in reg["items"]:
            w.writerow(r)
    return {"boundary": BOUNDARY, "income_csv": str(base), "gifts_csv": str(gifts), "rows": len(live),
            "gift_rows": len(reg["items"]), "human_review_required": True, "computed_by": f"{TOOL} export_csv"}


def redact(obj):
    """finance.redact (its own amount and name keys) plus the ledger's: the amounts under
    _LEDGER_AMOUNT_KEYS and each by_month figure banded, payer and item initialed (the payers
    table's keys too), page and evidence references, content references and notes hidden."""
    out = _fin.redact(obj)

    def walk(x):
        if isinstance(x, list):
            return [walk(v) for v in x]
        if not isinstance(x, dict):
            return x
        res = {}
        for k, v in x.items():
            if k in ("price_source_ref", "evidence_ref") and v:
                res[k] = "[ref]"
            elif k in ("payer", "item") and isinstance(v, str):
                res[k] = _fin._initials(v)
            elif k in _LEDGER_AMOUNT_KEYS and not isinstance(v, (dict, list)):
                res[k] = _fin._band(v) if v is not None else None
            elif k == "by_month" and isinstance(v, dict):
                res[k] = {m: _fin._band(a) for m, a in v.items()}
            elif k == "content_refs" and isinstance(v, list):
                res[k] = ["[ref]"] * len(v)
            elif k == "notes" and isinstance(v, str) and v:
                res[k] = "[note]"
            else:
                res[k] = walk(v)
        return res
    out = walk(out)
    if isinstance(out, dict) and isinstance(out.get("payers"), dict):
        keyed = {}
        for k, v in out["payers"].items():
            ini = _fin._initials(k)
            key, n = ini, 2
            while key in keyed:  # two payers with the same initials stay two rows
                key, n = f"{ini} {n}", n + 1
            keyed[key] = v
        out["payers"] = keyed
    return out


# ── selftest ─────────────────────────────────────────────────────────────────

def selftest():
    import tempfile
    import file_hash
    f = []
    _c = _fin._check
    start = getattr(_c, "count", 0)
    on = {"capabilities": {"finance_management": {"enabled": True}}}
    off = {"capabilities": {"finance_management": {"enabled": False}}}
    decimal_figure = re.compile(r"\d+\.\d\d")

    def cash(**kw):
        base = {"date": "2026-03-04", "payer": "Hearthline Paint", "payer_type": "brand", "kind": "cash",
                "amount": "1250", "source": "user_entry"}
        base.update(kw)
        return base

    def product(**kw):
        base = {"date": "2026-05-11", "payer": "Northstar Tools", "payer_type": "brand", "kind": "product",
                "source": "user_entry",
                "product": {"item": "cordless brad nailer", "quantity": 1, "retail_price": "199.99",
                            "price_source": "brand_page", "price_source_ref": "https://example.com/nailer",
                            "price_captured_at": "2026-05-11"}}
        base.update(kw)
        return base

    def priced(**kw):
        e = product()
        e["product"] = dict(e["product"], **kw)
        return e

    def problems_with(entry, text):
        return any(text in p for p in validate_entry(entry))

    band_labels = sorted({name for _edge, name in _fin._BANDS} | {"over 50k"}, key=len, reverse=True)

    def figures(obj, key=None, out=None):
        """The whole-number part of each figure under the ledger's and finance's amount keys."""
        out = set() if out is None else out
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k == "by_month" and isinstance(v, dict):
                    out.update(str(abs(int(Decimal(a)))) for a in v.values())
                else:
                    figures(v, k, out)
        elif isinstance(obj, list):
            for v in obj:
                figures(v, key, out)
        elif key in _LEDGER_AMOUNT_KEYS + ("amount", "net") and obj not in (None, ""):
            out.add(str(abs(int(Decimal(str(obj))))))
        return out

    def leaked(raw_obj, red_text):
        """The figures of raw_obj whose whole-number part still stands in red_text, band labels aside."""
        text = red_text
        for label in band_labels:
            text = text.replace(label, " ")
        return sorted(x for x in figures(raw_obj) if x != "0" and re.search(rf"(?<![\w.]){x}(?!\w)", text))

    def run_cli(args):
        """(exit code or the exception's name, text) of main(args) printing to a cp1252 stream."""
        import io
        buf = io.BytesIO()
        stream = io.TextIOWrapper(buf, encoding="cp1252")
        saved_out = sys.stdout
        sys.stdout = stream
        try:
            rc = main(args)
            stream.flush()
        except UnicodeEncodeError:
            rc = "UnicodeEncodeError"
        finally:
            sys.stdout = saved_out
        return rc, buf.getvalue().decode("utf-8", errors="replace")

    # validation
    _c("a cash entry validates", validate_entry(cash()) == [], f)
    _c("a product entry with a sourced price validates", validate_entry(product()) == [], f)
    _c("a brand price without its page is refused",
       problems_with(priced(price_source_ref=None), "price_source_ref"), f)
    _c("a retailer price without its page is refused, a price the human states needs none",
       problems_with(priced(price_source="retailer_page", price_source_ref=None), "price_source_ref")
       and validate_entry(priced(price_source="user_stated", price_source_ref=None)) == [], f)
    _c("an unknown price source is refused", problems_with(priced(price_source="guess"), "price_source"), f)
    _c("a price without its capture date is refused",
       problems_with(priced(price_captured_at=None), "price_captured_at"), f)
    _c("a capture date after today is refused",
       problems_with(priced(price_captured_at="2099-01-01"), "after today"), f)
    _c("a zero or unreadable retail price is refused",
       problems_with(priced(retail_price="0"), "must be positive")
       and problems_with(priced(retail_price="$199"), "must be a number"), f)
    _c("a product entry with an amount is refused",
       problems_with(product(amount="199.99"), "retail_price, not amount"), f)
    _c("a quantity of 0, -3, 1.5, text or true is refused",
       all(problems_with(priced(quantity=q), "whole number") for q in (0, -3, 1.5, "two", True)), f)
    _c("a cash entry with no amount, or one Decimal cannot read, is refused with the field named",
       problems_with(cash(amount=None), "amount is required")
       and problems_with(cash(amount="$100"), "amount must be a number")
       and problems_with(cash(amount="NaN"), "finite"), f)
    _c("a zero cash amount is refused", problems_with(cash(amount="0"), "positive"), f)
    _c("a refund must be negative and must carry an amount",
       validate_entry(cash(kind="refund", amount="-40")) == []
       and problems_with(cash(kind="refund", amount="40"), "negative")
       and problems_with(cash(kind="refund", amount=None), "amount is required")
       and problems_with(cash(kind="refund", amount="0"), "negative")
       and problems_with(cash(kind="refund", amount="-0"), "negative"), f)
    _c("an amount too large to hold in cents is refused, and no message repeats the value",
       problems_with(cash(amount="1e30"), "too large") and problems_with(cash(amount="1e26"), "too large")
       and not any("4,750" in p or "1e30" in p for p in validate_entry(cash(amount="$4,750"))
                   + validate_entry(cash(amount="1e30"))), f)
    _c("a date not written YYYY-MM-DD, or after today, is refused",
       all(problems_with(cash(date=d), "YYYY-MM-DD") for d in ("March 4", "20260304", "2026-W10-1"))
       and problems_with(cash(date="2099-01-01"), "after today"), f)
    _c("an entry dated today, with a price captured today, is accepted",
       validate_entry(cash(), today=date(2026, 3, 4)) == []
       and validate_entry(product(), today=date(2026, 5, 11)) == []
       and validate_entry(product(), today=date(2026, 5, 10)) != [], f)
    _c("a blank or non-text payer is refused",
       problems_with(cash(payer="   "), "payer is required") and problems_with(cash(payer=5), "payer is required"), f)
    _c("an unknown kind is refused", problems_with(cash(kind="tip"), "kind"), f)
    _c("a sequence below 2 or not a whole number is refused",
       all(problems_with(cash(sequence=s), "sequence") for s in (1, 0, "2", True))
       and validate_entry(cash(sequence=2)) == [], f)
    unpriced = product(); unpriced["product"] = {"item": "throw pillow set"}
    n = normalize(unpriced)
    _c("an unpriced product normalizes with a gap, never an invented price, and counts as one item",
       n["product"]["retail_price"] is None and any("retail_price" in g for g in n["gaps"])
       and n["product"]["quantity"] == 1, f)
    _c("normalize quantizes and derives tax_year", normalize(cash(amount="1250"))["amount"] == "1250.00"
       and normalize(cash())["tax_year"] == 2026, f)
    _c("an input status of confirmed or void is stored as proposed",
       [normalize(cash(status=s))["status"] for s in ("confirmed", "void", "proposed")]
       == ["proposed", "proposed", "proposed"], f)
    nid = lambda e: normalize(e)["entry_id"]  # noqa: E731
    _c("the id is deterministic for the same event", nid(cash()) == nid(cash()), f)
    _c("the id ignores case and extra spaces in the payer and the item",
       nid(cash(payer="hearthline  paint ")) == nid(cash())
       and nid(priced(item="Cordless Brad  Nailer")) == nid(product()), f)
    _c("the id differs by amount, payer, kind, evidence reference and sequence",
       len({nid(cash()), nid(cash(amount="1250.01")), nid(cash(payer="Hearthline Stain")),
            nid(cash(kind="affiliate")), nid(cash(evidence_ref="receipt-b.pdf")), nid(cash(sequence=2))}) == 6, f)
    _c("the MCP write argument is true only for true or the text true",
       [write_flag(v) for v in (True, "true", " TRUE ", False, "false", "False", 1, None, "yes", "no", "0")]
       == [True, True, True, False, False, False, False, False, False, False, False], f)
    _c("the gifts file name differs from the income file name, also with no -income and no dot",
       [_gifts_name(x) for x in ("2026-income.local.csv", "income.local.csv", "books.local.csv", "books")]
       == ["2026-gifts.local.csv", "income-gifts.local.csv", "books-gifts.local.csv", "books-gifts"], f)
    with tempfile.TemporaryDirectory() as cs:
        repo_dir, other_spelling = Path(cs) / "repo", Path(cs) / "REPO-alias"
        repo_dir.mkdir()
        other_spelling.mkdir()
        same_folder = lambda a, b: Path(a).name == "REPO-alias" and Path(b).name == "repo"  # noqa: E731
        _c("a path spelled another way on a filesystem that ignores case counts as inside the repo",
           _under(other_spelling / "docs" / "x.local.csv", repo_dir, samefile=same_folder)
           and not _under(other_spelling / "docs" / "x.local.csv", repo_dir, samefile=lambda a, b: False), f)

    with tempfile.TemporaryDirectory() as td, tempfile.TemporaryDirectory() as away, file_hash.windows_paths():
        root = Path(td)
        (root / "pipeline" / "finance").mkdir(parents=True)
        saved = os.environ.get("CREATOR_OS_ROOT")
        os.environ["CREATOR_OS_ROOT"] = str(root)
        here = os.getcwd()
        # The checks run from a temporary folder: a mutant that reads a relative path from the current
        # folder (or drops a refusal) then writes there, never into the checkout the run started in.
        os.chdir(away)
        try:
            # writes and the gate
            r = add_entry(cash(), write=True, config=off)
            _c("the gate refuses a write with finance_management off", not r["written"] and "finance_management" in r["reason"]
               and not ledger_path().exists(), f)
            r = add_entry(cash(), write=False, config=on)
            _c("a dry run writes nothing, and an add carries the boundary line",
               not r["written"] and not ledger_path().exists() and r["boundary"] == BOUNDARY
               and add_entry(cash(amount=None))["boundary"] == BOUNDARY, f)
            r1 = add_entry(cash(), write=True, config=on)
            r2 = add_entry(cash(), write=True, config=on)
            _c("the first write lands and the same event again is a duplicate",
               r1["written"] and not r2["written"] and "duplicate" in r2["reason"]
               and len(load_ledger()["entries"]) == 1, f)
            add_entry(product(), write=True, config=on)
            add_entry(product(date="2026-06-01", product={"item": "wall hooks"}), write=True, config=on)
            add_entry(cash(date="2026-04-02", payer="VidTube", payer_type="platform", kind="ad_revenue",
                           amount="312.40", source="platform_statement"), write=True, config=on)
            add_entry(cash(date="2026-04-20", payer="Hearthline Paint", kind="refund", amount="-50"),
                      write=True, config=on)
            add_entry(cash(date="2025-12-30", payer="Old Brand", amount="10"), write=True, config=on)
            again = add_entry(cash(payer="HEARTHLINE PAINT"), write=True, config=on)
            led = load_ledger()
            _c("six entries, all proposed; the first entry re-sent under another case is a duplicate",
               len(led["entries"]) == 6 and all(e["status"] == "proposed" for e in led["entries"])
               and not again["written"] and "duplicate" in again["reason"], f)
            side = root / "pipeline" / "finance" / "side.local.json"
            w1 = add_entry(cash(), write=True, config=on, path=side)
            w2 = add_entry(cash(amount="75"), write=True, config=on, path=side)
            w3 = add_entry(cash(sequence=2), write=True, config=on, path=side)
            w4 = add_entry(cash(sequence=2), write=True, config=on, path=side)
            _c("another event on the same date is written, a sequence 2 repeat is written once",
               w1["written"] and w2["written"] and w3["written"] and not w4["written"]
               and len(load_ledger(side)["entries"]) == 3, f)
            s = payer_summary(2026)
            _c("payer summary: cash nets the refund and excludes other years",
               s["payers"]["Hearthline Paint"]["cash"] == "1200.00" and "Old Brand" not in s["payers"], f)
            _c("payer summary: product value counts priced items, counts unpriced ones and each item",
               s["payers"]["Northstar Tools"]["product_value"] == "199.99"
               and s["payers"]["Northstar Tools"]["unpriced_items"] == 1 and s["totals"]["unpriced_items"] == 1
               and s["payers"]["Northstar Tools"]["items"] == 2, f)
            _c("payer summary: by-month cash", s["by_month"] == {"2026-03": "1250.00", "2026-04": "262.40"}, f)
            _c("payer summary: totals", s["totals"]["cash"] == "1512.40" and s["totals"]["product_value"] == "199.99"
               and s["totals"]["proposed"] == 5, f)
            _c("the boundary line is on the summary", s["boundary"] == BOUNDARY, f)
            mem = {"entries": [normalize(cash()), normalize(cash(payer="hearthline paint", amount="5")),
                               dict(normalize(cash(amount="7")), payer=None),
                               dict(normalize(priced(quantity=3, retail_price="33.335"))),
                               dict(normalize(product(date="2026-05-12")), product=dict(product()["product"], quantity=0)),
                               dict(normalize(product(date="2026-05-13")), product=dict(product()["product"], quantity=None)),
                               normalize(cash(payer="Harbor Pine", amount="11")),
                               normalize(cash(payer="Harbor Point", amount="13")),
                               {k: v for k, v in normalize(cash(payer="Undated Co", amount="3")).items() if k != "date"}]}
            ms = payer_summary(2026, mem)
            _c("payer summary: one payer written two ways is one row; an entry with no payer is shown, not a crash",
               ms["payers"]["Hearthline Paint"]["cash"] == "1255.00" and ms["payers"]["(no payer)"]["cash"] == "7.00", f)
            _c("payer summary: two payers with similar names stay two rows; an entry with no date is counted as undated",
               ms["payers"]["Harbor Pine"]["cash"] == "11.00" and ms["payers"]["Harbor Point"]["cash"] == "13.00"
               and ms["by_month"].get("undated") == "3.00", f)
            _c("redaction keeps a row for each payer when initials collide (three payers are H.P.)",
               len(redact(ms)["payers"]) == len(ms["payers"])
               and {"H.P.", "H.P. 2", "H.P. 3"} <= set(redact(ms)["payers"]), f)
            _c("payer summary: quantity times the quantized price; a stored quantity of 0 is unpriced, never valued; "
               "a stored null quantity is one item",
               ms["payers"]["Northstar Tools"]["product_value"] == "300.01"
               and ms["payers"]["Northstar Tools"]["items"] == 4 and ms["payers"]["Northstar Tools"]["unpriced_items"] == 1, f)
            # confirm and void
            pid = next(e["entry_id"] for e in led["entries"] if e["kind"] == "product" and e["product"]["item"] == "wall hooks")
            _c("void is refused with the gate off", not set_status(pid, "void", config=off)["updated"], f)
            _c("void lands with the gate on", set_status(pid, "void", config=on)["updated"], f)
            _c("a void entry leaves the summary", payer_summary(2026)["totals"]["unpriced_items"] == 0, f)
            _c("an unknown status is refused", not set_status(pid, "maybe", config=on)["updated"], f)
            _c("an unknown id is refused", not set_status("BK-nope", "confirmed", config=on)["updated"], f)
            g = gift_register(2026)
            _c("gift register lists the priced item with its source",
               [r["item"] for r in g["items"]] == ["cordless brad nailer"] and g["items"][0]["price_source"] == "brand_page", f)
            # forms
            led = load_ledger()
            led["forms_received"] = [{"tax_year": 2026, "payer": "Hearthline Paint", "form": "1099-NEC", "amount": "1250"},
                                     {"tax_year": 2026, "payer": "VidTube", "form": "1099-MISC", "amount": "312.40"},
                                     {"tax_year": 2025, "payer": "Old Brand", "form": "1099-NEC", "amount": "10"}]
            _save(led)
            fc = form_check(2026)
            _c("form check: a form that differs from the ledger is reported with the difference",
               fc["forms"][0]["difference"] == "50.00" and fc["forms"][0]["matches"] is False, f)
            _c("form check: a matching form matches, and another year's form is left out",
               fc["forms"][1]["matches"] is True and len(fc["forms"]) == 2, f)
            _c("form check: no payer is missing a form here", fc["payers_without_form"] == [], f)
            fmem = {"entries": [normalize(cash(date="2026-04-02", payer="VidTube", payer_type="platform",
                                                kind="ad_revenue", amount="312.40", source="platform_statement")),
                                normalize(cash())],
                    "forms_received": [{"tax_year": "2026", "payer": "vidtube ", "form": "1099-MISC", "amount": "312.40"},
                                       {"tax_year": 2026, "payer": "Quill Media", "form": "1099-NEC", "amount": "4,750.00"}]}
            fm = form_check(2026, fmem)
            _c("form check: a payer written another way matches, a year written as text counts, an unreadable "
               "amount is listed with the problem, and a payer with cash and no form is listed",
               fm["forms"][0]["matches"] is True and "must be a number" in fm["forms"][1]["problem"]
               and fm["payers_without_form"] == [{"payer": "Hearthline Paint", "ledger_cash": "1250.00"}], f)
            red_fm = json.dumps(redact(fm))
            _c("form check: a redacted problem row carries neither the payer's name nor the figure",
               "Quill" not in red_fm and "4,750" not in red_fm and "4750" not in red_fm, f)
            # proposals from paid invoices
            inv = [{"invoice_id": "INV-D1-001", "status": "paid", "total": "900.00", "brand_name": "Hearthline Paint",
                    "deal_id": "D1", "payment_received_date": "2026-07-01", "payment_method": "ach"},
                   {"invoice_id": "INV-D2-001", "status": "sent", "total": "500.00", "brand_name": "X", "deal_id": "D2",
                    "payment_received_date": "2026-07-03"},  # dated and totalled, excluded by status alone
                   {"invoice_id": "INV-D3-001", "status": "paid", "total": None, "brand_name": "Y", "deal_id": "D3",
                    "payment_received_date": "2026-07-02"}]
            skipped = []
            props = propose_from_invoices(inv, load_ledger(), skipped)
            _c("paid invoices with a total and a date are proposed, unpaid ones are not, incomplete ones are skipped "
               "with the reason",
               [p["invoice_id"] for p in props] == ["INV-D1-001"] and props[0]["source"] == "invoice_paid"
               and props[0]["amount"] == "900.00" and [x["invoice_id"] for x in skipped] == ["INV-D3-001"]
               and "amount" in skipped[0]["problems"][0], f)
            odd = []
            propose_from_invoices([{"invoice_id": "INV-E1", "status": "paid", "total": 900.0, "brand_name": "E",
                                    "payment_received_date": "2026-07-01"},
                                   {"invoice_id": "INV-E2", "status": "paid", "total": "-50", "brand_name": "E",
                                    "payment_received_date": "2026-07-01"},
                                   {"invoice_id": "INV-E3", "status": "paid", "total": "50", "brand_name": "",
                                    "account_ref": None, "payment_received_date": "2026-07-01"},
                                   {"invoice_id": "INV-E4", "status": "paid", "total": "50", "brand_name": "E",
                                    "payment_received_date": "2026-07-01T10:00:00"}], _empty(), odd)
            _c("a numeric total is proposed; a negative total, no payer name or a timestamp date is skipped",
               [x["invoice_id"] for x in odd] == ["INV-E2", "INV-E3", "INV-E4"], f)
            add_entry(props[0], write=True, config=on)
            _c("an invoice already in the ledger is not proposed again",
               propose_from_invoices(inv, load_ledger()) == [], f)
            # set-aside
            (root / "pipeline" / "finance" / "cost-actuals.local.json").write_text(json.dumps(
                {"entries": [{"date": "2026-02-01", "amount": "100.00"}, {"date": "2025-02-01", "amount": "999"}]}),
                encoding="utf-8")
            sa = set_aside(2026, "25")
            _c("set-aside: net is income plus priced product minus this year's actuals, times the given percent",
               sa["income"] == "2612.39" and sa["cost_actuals"] == "100.00" and sa["net"] == "2512.39"
               and sa["set_aside"] == "628.10" and set_aside(2026, "25%")["set_aside"] == "628.10", f)
            refused = []
            for bad_pct in ("0", "100", "27,5", "NaN", True):
                try:
                    set_aside(2026, bad_pct)
                except ValueError:
                    refused.append(bad_pct)
            _c("set-aside refuses 0, 100, a comma decimal, NaN and a bool", refused == ["0", "100", "27,5", "NaN", True], f)
            low = set_aside(2026, "25", cost_actuals={"entries": [{"date": "2026-01-01", "amount": "9999"}]})
            _c("set-aside on a negative net is zero, and the net stays negative",
               low["set_aside"] == "0.00" and low["net"].startswith("-"), f)
            try:
                set_aside(2026, "25", cost_actuals={"entries": [{"date": "2026-01-01", "amount": "$100"}]})
                _c("set-aside names a cost-actuals amount it cannot read", False, f)
            except ValueError as exc:
                _c("set-aside names a cost-actuals amount it cannot read", "2026-01-01" in str(exc), f)
            # cost actuals (spending proposed from a receipt)
            spend = {"date": "2026-05-02", "vendor": "  Northstar   Tools ", "amount": "239.61",
                     "category": None, "receipt_ref": "Inbox/Processed/2026-05-03/order.txt",
                     "receipt_sha256": "ab" * 32}
            ca = cost_actuals_path()
            ca.unlink()
            gated = add_cost_actual(spend, write=True, config=off)
            _c("cost actual: refused to write with finance_management off, nothing created",
               gated["written"] is False and "finance_management" in gated["reason"] and not ca.exists(), f)
            w1 = add_cost_actual(spend, write=True, config=on)
            w2 = add_cost_actual(spend, write=True, config=on)
            stored = json.loads(ca.read_text(encoding="utf-8"))["entries"]
            _c("cost actual: written once, normalized; the same receipt again is a duplicate",
               w1["written"] and not w2["written"] and "duplicate" in w2["reason"] and len(stored) == 1
               and stored[0]["vendor"] == "Northstar Tools" and stored[0]["amount"] == "239.61", f)
            bads = [add_cost_actual(dict(spend, **chg), write=True, config=on)["problems"][0]
                    for chg in ({"date": "2099-01-01"}, {"vendor": " "}, {"amount": "-5"},
                                {"category": "snacks"}, {"is_capex": "yes"}, {"date": "05/02/2026"})]
            _c("cost actual: a future or malformed date, no vendor, a negative amount, an unknown "
               "category and a non-bool is_capex are refused",
               [b.split()[0] for b in bads] == ["date", "vendor", "amount", "category", "is_capex", "date"], f)
            ca.write_text("{oops", encoding="utf-8")
            kept = add_cost_actual(dict(spend, receipt_sha256="cd" * 32), write=True, config=on)
            _c("cost actual: a file that does not parse is left as it is",
               not kept["written"] and ca.read_text(encoding="utf-8") == "{oops", f)
            ca.unlink()
            # export
            not_written = []
            for bad_out in (root / "pipeline" / "finance" / "books-2026.csv",
                            root / "pipeline" / "finance" / "x.local.d" / "books.csv",
                            root / "docs" / "2026-income.local.csv",
                            root / "pipeline" / "2026-income.local.csv",
                            root / "pipeline" / "finance" / "2026-income.local.template.json",
                            "pipeline/finance/../../docs/2026-income.local.csv"):
                try:
                    export_csv(2026, bad_out)
                except ValueError:
                    target = bad_out if isinstance(bad_out, Path) else root / bad_out
                    not_written.append(not target.exists())
            _c("an in-repo export that is not a .local.csv under pipeline/finance/ is refused, also through ..",
               not_written == [True] * 6, f)
            before = ledger_path().read_bytes()
            try:
                export_csv(2026, "pipeline/finance/income-ledger.local.json")
                kept = False
            except ValueError:
                kept = ledger_path().read_bytes() == before
            other = root / "pipeline" / "finance" / "notes.local.csv"
            other.write_text("my own notes\n", encoding="utf-8")
            try:
                export_csv(2026, other)
                kept_other = False
            except ValueError as exc:
                kept_other = other.read_text(encoding="utf-8") == "my own notes\n" and "earlier export" in str(exc)
            mine = root / "pipeline" / "finance" / "exports" / "2028-gifts.local.csv"
            mine.parent.mkdir(parents=True, exist_ok=True)
            mine.write_text("my own gift list\n", encoding="utf-8")
            try:
                export_csv(2028)
                kept_gifts = False
            except ValueError:
                kept_gifts = (mine.read_text(encoding="utf-8") == "my own gift list\n"
                              and not (mine.parent / "2028-income.local.csv").exists())
            mine.unlink()
            _c("an export never overwrites the ledger, or a file that is not an earlier export, and checks the "
               "gifts file before writing either",
               kept and kept_other and kept_gifts, f)
            ex = export_csv(2026)
            inc = Path(ex["income_csv"]).read_text(encoding="utf-8")
            gif = Path(ex["gifts_csv"]).read_text(encoding="utf-8")
            rows = list(csv.DictReader(inc.splitlines()[1:]))
            _c("export writes the income and gift CSVs at .local. paths with the boundary first",
               ".local.csv" in ex["income_csv"] and inc.startswith(BOUNDARY + "\n") and gif.startswith(BOUNDARY + "\n")
               and ex["rows"] == 5 and ex["gift_rows"] == 1 and ex["boundary"] == BOUNDARY, f)
            _c("export: the income CSV carries each entry's amount",
               "1250.00" in [r["amount"] for r in rows] and "cordless brad nailer" in gif, f)
            again = export_csv(2026)
            _c("export: an earlier export is replaced", again["income_csv"] == ex["income_csv"], f)
            named = export_csv(2026, "pipeline/finance/exports/2026-books.local.csv")
            _c("export: a relative --out is read from the repo root, and a name without -income keeps both files",
               named["income_csv"] != named["gifts_csv"] and named["gifts_csv"].endswith("2026-books-gifts.local.csv")
               and Path(named["income_csv"]).is_relative_to(root) and Path(named["gifts_csv"]).exists()
               and "1250.00" in Path(named["income_csv"]).read_text(encoding="utf-8"), f)
            outside = export_csv(2026, Path(away) / "books.csv")
            _c("export: a path outside the repo is allowed", Path(outside["gifts_csv"]).name == "books-gifts.csv"
               and Path(outside["income_csv"]).exists(), f)
            (root / "docs").mkdir(exist_ok=True)
            tracked = root / "docs" / "tracked.md"
            tracked.write_text("keep\n", encoding="utf-8")
            exports = root / "pipeline" / "finance" / "exports"
            gifts_link, dir_link = exports / "2027-gifts.local.csv", root / "pipeline" / "finance" / "linked"
            try:
                os.symlink(tracked, gifts_link)
                os.symlink(root / "docs", dir_link, target_is_directory=True)
                linked = True
            except (OSError, NotImplementedError):
                linked = False
                print("  [skip] export through a link: os.symlink is refused here")
            if linked:
                refused = []
                for out in (exports / "2027-income.local.csv", dir_link / "2026-income.local.csv"):
                    try:
                        export_csv(2027 if "2027" in out.name else 2026, out)
                    except ValueError:
                        refused.append(True)
                _c("export: a link at the gifts file or a linked folder cannot point the export out of "
                   "pipeline/finance/", refused == [True, True] and tracked.read_text(encoding="utf-8") == "keep\n"
                   and not (exports / "2027-income.local.csv").exists(), f)
                gifts_link.unlink()
                dir_link.unlink()
            # redaction: no figure survives, with or without its cents
            raw = [payer_summary(2026), form_check(2026), set_aside(2026, "25"),
                   add_entry(cash(notes="paid by Hearthline Paint",
                                  content_refs=["https://videos.example/hearthline-spot"]))]
            red = json.dumps([redact(o) for o in raw])
            raw_g = gift_register(2026)
            red_g = json.dumps(redact(raw_g))
            _c("redaction bands every figure and initials payers in the summary, form check, set-aside and an add, "
               "and hides an entry's notes and content references",
               len(figures(raw)) >= 8 and leaked(raw, red) == [] and decimal_figure.search(red) is None
               and "Hearthline" not in red and "VidTube" not in red and "videos.example" not in red, f)
            _c("redaction bands the gift register, initials items and hides page references",
               figures(raw_g) == {"199"} and leaked(raw_g, red_g) == [] and decimal_figure.search(red_g) is None
               and "cordless" not in red_g and "Northstar" not in red_g and "example.com" not in red_g
               and "[ref]" in red_g, f)
            # the CLI, run in this process on a cp1252 stream that is not a terminal (a redirect on Windows)
            entry_file = root / "entry.json"
            entry_file.write_text(json.dumps(cash(payer="Café Ünal \U0001f3a8")), encoding="utf-8")
            rc_u, out_u = run_cli(["--add", str(entry_file)])
            _c("the CLI writes its output as UTF-8 when it is redirected",
               rc_u == 0 and "Café Ünal \U0001f3a8" in out_u, f)
            real_loader = _fin._load_local_invoices
            _fin._load_local_invoices = lambda: [{"invoice_id": "INV-Z9-001", "status": "paid", "total": "$4,750",
                                                  "brand_name": "Quill Media", "payment_received_date": "2026-07-01"}]
            try:
                rc_p, out_p = run_cli(["--propose-from-invoices", "--redacted"])
            finally:
                _fin._load_local_invoices = real_loader
            _c("the CLI lists a paid invoice it skipped, and its redacted output carries no figure or name",
               rc_p == 0 and [x["invoice_id"] for x in json.loads(out_p)["skipped"]] == ["INV-Z9-001"]
               and "4,750" not in out_p and "Quill" not in out_p, f)
            # a ledger that does not parse, or has another shape, is never overwritten
            for text in ("{oops", "", "[]", '{"entries": {}}', '{"entries": [], "forms_received": {}}'):
                ledger_path().write_text(text, encoding="utf-8")
                try:
                    add_entry(cash(date="2026-08-08"), write=True, config=on)
                    _c(f"a ledger of {text!r} stops the write", False, f)
                except ValueError:
                    _c(f"a ledger of {text!r} stops the write", ledger_path().read_text(encoding="utf-8") == text, f)
        finally:
            os.chdir(here)
            if saved is None:
                os.environ.pop("CREATOR_OS_ROOT", None)
            else:
                os.environ["CREATOR_OS_ROOT"] = saved
    n = _c.count - start
    print(f"books selftest: {'PASS' if not f else 'FAIL'} ({n - len(f)} of {n} checks)")
    return 0 if not f else 1


# ── CLI ──────────────────────────────────────────────────────────────────────

def main(argv=None):
    import argparse
    env_paths.utf8_stdio()
    ap = argparse.ArgumentParser(description="Creator OS income ledger (offline)")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--summary", action="store_true")
    ap.add_argument("--gifts", action="store_true")
    ap.add_argument("--form-check", action="store_true")
    ap.add_argument("--set-aside", action="store_true")
    ap.add_argument("--export", action="store_true")
    ap.add_argument("--propose-from-invoices", action="store_true")
    ap.add_argument("--add", metavar="ENTRY_JSON")
    ap.add_argument("--add-cost", metavar="ENTRY_JSON")
    ap.add_argument("--confirm", metavar="ENTRY_ID")
    ap.add_argument("--void", metavar="ENTRY_ID")
    ap.add_argument("--year", type=int, default=date.today().year)
    ap.add_argument("--percent")
    ap.add_argument("--out")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--redacted", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    try:
        if a.summary:
            out = payer_summary(a.year)
        elif a.gifts:
            out = gift_register(a.year)
        elif a.form_check:
            out = form_check(a.year)
        elif a.set_aside:
            if a.percent is None:
                ap.error("--set-aside needs --percent (your choice; there is no default)")
            out = set_aside(a.year, a.percent)
        elif a.export:
            out = export_csv(a.year, a.out)
        elif a.propose_from_invoices:
            skipped = []
            props = propose_from_invoices(skipped=skipped)
            out = {"boundary": BOUNDARY, "proposed": props, "skipped": skipped, "written": []}
            if a.write:
                out["written"] = [add_entry(p, write=True) for p in props]
        elif a.add:
            out = add_entry(json.loads(Path(a.add).read_text(encoding="utf-8")), write=a.write)
        elif a.add_cost:
            out = add_cost_actual(json.loads(Path(a.add_cost).read_text(encoding="utf-8")), write=a.write)
        elif a.confirm:
            out = set_status(a.confirm, "confirmed")
        elif a.void:
            out = set_status(a.void, "void")
        else:
            ap.print_help()
            return 2
    except (ValueError, OSError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(redact(out) if a.redacted else out, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
