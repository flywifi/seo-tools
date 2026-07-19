#!/usr/bin/env python3
"""Creator OS accounts: offline, deterministic, read-only CRM resolution.

The CRM read lane, shaped like tools/finance.py and tools/obligations.py (the offline compute
lane, docs/LOCAL_CONTEXT.md): stdlib only, CREATOR_OS_ROOT sandbox, computed_by on every result,
a missing figure is null plus a gaps[] entry, never a guess (protocols/no-fabrication.md).

This tool READS brand account and deal records and answers three questions:
  - resolve(query): which account does a fuzzy phrase ("that lightbulb company", "hearthline")
    point at? Tiered matching (exact, alias, substring, difflib fuzzy, brand-category term map).
    It NEVER auto-picks past the alias tier: a category or multi-candidate outcome returns
    resolved: null plus the candidate list with the evidence for each, for the human to choose.
  - contacts(query, person): the contact(s) on the resolved account, optionally filtered to a
    person hint. A person hint that matches nobody returns a gap, never the wrong person.
  - deal_status(query|deal_id): the lifecycle stage of a deal, reported VERBATIM from the record
    (stage, latest stage_history entry, payment_due_date, denormalized invoice.status). No money
    math happens here; that is tools/finance.py.

There are NO write modes. Account and deal mutations stay in the spoke/SKILL contracts and their
human-gated flows; this tool only reads. Real records live in pipeline/accounts/*.local.json and
pipeline/deals/*.local.json (gitignored, PII); on a fresh clone with no local records every
command degrades to an empty result plus a gap, exit 0. Contact data is PII: pass --redacted (or
redacted=True) to mask names to initials and emails for anything quoted off this machine.

Usage:
  python3 tools/accounts.py --resolve "that lightbulb company" [--records FILE] [--redacted]
  python3 tools/accounts.py --contacts "hearthline" [--person "marcus"] [--records FILE] [--redacted]
  python3 tools/accounts.py --deal-status "lumen" [--deals FILE] [--records FILE] [--today YYYY-MM-DD]
  python3 tools/accounts.py --deal-status --deal-id deal-lumen-001 [--deals FILE]
  python3 tools/accounts.py --selftest
"""
import argparse
import difflib
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(os.environ.get("CREATOR_OS_ROOT", str(Path(__file__).resolve().parent.parent)))
ACCOUNTS_DIR = ROOT / "pipeline" / "accounts"
DEALS_DIR = ROOT / "pipeline" / "deals"
TOOL = "tools/accounts.py"

# Confidence floors per matching tier.
EXACT, ALIAS, SUBSTRING = 1.0, 0.95, 0.9
FUZZY_HIGH, FUZZY_FLOOR, CATEGORY = 0.8, 0.6, 0.5

# Brand-category term map: everyday words a creator might use, keyed to the brand_category enum
# in pipeline/accounts/account-schema.json. Used only for the weakest tier; a category match
# never auto-resolves, it only surfaces candidates for the human to confirm.
CATEGORY_TERMS = {
    "furniture": ["furniture", "couch", "sofa", "table", "chair", "dresser"],
    "home decor": ["decor", "home decor", "homeware", "decorating"],
    "paint and finishes": ["paint", "finish", "stain", "varnish"],
    "tools and hardware": ["tool", "hardware", "drill", "saw"],
    "textiles": ["textile", "fabric", "rug", "curtain", "linen"],
    "lighting": ["lightbulb", "light bulb", "lightbulbs", "lamp", "lamps", "lighting",
                 "sconce", "chandelier", "bulb"],
    "organization": ["organization", "organizing", "storage", "bins"],
    "garden and outdoor": ["garden", "outdoor", "patio", "backyard", "plant"],
    "marketplace and thrift": ["thrift", "marketplace", "secondhand", "vintage market"],
}


def _norm(s):
    if not isinstance(s, str):
        return ""
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", s.lower())).strip()


def _ratio(a, b):
    return difflib.SequenceMatcher(None, a, b).ratio()


# ── record loading ───────────────────────────────────────────────────────────

def _load_dir(directory, glob="*.local.json"):
    out = []
    if not directory.exists():
        return out
    for p in sorted(directory.glob(glob)):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(data, dict):
            out.append(data)
    return out


def load_accounts(records=None):
    """Real account records from pipeline/accounts/*.local.json, or an explicit in-memory list
    (used by the scenario runner and --records, so tests never touch the local store)."""
    if records is not None:
        return list(records)
    return _load_dir(ACCOUNTS_DIR)


def load_deals(records=None):
    if records is not None:
        return list(records)
    return _load_dir(DEALS_DIR)


# ── resolver ─────────────────────────────────────────────────────────────────

def _account_terms(acct):
    name = acct.get("brand_name", "")
    aliases = acct.get("aliases", []) or []
    return _norm(name), [_norm(a) for a in aliases if isinstance(a, str)]


def _score_account(query_norm, acct):
    """Best (confidence, basis) for one account against the normalized query, or None."""
    name_norm, alias_norms = _account_terms(acct)
    if not name_norm:
        return None
    if query_norm == name_norm:
        return EXACT, "exact"
    if query_norm in alias_norms:
        return ALIAS, "alias"
    if name_norm and (query_norm in name_norm or name_norm in query_norm):
        return SUBSTRING, "substring"
    best_fuzzy = max([_ratio(query_norm, name_norm)]
                     + [_ratio(query_norm, a) for a in alias_norms])
    if best_fuzzy >= FUZZY_HIGH:
        return best_fuzzy, "fuzzy_high"
    if best_fuzzy >= FUZZY_FLOOR:
        return best_fuzzy, "fuzzy_low"
    # weakest tier: brand-category term map
    cat = acct.get("brand_category", "")
    for term in CATEGORY_TERMS.get(cat, []):
        if re.search(rf"\b{re.escape(term)}\b", query_norm):
            return CATEGORY, "category"
    return None


def resolve(query, accounts=None):
    """Resolve a fuzzy account phrase to at most one account. Never auto-picks past the alias
    tier: only an exact/alias match, or a sole fuzzy_high candidate, sets `resolved`. Everything
    else returns resolved: null plus the ranked candidates with each match_basis."""
    accts = load_accounts(accounts)
    qn = _norm(query)
    result = {"query": query, "resolved": None, "resolution": "none",
              "candidates": [], "computed_by": f"{TOOL}.resolve", "gaps": []}
    if not qn:
        result["gaps"].append("empty query after normalization")
        return result
    if not accts:
        result["gaps"].append("no account records available (fresh clone or empty store)")
        return result

    scored = []
    for a in accts:
        s = _score_account(qn, a)
        if s is not None:
            conf, basis = s
            scored.append({"account_id": a.get("account_id"),
                           "brand_name": a.get("brand_name"),
                           "confidence": round(float(conf), 3),
                           "match_basis": basis})
    scored.sort(key=lambda c: c["confidence"], reverse=True)
    result["candidates"] = scored
    if not scored:
        result["gaps"].append("no account matched; ask the human to name the brand exactly")
        return result

    top = scored[0]
    result["resolution"] = top["match_basis"]
    strong = [c for c in scored if c["confidence"] >= FUZZY_HIGH]
    if top["match_basis"] in ("exact", "alias"):
        # a decisive match, unless a second candidate ties it exactly
        if len(scored) == 1 or scored[1]["confidence"] < top["confidence"]:
            result["resolved"] = top
        else:
            result["gaps"].append("two accounts tie at the top; ask the human which brand")
    elif len(strong) == 1 and top["confidence"] >= FUZZY_HIGH:
        result["resolved"] = top
    else:
        result["gaps"].append(
            "no single confident match; candidates surfaced for the human to choose "
            "(a category or nickname phrase never auto-resolves)")
    return result


# ── contacts ─────────────────────────────────────────────────────────────────

def _all_contacts(acct):
    rows = []
    pc = acct.get("primary_contact")
    if isinstance(pc, dict) and (pc.get("name") or pc.get("email")):
        rows.append({**pc, "kind": "primary"})
    for sc in acct.get("secondary_contacts", []) or []:
        if isinstance(sc, dict) and (sc.get("name") or sc.get("email")):
            rows.append({**sc, "kind": "secondary"})
    return rows


def contacts(query, person=None, accounts=None):
    """Contacts on the account `query` resolves to. `person` filters by a name/role token; a hint
    that matches nobody returns a gap (never the wrong person). Resolution reuses resolve(), so an
    unresolved brand yields no contacts, only the resolver's candidate list."""
    r = resolve(query, accounts)
    out = {"query": query, "person_hint": person, "account": None, "contacts": [],
           "candidates": r["candidates"], "computed_by": f"{TOOL}.contacts", "gaps": []}
    if not r["resolved"]:
        out["gaps"].append("brand did not resolve to one account; cannot return contacts")
        out["gaps"].extend(r["gaps"])
        return out
    acct = next((a for a in load_accounts(accounts)
                 if a.get("account_id") == r["resolved"]["account_id"]), None)
    out["account"] = {"account_id": r["resolved"]["account_id"],
                      "brand_name": r["resolved"]["brand_name"]}
    rows = _all_contacts(acct) if acct else []
    if not rows:
        out["gaps"].append("account has no contact on record")
        return out
    if person:
        pn = _norm(person)
        matched = [c for c in rows
                   if pn in _norm(c.get("name", "")) or pn in _norm(c.get("role", ""))
                   or any(pn == t for t in _norm(c.get("name", "")).split())]
        if not matched:
            out["gaps"].append(
                f"no contact matches {person!r} on this account; not guessing (the known "
                f"contacts are: {', '.join(c.get('name', '?') for c in rows)})")
            return out
        rows = matched
    out["contacts"] = rows
    return out


# ── deal status ──────────────────────────────────────────────────────────────

def deal_status(query=None, deal_id=None, deals=None, accounts=None, today=None):
    """Lifecycle status of a deal, reported VERBATIM from the record. No money math (that is
    tools/finance.py). Resolve by explicit deal_id, else by resolving `query` to an account and
    taking that account's deal(s)."""
    all_deals = load_deals(deals)
    out = {"query": query, "deal_id": deal_id, "deals": [],
           "computed_by": f"{TOOL}.deal_status", "gaps": []}
    picked = []
    if deal_id:
        picked = [d for d in all_deals if d.get("deal_id") == deal_id]
        if not picked:
            out["gaps"].append(f"no deal with id {deal_id!r}")
    elif query:
        r = resolve(query, accounts)
        out["resolution"] = r
        if not r["resolved"]:
            out["gaps"].append("brand did not resolve to one account; cannot list its deals")
            return out
        aid = r["resolved"]["account_id"]
        picked = [d for d in all_deals if d.get("account_ref") == aid]
        if not picked:
            out["gaps"].append(f"account {aid!r} resolved but has no deal records")
    else:
        out["gaps"].append("provide either --deal-status <query> or --deal-id")
        return out

    for d in picked:
        hist = d.get("stage_history") or []
        inv = d.get("invoice") or {}
        out["deals"].append({
            "deal_id": d.get("deal_id"),
            "brand_name": d.get("brand_name"),
            "stage": d.get("stage"),
            "latest_stage_event": hist[-1] if hist else None,
            "payment_due_date": d.get("payment_due_date"),
            "invoice_status": inv.get("status"),
        })
    return out


# ── redaction (contact data is PII) ──────────────────────────────────────────

def _initials(name):
    if not isinstance(name, str) or not name.strip():
        return name
    return ".".join(part[0].upper() for part in name.split() if part) + "."


def _mask_email(email):
    if not isinstance(email, str) or "@" not in email:
        return email
    local, _, domain = email.partition("@")
    dparts = domain.split(".")
    dmask = (dparts[0][:1] + "***") if dparts[0] else "***"
    tld = ("." + ".".join(dparts[1:])) if len(dparts) > 1 else ""
    return f"{local[:1]}***@{dmask}{tld}"


_NAME_KEYS = {"name", "brand_name"}
_EMAIL_KEYS = {"email"}


def redact(obj):
    """Mask contact names to initials and emails to a stub for anything that leaves this machine.
    The record on disk is untouched; this returns a copy. account_id and stage stay clear (not
    PII); names, brand names, and emails are masked."""
    if isinstance(obj, list):
        return [redact(x) for x in obj]
    if not isinstance(obj, dict):
        return obj
    out = {}
    for k, v in obj.items():
        if k in _NAME_KEYS and isinstance(v, str):
            out[k] = _initials(v)
        elif k in _EMAIL_KEYS and isinstance(v, str):
            out[k] = _mask_email(v)
        elif isinstance(v, (dict, list)):
            out[k] = redact(v)
        else:
            out[k] = v
    return out


# ── selftest ─────────────────────────────────────────────────────────────────

_ROSTER = [
    {"account_id": "acct-hearthline-001", "brand_name": "Hearthline Home",
     "brand_category": "home decor", "aliases": ["hearthline"],
     "primary_contact": {"name": "Marcus Webb", "email": "marcus.webb@hearthlinehome.example",
                         "role": "Partnerships Manager"},
     "secondary_contacts": [{"name": "Dana Ellis", "email": "dana.ellis@hearthlinehome.example",
                             "role": "Creative Director"}]},
    {"account_id": "acct-hearthstone-001", "brand_name": "Hearthstone Decor",
     "brand_category": "home decor", "aliases": [],
     "primary_contact": {"name": "Priya Nair", "email": "priya@hearthstonedecor.example",
                         "role": "Owner"}},
    {"account_id": "acct-lumen-001", "brand_name": "Lumen & Co",
     "brand_category": "lighting", "aliases": ["lumen"],
     "primary_contact": {"name": "Sam Ortega", "email": "sam@lumenco.example", "role": "Founder"}},
]

_DEALS = [
    {"deal_id": "deal-lumen-001", "account_ref": "acct-lumen-001", "brand_name": "Lumen & Co",
     "stage": "contract-negotiating", "payment_due_date": None,
     "invoice": {"status": "draft"},
     "stage_history": [{"stage": "in-discussion", "date": "2026-08-01"},
                       {"stage": "contract-negotiating", "date": "2026-09-10"}]},
]


def selftest():
    checks = []

    def ok(name, cond):
        checks.append((name, bool(cond)))

    # resolve tiers
    r = resolve("hearthline", _ROSTER)
    ok("alias resolves hearthline", r["resolved"] and r["resolved"]["account_id"] == "acct-hearthline-001")
    ok("hearthline resolution basis is alias", r["resolution"] == "alias")
    ok("hearthline single candidate", len(r["candidates"]) == 1)

    r = resolve("Hearthline Home", _ROSTER)
    ok("exact resolves", r["resolved"] and r["resolution"] == "exact")

    r = resolve("hearth", _ROSTER)
    ok("ambiguous hearth resolves to null", r["resolved"] is None)
    ok("ambiguous hearth has 2 candidates", len(r["candidates"]) == 2)
    ok("ambiguous hearth basis substring", r["candidates"][0]["match_basis"] == "substring")

    r = resolve("that lightbulb company", _ROSTER)
    ok("category never auto-resolves", r["resolved"] is None)
    ok("category resolution basis", r["resolution"] == "category")
    ok("category surfaces Lumen", r["candidates"] and r["candidates"][0]["brand_name"] == "Lumen & Co")

    r = resolve("Totally Unknown Brand", _ROSTER)
    ok("unknown yields no candidates", r["candidates"] == [])
    ok("unknown records a gap", len(r["gaps"]) >= 1)

    r = resolve("hearthline", [])
    ok("empty store degrades with gap", r["resolved"] is None and r["gaps"])

    # contacts
    c = contacts("hearthline", accounts=_ROSTER)
    ok("contacts returns both rows", len(c["contacts"]) == 2)
    c = contacts("hearthline", person="marcus", accounts=_ROSTER)
    ok("person hint finds Marcus", len(c["contacts"]) == 1 and c["contacts"][0]["name"] == "Marcus Webb")
    ok("Marcus email present", c["contacts"][0]["email"] == "marcus.webb@hearthlinehome.example")
    c = contacts("hearthline", person="that guy", accounts=_ROSTER)
    ok("unmatched person gaps, never guesses", c["contacts"] == [] and c["gaps"])
    c = contacts("hearth", accounts=_ROSTER)
    ok("unresolved brand returns no contacts", c["contacts"] == [] and c["account"] is None)

    # deal status
    d = deal_status(query="lumen", deals=_DEALS, accounts=_ROSTER)
    ok("deal resolves via alias", len(d["deals"]) == 1)
    ok("deal stage verbatim", d["deals"][0]["stage"] == "contract-negotiating")
    ok("latest stage event verbatim", d["deals"][0]["latest_stage_event"]["date"] == "2026-09-10")
    ok("invoice status verbatim", d["deals"][0]["invoice_status"] == "draft")
    d = deal_status(deal_id="deal-lumen-001", deals=_DEALS)
    ok("deal by id", len(d["deals"]) == 1 and d["deals"][0]["deal_id"] == "deal-lumen-001")
    d = deal_status(deal_id="nope", deals=_DEALS)
    ok("missing deal id gaps", d["deals"] == [] and d["gaps"])

    # redaction
    red = redact({"name": "Marcus Webb", "email": "marcus.webb@hearthlinehome.example",
                  "account_id": "acct-hearthline-001"})
    ok("name redacts to initials", red["name"] == "M.W.")
    ok("email masked", red["email"] == "m***@h***.example")
    ok("account_id stays clear", red["account_id"] == "acct-hearthline-001")

    # P64 AUDIT-F2 boundary case: a >NAME_MAX (255-byte) --records arg must yield the clean
    # envelope + exit 1, never a raw OSError traceback (the whole-path rule).
    import io as _io
    import contextlib as _cl
    buf = _io.StringIO()
    with _cl.redirect_stdout(buf):
        rc_long = main(["--resolve", "x", "--records", "x" * 300])
    try:
        err_obj = json.loads(buf.getvalue().strip())
    except json.JSONDecodeError:
        err_obj = {}
    ok("oversize --records arg -> clean envelope + exit 1",
       rc_long == 1 and "error" in err_obj and "next_step" in err_obj)

    passed = sum(1 for _, c in checks if c)
    for name, c in checks:
        print(f"  [{'ok' if c else 'FAIL'}] {name}")
    total = len(checks)
    print(f"selftest: {'PASS' if passed == total else 'FAIL'} ({passed} of {total} checks)")
    return 0 if passed == total else 1


# ── CLI ──────────────────────────────────────────────────────────────────────

def _load_records_arg(path):
    if not path:
        return None
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return data if isinstance(data, list) else [data]


def main(argv):
    ap = argparse.ArgumentParser(description="Offline, read-only CRM account/deal resolution.")
    ap.add_argument("--resolve", metavar="QUERY", help="resolve a fuzzy brand phrase to an account")
    ap.add_argument("--contacts", metavar="QUERY", help="contacts on the account a phrase resolves to")
    ap.add_argument("--person", metavar="HINT", help="filter contacts by a name or role token")
    ap.add_argument("--deal-status", metavar="QUERY", nargs="?", const="", help="deal lifecycle status")
    ap.add_argument("--deal-id", metavar="ID", help="deal id for --deal-status")
    ap.add_argument("--records", metavar="FILE", help="account records JSON (default: local store)")
    ap.add_argument("--deals", metavar="FILE", help="deal records JSON (default: local store)")
    ap.add_argument("--today", metavar="YYYY-MM-DD", help="reserved for date-relative reads")
    ap.add_argument("--redacted", action="store_true", help="mask names and emails for sharing")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)

    if args.selftest:
        return selftest()

    try:
        accts = _load_records_arg(args.records)
        deals = _load_records_arg(args.deals)
    except (OSError, json.JSONDecodeError) as exc:  # bad/oversize path or invalid JSON: clean envelope
        print(json.dumps({"error": f"could not read records file: {exc}",
                          "next_step": "pass a readable JSON file path"}))
        return 1

    if args.resolve is not None:
        result = resolve(args.resolve, accts)
    elif args.contacts is not None:
        result = contacts(args.contacts, person=args.person, accounts=accts)
    elif args.deal_status is not None or args.deal_id:
        q = args.deal_status if args.deal_status else None
        result = deal_status(query=q, deal_id=args.deal_id, deals=deals, accounts=accts,
                             today=args.today)
    else:
        ap.print_help()
        return 2

    if args.redacted:
        result = redact(result)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
