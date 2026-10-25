#!/usr/bin/env python3
"""Creator income ledger: money and product RECEIVED for the content business (P103 prototype).

The third instance of the offline money lane beside tools/finance.py (invoices, AR, cash flow) and
tools/obligations.py (dated duties): stdlib only, exact Decimal arithmetic, CREATOR_OS_ROOT sandbox
override, read-only reports always on, writes gated by finance_management, a selftest, and the
verbatim boundary on every report. It owns ONE record, pipeline/finance/income-ledger.local.json
(blank schema: income-ledger.template.json), and reads the paid invoices finance.py keeps so a
payment already tracked there becomes a ledger entry without retyping.

What it does: propose, confirm and void entries; per-payer and per-month summaries for a tax year;
the gift register (every product entry with its price source and where it was featured); a check of
each 1099 the human enters against the ledger's cash total for that payer; a CSV export at a
gitignored .local. path; a set-aside figure (year-to-date net times a percentage the human sets).
What it never does: estimate a product's value, decide deductibility, name a tax line, or send
anything anywhere. Every figure comes from a record, a receipt the human approved, or the human.

CLI:
  python3 tools/books.py --summary --year 2026 [--redacted]
  python3 tools/books.py --gifts --year 2026
  python3 tools/books.py --form-check --year 2026
  python3 tools/books.py --propose-from-invoices [--write]
  python3 tools/books.py --add entry.json [--write]
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
import sys
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import finance as _fin  # noqa: E402  (money(), redact(), _load_local_invoices, FINANCE_DIR)
import obligations as _ob  # noqa: E402  (load_config, flag_enabled)
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


def _root():
    return Path(os.environ.get("CREATOR_OS_ROOT", str(HERE.parent)))


def ledger_path():
    return _root() / "pipeline" / "finance" / "income-ledger.local.json"


def _empty():
    return {"_schema_version": "0.1.0", "currency": "USD", "entries": [], "forms_received": [],
            "human_review_required": True, "last_updated": None}


def load_ledger(path=None):
    """The ledger, or an empty one when the file is missing. A file that does not parse raises:
    the caller must not overwrite a record it could not read (the inbox ledger's rule)."""
    p = Path(path) if path else ledger_path()
    if not p.exists():
        return _empty()
    data = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("entries"), list):
        raise ValueError(f"{p} is not an income ledger (an object with an entries list)")
    data.setdefault("forms_received", [])
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


def entry_id_for(entry):
    """Deterministic id: BK-<yyyymmdd>-<8 hex of the fields that make an entry the same event>, so
    the same receipt or invoice proposed twice is one entry, never two."""
    key = "|".join(str(entry.get(k) or "") for k in
                   ("date", "payer", "kind", "amount", "invoice_id", "evidence_sha256"))
    if entry.get("kind") == "product":
        prod = entry.get("product") or {}
        key += "|" + "|".join(str(prod.get(k) or "") for k in ("item", "quantity", "retail_price"))
    d = str(entry.get("date") or "00000000").replace("-", "")
    return f"BK-{d}-{hashlib.sha256(key.encode('utf-8')).hexdigest()[:8]}"


def validate_entry(entry):
    """Problems with a proposed entry; empty means it may be written. The product rule: a retail
    price needs a source and a capture date, and a brand or retailer source needs its reference
    (the page), else the price is refused (no-fabrication). An amount is refused on a product
    entry (the value lives in product.retail_price) and required on every cash kind."""
    p = []
    if not isinstance(entry, dict):
        return ["entry is not an object"]
    try:
        date.fromisoformat(str(entry.get("date")))
    except (TypeError, ValueError):
        p.append("date must be YYYY-MM-DD")
    if not entry.get("payer"):
        p.append("payer is required")
    if entry.get("payer_type") not in PAYER_TYPES:
        p.append(f"payer_type must be one of {PAYER_TYPES}")
    kind = entry.get("kind")
    if kind not in KINDS:
        p.append(f"kind must be one of {KINDS}")
    if entry.get("source") not in SOURCES:
        p.append(f"source must be one of {SOURCES}")
    if kind in CASH_KINDS:
        try:
            amt = _fin.money(entry.get("amount"))
            if kind != "refund" and amt <= 0:
                p.append("amount must be positive for a cash kind")
        except Exception:  # noqa: BLE001
            p.append("amount must be a number for a cash kind")
    if kind == "product":
        if entry.get("amount") not in (None, ""):
            p.append("a product entry carries its value in product.retail_price, not amount")
        prod = entry.get("product") or {}
        if not prod.get("item"):
            p.append("product.item is required")
        price = prod.get("retail_price")
        if price not in (None, ""):
            try:
                if _fin.money(price) <= 0:
                    p.append("product.retail_price must be positive")
            except Exception:  # noqa: BLE001
                p.append("product.retail_price must be a number")
            src = prod.get("price_source")
            if src not in PRICE_SOURCES:
                p.append(f"product.price_source must be one of {PRICE_SOURCES} when a price is given")
            elif src != "user_stated" and not prod.get("price_source_ref"):
                p.append("product.price_source_ref (the page) is required for a brand or retailer price")
            try:
                date.fromisoformat(str(prod.get("price_captured_at")))
            except (TypeError, ValueError):
                p.append("product.price_captured_at must be YYYY-MM-DD when a price is given")
    return p


def normalize(entry):
    """A validated entry in its stored shape: quantized amounts as strings, tax_year from the date,
    deterministic id, status proposed unless given, gaps for a product with no price."""
    e = json.loads(json.dumps(entry))
    e["tax_year"] = int(str(e["date"])[:4])
    e["amount"] = str(_fin.money(e["amount"])) if e.get("kind") in CASH_KINDS else None
    prod = e.get("product") or {}
    if e.get("kind") == "product":
        if prod.get("retail_price") not in (None, ""):
            prod["retail_price"] = str(_fin.money(prod["retail_price"]))
        else:
            prod["retail_price"] = None
            e.setdefault("gaps", []).append(
                "retail_price: provide the brand or retailer page for this item, or state the price")
        prod.setdefault("quantity", 1)
        prod.setdefault("disposition", "kept")
        e["product"] = prod
    else:
        e["product"] = None
    e.setdefault("status", "proposed")
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
        return {"written": False, "problems": problems, "human_review_required": True}
    e = normalize(entry)
    out = {"entry": e, "written": False, "human_review_required": True, "computed_by": f"{TOOL} add_entry"}
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
            out["reason"] = f"duplicate: {e['entry_id']} is already in the ledger"
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


def propose_from_invoices(invoices=None, ledger=None):
    """Proposed entries for paid invoices the ledger does not hold yet (keyed by invoice_id). Pure:
    the caller decides whether to write them. The payment date and method come from the invoice
    record finance.mark_paid wrote; the amount is its total."""
    invoices = _fin._load_local_invoices() if invoices is None else invoices
    ledger = load_ledger() if ledger is None else ledger
    seen = {e.get("invoice_id") for e in ledger["entries"] if e.get("invoice_id")}
    out = []
    for inv in invoices:
        if inv.get("status") != "paid" or inv.get("invoice_id") in seen:
            continue
        if not inv.get("payment_received_date") or inv.get("total") in (None, ""):
            continue
        e = {"date": inv["payment_received_date"], "payer": inv.get("brand_name") or inv.get("account_ref"),
             "payer_type": "brand", "kind": "cash", "amount": inv["total"],
             "deal_id": inv.get("deal_id"), "invoice_id": inv["invoice_id"],
             "payment_method": inv.get("payment_method"), "source": "invoice_paid",
             "notes": f"from paid invoice {inv['invoice_id']}"}
        if not validate_entry(e):
            out.append(normalize(e))
    return out


def _live(entries, year):
    return [e for e in entries if e.get("status") != "void" and e.get("tax_year") == year]


def _dec(x):
    return _fin.money(x) if x not in (None, "") else Decimal("0.00")


def _product_value(e):
    prod = e.get("product") or {}
    if prod.get("retail_price") in (None, ""):
        return None
    return _fin.money(Decimal(str(prod["retail_price"])) * Decimal(str(prod.get("quantity") or 1)))


def payer_summary(year, ledger=None):
    """Per payer: cash received (refunds subtract), product value received (priced items only),
    the count of unpriced items, entries awaiting confirmation; plus per-month cash and the
    year totals. Confirmed and proposed entries both count, each flagged; void ones never."""
    ledger = load_ledger() if ledger is None else ledger
    live = _live(ledger["entries"], year)
    payers, months = {}, {}
    totals = {"cash": Decimal("0.00"), "product_value": Decimal("0.00"), "unpriced_items": 0,
              "proposed": 0, "confirmed": 0}
    for e in live:
        row = payers.setdefault(e["payer"], {"payer_type": e.get("payer_type"), "cash": Decimal("0.00"),
                                             "product_value": Decimal("0.00"), "items": 0,
                                             "unpriced_items": 0, "proposed": 0, "entries": 0})
        row["entries"] += 1
        row["proposed"] += e.get("status") == "proposed"
        totals["proposed" if e.get("status") == "proposed" else "confirmed"] += 1
        if e.get("kind") in CASH_KINDS:
            amt = _dec(e.get("amount"))
            row["cash"] += amt
            totals["cash"] += amt
            m = str(e["date"])[:7]
            months[m] = months.get(m, Decimal("0.00")) + amt
        elif e.get("kind") == "product":
            row["items"] += int((e.get("product") or {}).get("quantity") or 1)
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
        rows.append({"entry_id": e["entry_id"], "date": e["date"], "payer": e["payer"],
                     "item": prod.get("item"), "quantity": prod.get("quantity"),
                     "retail_price": prod.get("retail_price"), "value": str(v) if v is not None else None,
                     "price_source": prod.get("price_source") if v is not None else None,
                     "price_source_ref": prod.get("price_source_ref") if v is not None else None,
                     "disposition": prod.get("disposition"), "content_refs": e.get("content_refs", []),
                     "status": e.get("status"), "gaps": e.get("gaps", [])})
    rows.sort(key=lambda r: (r["value"] is not None, r["date"]))
    return {"boundary": BOUNDARY, "tax_year": year, "items": rows,
            "unpriced": sum(1 for r in rows if r["value"] is None),
            "human_review_required": True, "computed_by": f"{TOOL} gift_register"}


def form_check(year, ledger=None):
    """Each form in forms_received for the year against the ledger's cash total for that payer,
    plus payers with cash and no form. A difference is reported, never explained: the usual
    causes (a form shows gross before platform fees; a payment processor's 1099-K repeats a
    brand's own 1099-NEC) are for the human and the CPA to resolve."""
    ledger = load_ledger() if ledger is None else ledger
    summary = payer_summary(year, ledger)
    forms = [f for f in ledger.get("forms_received", []) if f.get("tax_year") == year]
    rows, covered = [], set()
    for f in forms:
        payer = f.get("payer")
        covered.add(payer)
        ledger_cash = Decimal(summary["payers"].get(payer, {}).get("cash", "0.00"))
        form_amt = _dec(f.get("amount"))
        rows.append({"payer": payer, "form": f.get("form"), "form_amount": str(form_amt),
                     "ledger_cash": str(ledger_cash), "difference": str(_fin.money(form_amt - ledger_cash)),
                     "matches": form_amt == ledger_cash})
    missing = [{"payer": p, "ledger_cash": r["cash"]} for p, r in summary["payers"].items()
               if p not in covered and Decimal(r["cash"]) != 0]
    return {"boundary": BOUNDARY, "tax_year": year, "forms": rows, "payers_without_form": missing,
            "human_review_required": True, "computed_by": f"{TOOL} form_check"}


def set_aside(year, percent, ledger=None, cost_actuals=None):
    """Year-to-date net (ledger cash plus priced product value, minus cost actuals for the year)
    times the percentage the human gives. Arithmetic only: no default percentage exists, the
    boundary line travels with the result, and the human chose the rate."""
    pct = Decimal(str(percent))
    if pct <= 0 or pct >= 100:
        raise ValueError("percent must be between 0 and 100, chosen by the human")
    summary = payer_summary(year, ledger)
    if cost_actuals is None:
        ca_path = _root() / "pipeline" / "finance" / "cost-actuals.local.json"
        cost_actuals = json.loads(ca_path.read_text(encoding="utf-8")) if ca_path.exists() else {"entries": []}
    spend = sum((_dec(e.get("amount")) for e in cost_actuals.get("entries", [])
                 if str(e.get("date") or "")[:4] == str(year) and e.get("amount") not in (None, "")),
                Decimal("0.00"))
    income = Decimal(summary["totals"]["cash"]) + Decimal(summary["totals"]["product_value"])
    net = _fin.money(income - spend)
    return {"boundary": BOUNDARY, "tax_year": year, "income": str(_fin.money(income)),
            "cost_actuals": str(_fin.money(spend)), "net": str(net), "percent": str(pct),
            "set_aside": str(_fin.money(max(net, Decimal(0)) * pct / Decimal(100))),
            "note": "the percentage is the human's choice; this is not a tax computation",
            "human_review_required": True, "computed_by": f"{TOOL} set_aside"}


def export_csv(year, out_path=None, ledger=None):
    """Two CSV files for the CPA, at gitignored .local. paths under pipeline/finance/exports/:
    <year>-income.local.csv (every live entry) and <year>-gifts.local.csv (the register). An
    out path inside the repo must carry .local. (the same structural rule as the bank-export
    reader); outside the repo any path is allowed."""
    ledger = load_ledger() if ledger is None else ledger
    root = _root()
    base = Path(out_path) if out_path else root / "pipeline" / "finance" / "exports" / f"{year}-income.local.csv"
    try:
        inside = base.resolve().is_relative_to(root.resolve())
    except AttributeError:  # Python 3.8
        inside = str(base.resolve()).startswith(str(root.resolve()))
    if inside and ".local." not in base.name:
        raise ValueError(f"refused: an export inside the repo must carry .local. in its name ({base.name})")
    base.parent.mkdir(parents=True, exist_ok=True)
    cols = ["entry_id", "status", "date", "payer", "payer_type", "kind", "amount", "item", "quantity",
            "retail_price", "price_source", "price_source_ref", "deal_id", "invoice_id", "evidence_ref",
            "payment_method", "source", "confidence", "notes"]
    live = sorted(_live(ledger["entries"], year), key=lambda e: e["date"])
    with open(base, "w", newline="", encoding="utf-8") as fh:
        fh.write(BOUNDARY + "\n")  # the first line, unquoted, so a reader sees it before any figure
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for e in live:
            prod = e.get("product") or {}
            w.writerow({**e, "item": prod.get("item"), "quantity": prod.get("quantity"),
                        "retail_price": prod.get("retail_price"), "price_source": prod.get("price_source"),
                        "price_source_ref": prod.get("price_source_ref")})
    gifts = base.with_name(base.name.replace("-income", "-gifts"))
    reg = gift_register(year, ledger)
    gcols = ["entry_id", "date", "payer", "item", "quantity", "retail_price", "value", "price_source",
             "price_source_ref", "disposition", "status"]
    with open(gifts, "w", newline="", encoding="utf-8") as fh:
        fh.write(BOUNDARY + "\n")
        w = csv.DictWriter(fh, fieldnames=gcols, extrasaction="ignore")
        w.writeheader()
        for r in reg["items"]:
            w.writerow(r)
    return {"income_csv": str(base), "gifts_csv": str(gifts), "rows": len(live), "gift_rows": len(reg["items"]),
            "computed_by": f"{TOOL} export_csv"}


def redact(obj):
    """finance.redact plus the ledger's own name keys (payer, item, page references)."""
    out = _fin.redact(obj)

    def walk(x):
        if isinstance(x, dict):
            return {k: ("[ref]" if k in ("price_source_ref", "evidence_ref") and v else
                        _fin._initials(v) if k in ("payer", "item") and isinstance(v, str) else walk(v))
                    for k, v in x.items()}
        if isinstance(x, list):
            return [walk(v) for v in x]
        return x
    out = walk(out)
    if isinstance(out, dict) and isinstance(out.get("payers"), dict):
        out["payers"] = {_fin._initials(k): v for k, v in out["payers"].items()}
    return out


# ── selftest ─────────────────────────────────────────────────────────────────

def selftest():
    import tempfile
    import file_hash
    f = []
    _c = _fin._check
    on = {"capabilities": {"finance_management": {"enabled": True}}}
    off = {"capabilities": {"finance_management": {"enabled": False}}}

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

    # validation
    _c("a cash entry validates", validate_entry(cash()) == [], f)
    _c("a product entry with a sourced price validates", validate_entry(product()) == [], f)
    bad = product(); bad["product"] = dict(bad["product"], price_source="brand_page", price_source_ref=None)
    _c("a brand price without its page is refused", any("price_source_ref" in p for p in validate_entry(bad)), f)
    bad2 = product(); bad2["product"] = dict(bad2["product"], price_source="guess")
    _c("an unknown price source is refused", any("price_source" in p for p in validate_entry(bad2)), f)
    bad3 = product(amount="199.99")
    _c("a product entry with an amount is refused", any("retail_price, not amount" in p for p in validate_entry(bad3)), f)
    _c("a cash entry with no amount is refused", any("amount" in p for p in validate_entry(cash(amount=None))), f)
    _c("a zero cash amount is refused", any("positive" in p for p in validate_entry(cash(amount="0"))), f)
    _c("a refund may be negative", validate_entry(cash(kind="refund", amount="-40")) == [], f)
    _c("a bad date is refused", any("date" in p for p in validate_entry(cash(date="March 4"))), f)
    _c("an unknown kind is refused", any("kind" in p for p in validate_entry(cash(kind="tip"))), f)
    unpriced = product(); unpriced["product"] = {"item": "throw pillow set"}
    n = normalize(unpriced)
    _c("an unpriced product normalizes with a gap, never an invented price",
       n["product"]["retail_price"] is None and any("retail_price" in g for g in n["gaps"]), f)
    _c("normalize quantizes and derives tax_year", normalize(cash(amount="1250"))["amount"] == "1250.00"
       and normalize(cash())["tax_year"] == 2026, f)
    _c("the id is deterministic for the same event", entry_id_for(normalize(cash())) == entry_id_for(normalize(cash())), f)
    _c("the id differs when the amount differs",
       entry_id_for(normalize(cash())) != entry_id_for(normalize(cash(amount="1250.01"))), f)

    with tempfile.TemporaryDirectory() as td, file_hash.windows_paths():
        root = Path(td)
        (root / "pipeline" / "finance").mkdir(parents=True)
        saved = os.environ.get("CREATOR_OS_ROOT")
        os.environ["CREATOR_OS_ROOT"] = str(root)
        try:
            # writes and the gate
            r = add_entry(cash(), write=True, config=off)
            _c("the gate refuses a write with finance_management off", not r["written"] and "finance_management" in r["reason"]
               and not ledger_path().exists(), f)
            r = add_entry(cash(), write=False, config=on)
            _c("a dry run writes nothing", not r["written"] and not ledger_path().exists(), f)
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
            led = load_ledger()
            _c("six entries, all proposed", len(led["entries"]) == 6
               and all(e["status"] == "proposed" for e in led["entries"]), f)
            s = payer_summary(2026)
            _c("payer summary: cash nets the refund and excludes other years",
               s["payers"]["Hearthline Paint"]["cash"] == "1200.00" and "Old Brand" not in s["payers"], f)
            _c("payer summary: product value counts priced items and counts unpriced ones",
               s["payers"]["Northstar Tools"]["product_value"] == "199.99"
               and s["payers"]["Northstar Tools"]["unpriced_items"] == 1 and s["totals"]["unpriced_items"] == 1, f)
            _c("payer summary: by-month cash", s["by_month"] == {"2026-03": "1250.00", "2026-04": "262.40"}, f)
            _c("payer summary: totals", s["totals"]["cash"] == "1512.40" and s["totals"]["product_value"] == "199.99"
               and s["totals"]["proposed"] == 5, f)
            _c("the boundary line is on the summary", s["boundary"] == BOUNDARY, f)
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
                                     {"tax_year": 2026, "payer": "VidTube", "form": "1099-MISC", "amount": "312.40"}]
            _save(led)
            fc = form_check(2026)
            _c("form check: a form that differs from the ledger is reported with the difference",
               fc["forms"][0]["difference"] == "50.00" and fc["forms"][0]["matches"] is False, f)
            _c("form check: a matching form matches", fc["forms"][1]["matches"] is True, f)
            _c("form check: no payer is missing a form here", fc["payers_without_form"] == [], f)
            # proposals from paid invoices
            inv = [{"invoice_id": "INV-D1-001", "status": "paid", "total": "900.00", "brand_name": "Hearthline Paint",
                    "deal_id": "D1", "payment_received_date": "2026-07-01", "payment_method": "ach"},
                   {"invoice_id": "INV-D2-001", "status": "sent", "total": "500.00", "brand_name": "X", "deal_id": "D2",
                    "payment_received_date": "2026-07-03"},  # dated and totalled, excluded by status alone
                   {"invoice_id": "INV-D3-001", "status": "paid", "total": None, "brand_name": "Y", "deal_id": "D3",
                    "payment_received_date": "2026-07-02"}]
            props = propose_from_invoices(inv, load_ledger())
            _c("paid invoices with a total and a date are proposed, unpaid or incomplete ones are not",
               [p["invoice_id"] for p in props] == ["INV-D1-001"] and props[0]["source"] == "invoice_paid"
               and props[0]["amount"] == "900.00", f)
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
               and sa["set_aside"] == "628.10", f)
            try:
                set_aside(2026, "0")
                _c("set-aside refuses a zero percent", False, f)
            except ValueError:
                _c("set-aside refuses a zero percent", True, f)
            # export
            try:
                export_csv(2026, root / "pipeline" / "finance" / "books-2026.csv")
                _c("an in-repo export without .local. is refused", False, f)
            except ValueError:
                _c("an in-repo export without .local. is refused", True, f)
            ex = export_csv(2026)
            inc = Path(ex["income_csv"]).read_text(encoding="utf-8")
            _c("export writes the income and gift CSVs at .local. paths with the boundary first",
               ".local.csv" in ex["income_csv"] and inc.startswith(BOUNDARY) and ex["rows"] == 5
               and Path(ex["gifts_csv"]).exists() and ex["gift_rows"] == 1, f)
            # redaction
            red = redact(payer_summary(2026))
            _c("redaction bands amounts and initials payers",
               "Hearthline Paint" not in json.dumps(red) and "1200.00" not in json.dumps(red), f)
            # a ledger that does not parse is never overwritten
            ledger_path().write_text("{oops", encoding="utf-8")
            try:
                add_entry(cash(date="2026-08-08"), write=True, config=on)
                _c("a ledger that does not parse stops the write", False, f)
            except ValueError:
                _c("a ledger that does not parse stops the write", ledger_path().read_text(encoding="utf-8") == "{oops", f)
        finally:
            if saved is None:
                os.environ.pop("CREATOR_OS_ROOT", None)
            else:
                os.environ["CREATOR_OS_ROOT"] = saved
    n = 46
    print(f"books selftest: {'PASS' if not f else 'FAIL'} ({n - len(f)} of {n} checks)")
    return 0 if not f else 1


# ── CLI ──────────────────────────────────────────────────────────────────────

def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description="Creator OS income ledger (offline)")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--summary", action="store_true")
    ap.add_argument("--gifts", action="store_true")
    ap.add_argument("--form-check", action="store_true")
    ap.add_argument("--set-aside", action="store_true")
    ap.add_argument("--export", action="store_true")
    ap.add_argument("--propose-from-invoices", action="store_true")
    ap.add_argument("--add", metavar="ENTRY_JSON")
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
            props = propose_from_invoices()
            out = {"proposed": props, "written": []}
            if a.write:
                out["written"] = [add_entry(p, write=True) for p in props]
        elif a.add:
            out = add_entry(json.loads(Path(a.add).read_text(encoding="utf-8")), write=a.write)
        elif a.confirm:
            out = set_status(a.confirm, "confirmed")
        elif a.void:
            out = set_status(a.void, "void")
        else:
            ap.print_help()
            return 2
    except (ValueError, OSError) as exc:
        print(json.dumps({"error": str(exc)}))
        return 1
    print(json.dumps(redact(out) if a.redacted else out, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
