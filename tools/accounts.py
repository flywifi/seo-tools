#!/usr/bin/env python3
"""Creator OS accounts: offline, deterministic, read-only CRM resolution.

The CRM read lane, shaped like tools/finance.py and tools/obligations.py (the offline compute
lane, docs/LOCAL_CONTEXT.md): stdlib only, CREATOR_OS_ROOT sandbox, computed_by on every result,
a missing figure is null plus a gaps[] entry, never a guess (protocols/no-fabrication.md).

This tool READS brand account and deal records and answers four questions:
  - resolve(query): which account does a fuzzy phrase ("that lightbulb company", "hearthline")
    point at? Tiered matching (exact, alias, substring, difflib fuzzy, brand-category term map).
    It sets `resolved` for a decisive exact or alias match, or for a single candidate at
    FUZZY_HIGH or above (a lone substring match counts); a category or multi-candidate outcome
    returns resolved: null plus the candidate list with the evidence for each, for the human to
    choose.
  - resolve_sender(from_header): which account does an email sender belong to? It matches the
    ADDRESS, not the display name (P103): an address that is a contact email on one account
    resolves; an address whose domain is the account's website host, when the website is a
    homepage address (or a subdomain of that host), is a candidate only; a domain on
    FREE_MAIL_DOMAINS is not matched by domain; a display name that names an account the address
    does not match is flagged.
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
  python3 tools/accounts.py --sender "Name <someone@brand.example>" [--records FILE] [--redacted]
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
    """Resolve a fuzzy account phrase to at most one account. `resolved` is set for a decisive
    exact or alias match, or for a single candidate at FUZZY_HIGH or above (a lone substring match
    counts). Everything else returns resolved: null plus the ranked candidates with each
    match_basis."""
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


# ── sender (an email From header) ────────────────────────────────────────────

# Free webmail domains: anyone can hold an address there, so a website host on or under one of these
# is not a domain basis and a sender on one is flagged free_mail_domain (P103). The list is fixed and
# incomplete; the domain basis is the website host alone, so a contact's mailbox domain, listed here
# or not, never makes other senders there candidates. A brand contact who writes from one still
# matches by the exact address.
FREE_MAIL_DOMAINS = frozenset({
    "gmail.com", "googlemail.com", "outlook.com", "hotmail.com", "hotmail.co.uk", "live.com",
    "msn.com", "yahoo.com", "yahoo.co.uk", "ymail.com", "rocketmail.com", "icloud.com", "me.com",
    "mac.com", "aol.com", "proton.me", "protonmail.com", "pm.me", "gmx.com", "gmx.net", "gmx.de",
    "zoho.com", "zohomail.com", "yandex.com", "mail.com", "fastmail.com", "hey.com",
    "tutanota.com", "tuta.io", "web.de", "qq.com", "163.com",
})
SENDER_HEADER_MAX = 2048   # characters of a From header read; a longer one is not matched
SENDER_NAME_MAX = 200      # characters of a display name compared against account names


def _a_labels(host):
    """host with each non-ASCII label written as its punycode A-label ("xn--" + punycode of the
    NFC label), mapping nothing: "glaßhouse.example" stays apart from "glasshouse.example", as
    IDNA2008 keeps them, where the stdlib "idna" codec (IDNA2003) maps ß to "ss" and drops joiners
    and soft hyphens. "" when a label cannot be encoded."""
    import unicodedata
    out = []
    for label in unicodedata.normalize("NFC", host).split("."):
        if label.isascii():
            out.append(label)
            continue
        try:
            out.append("xn--" + label.encode("punycode").decode("ascii"))
        except UnicodeError:
            return ""
    return ".".join(out)


def _host(value):
    """The lowercase ASCII host of a domain or URL ("https://www.Brand.example/shop" ->
    "brand.example"), each non-ASCII label as its A-label (_a_labels), so a Unicode and a punycode
    spelling of one domain compare equal; or ""."""
    s = str(value or "").strip().lower()
    if not s:
        return ""
    if "//" in s:
        s = s.split("//", 1)[1]
    s = s.split("/", 1)[0].split("?", 1)[0].split("#", 1)[0].rsplit("@", 1)[-1].split(":", 1)[0]
    s = s.rstrip(".")
    if s.startswith("www."):
        s = s[4:]
    return _a_labels(s)


def _address(value):
    """A lowercase address with its domain through _host, or "" when value is not one address."""
    s = str(value or "").strip().lower()
    local, at, domain = s.rpartition("@")
    if not at or not local or not domain or any(c.isspace() for c in s):
        return ""
    host = _host(domain)
    return f"{local}@{host}" if host else ""


def _homepage_host(url, free=FREE_MAIL_DOMAINS):
    """The host of a website field when it is a homepage address: no user part, no path beyond "/",
    and a host not equal to or under a domain in free. "" otherwise: a page on a shared platform
    ("https://social.example/brand") or a URL with a user part names a host the brand does not
    own."""
    s = str(url or "").strip()
    rest = s.split("//", 1)[1] if "//" in s else s
    authority, slash, path = rest.split("?", 1)[0].split("#", 1)[0].partition("/")
    if "@" in authority or path.strip("/"):
        return ""
    host = _host(authority)
    if not host or any(host == d or host.endswith("." + d) for d in free):
        return ""
    return host


def _sender_domains(acct, free=FREE_MAIL_DOMAINS):
    """The domains a sender may share with this account: its website host, when the website is a
    homepage address (_homepage_host). A contact's mailbox domain is not one: it may be a free or
    ISP mailbox domain that FREE_MAIL_DOMAINS does not list."""
    site = _homepage_host(acct.get("website"), free)
    return {site} if site else set()


def resolve_sender(from_header, accounts=None, free_mail=None):
    """Which account an email sender belongs to, by ADDRESS (P103). `resolved` is set only when the
    address is a contact email on exactly one account. A sender whose domain equals, or is a
    subdomain of, an account's website host (a homepage address, _homepage_host) is a candidate
    for the human to confirm (`domain_candidate`), never resolved: anyone at a company can write,
    and a domain says nothing about which person. A domain on FREE_MAIL_DOMAINS is not matched by
    domain. The header is split into name and address before any decoding, and only the display
    name is decoded: an address holding an encoded word (RFC 2047 keeps them out of an address) is
    flagged `encoded_address` and not matched. The display name is not used to match; when it
    names an account the address does not match, the result carries the flag
    `display_name_names_another_account` (what a spoofed brand email looks like). free_mail stands
    in for FREE_MAIL_DOMAINS (the selftest passes .example names, so no address at a real provider
    is written into the repo)."""
    from email.errors import HeaderParseError
    from email.header import decode_header, make_header
    from email.utils import parseaddr
    accts = load_accounts(accounts)
    free = FREE_MAIL_DOMAINS if free_mail is None else frozenset(free_mail)
    result = {"sender": {"name": None, "email": None}, "domain": None, "resolution": "none",
              "resolved": None, "candidates": [], "flags": [],
              "computed_by": f"{TOOL}.resolve_sender", "gaps": []}
    raw = str(from_header or "")
    if len(raw) > SENDER_HEADER_MAX:
        result["flags"].append("header_too_long")
        result["gaps"].append(f"the From header is longer than {SENDER_HEADER_MAX} characters; not matched")
        return result
    name, raw_addr = parseaddr(raw)
    try:
        name = str(make_header(decode_header(name)))
    except (ValueError, LookupError, UnicodeError, HeaderParseError):
        pass
    name = name.strip()[:SENDER_NAME_MAX]
    if "=?" in raw_addr:
        result["sender"] = {"name": name or None, "email": None}
        result["flags"].append("encoded_address")
        result["gaps"].append("the sender address is written as an encoded word, which an address "
                              "cannot be; not matched")
        return result
    addr = _address(raw_addr)
    result["sender"] = {"name": name or None, "email": addr or None}
    if not addr:
        result["flags"].append("no_address")
        result["gaps"].append("no single sender address could be read from the From header")
        return result
    if not accts:
        result["gaps"].append("no account records available (fresh clone or empty store)")
        return result
    domain = addr.rsplit("@", 1)[1]
    result["domain"] = domain

    exact = []
    for a in accts:
        for c in _all_contacts(a):
            if _address(c.get("email")) == addr:
                exact.append((a, c))
                break
    if len(exact) == 1:
        a, c = exact[0]
        result["resolution"] = "contact_email"
        result["resolved"] = {"account_id": a.get("account_id"), "brand_name": a.get("brand_name"),
                              "contact": {"name": c.get("name"), "email": c.get("email"),
                                          "role": c.get("role"), "kind": c.get("kind")}}
    elif len(exact) > 1:
        result["resolution"] = "contact_email_ambiguous"
        result["candidates"] = [{"account_id": a.get("account_id"), "brand_name": a.get("brand_name"),
                                 "match_basis": "contact_email"} for a, _ in exact]
        result["flags"].append("address_on_several_accounts")
        result["gaps"].append("this address is a contact on more than one account; ask the human which")
    elif domain in free:
        result["flags"].append("free_mail_domain")
        result["gaps"].append("a free webmail address that no account lists; not matched by domain")
    else:
        for a in accts:
            for d in sorted(_sender_domains(a, free)):
                if domain == d or domain.endswith("." + d):
                    result["candidates"].append({"account_id": a.get("account_id"),
                                                 "brand_name": a.get("brand_name"),
                                                 "match_basis": "domain" if domain == d else "subdomain"})
                    break
        if result["candidates"]:
            result["resolution"] = "domain_candidate"
            result["gaps"].append("the sender's domain matches an account but the address is not a "
                                  "contact on record; the human confirms who this is")
        else:
            result["gaps"].append("no account lists this address or its domain")

    if name:
        named = (resolve(name, accts).get("resolved") or {}).get("account_id")
        matched = {result["resolved"]["account_id"]} if result["resolved"] else set()
        matched |= {c["account_id"] for c in result["candidates"]}
        if named and named not in matched:
            result["flags"].append("display_name_names_another_account")
            result["gaps"].append("the display name names an account the address does not belong to "
                                  "(a spoofed sender looks like this)")
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
     "website": "https://www.hearthlinehome.example",
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

    # P103: a sender is matched by address, never by display name
    def _snd(header, roster=_ROSTER):
        return resolve_sender(header, roster)

    s = _snd("Marcus Webb <marcus.webb@hearthlinehome.example>")
    ok("a contact's address resolves to its account",
       s["resolution"] == "contact_email" and s["resolved"]["account_id"] == "acct-hearthline-001"
       and s["resolved"]["contact"]["kind"] == "primary" and not s["flags"])
    s = _snd("MARCUS.WEBB@HearthlineHome.example")
    ok("address matching ignores letter case",
       s["resolution"] == "contact_email" and s["resolved"]["account_id"] == "acct-hearthline-001")
    s = _snd("Dana <dana.ellis@hearthlinehome.example>")
    ok("a secondary contact's address resolves",
       s["resolved"] and s["resolved"]["contact"]["kind"] == "secondary")
    s = _snd("New Person <jo@hearthlinehome.example>")
    ok("an unknown address on the website's host is a candidate, not resolved",
       s["resolution"] == "domain_candidate" and s["resolved"] is None
       and [c["account_id"] for c in s["candidates"]] == ["acct-hearthline-001"]
       and s["candidates"][0]["match_basis"] == "domain")
    s = _snd("Ops <billing@mail.hearthlinehome.example>")
    ok("a subdomain of the website's host is a candidate",
       s["resolution"] == "domain_candidate" and s["candidates"][0]["match_basis"] == "subdomain")
    s = _snd("Hearthline Home <jo@hearthlinehome.example>")
    ok("a display name naming the candidate's own account is not flagged",
       s["resolution"] == "domain_candidate" and "display_name_names_another_account" not in s["flags"])
    _caps = [dict(_ROSTER[2], primary_contact={"name": "Sam Ortega", "email": "Sam@LumenCo.example",
                                               "role": "Founder"})]
    _twice = [dict(_ROSTER[0], secondary_contacts=[{"name": "Marcus Webb",
                                                    "email": "marcus.webb@hearthlinehome.example"}])]
    s = _snd("Marcus <marcus.webb@hearthlinehome.example>", _twice)
    ok("a record address in capitals matches, and an address listed twice on one account resolves",
       _snd("sam@lumenco.example", _caps)["resolution"] == "contact_email"
       and s["resolution"] == "contact_email" and not s["flags"])
    ok("a trailing dot on the sender's domain is the same address",
       _snd("marcus.webb@hearthlinehome.example.")["resolution"] == "contact_email")
    s = _snd("Marcus <marcus webb@hearthlinehome.example>")
    ok("an address with a space in it is not read",
       s["resolution"] == "none" and "no_address" in s["flags"])
    _glass = [{"account_id": "acct-glass-001", "brand_name": "Glasshouse Goods", "aliases": [],
               "primary_contact": {"name": "Lee", "email": "lee@glasshouse.example"}}]
    _glass_a = [{"account_id": "acct-glass-002", "brand_name": "Glasshouse Goods", "aliases": [],
                 "primary_contact": {"name": "Lee", "email": "lee@xn--glahouse-sya.example"}}]
    ok("an eszett domain is not the ss domain, and its Unicode and A-label spellings are one address",
       _host("gla\u00dfhouse.example") == "xn--glahouse-sya.example"
       and _snd("Lee <lee@gla\u00dfhouse.example>", _glass)["resolution"] == "none"
       and _snd("Lee <lee@gla\u00dfhouse.example>", _glass_a)["resolution"] == "contact_email")
    ok("a fullwidth or soft-hyphen spelling of a brand's domain is not that domain",
       _snd("marcus.webb@ｈｅａｒｔｈｌｉｎｅｈｏｍｅ"
            ".example")["resolution"] == "none"
       and _snd("marcus.webb@hearthline­home.example")["resolution"] == "none")
    for _hdr in ("X <=?utf-8?q?marcus.webb=40hearthlinehome.example?=>",
                 "=?utf-8?b?bWFyY3VzLndlYmJAaGVhcnRobGluZWhvbWUuZXhhbXBsZQ==?="):
        s = _snd(_hdr)
        ok(f"an address written as an encoded word is flagged and not matched ({_hdr[:12]})",
           s["resolution"] == "none" and "encoded_address" in s["flags"] and s["sender"]["email"] is None)
    s = _snd("=?x-unknown?q?abc?= <marcus.webb@hearthlinehome.example>")
    ok("a display name in an unknown charset keeps the address",
       s["resolution"] == "contact_email" and s["sender"]["name"] == "=?x-unknown?q?abc?=")
    s = _snd("x" * 2100 + " <marcus.webb@hearthlinehome.example>")
    ok("an over-long header is not matched even when it carries a contact's address",
       s["resolution"] == "none" and s["resolved"] is None and "header_too_long" in s["flags"])
    s = _snd("Hearthline Home <billing@phish.example>")
    ok("a display name naming an account does not match it, and is flagged",
       s["resolution"] == "none" and s["resolved"] is None and not s["candidates"]
       and "display_name_names_another_account" in s["flags"])
    ok("a look-alike domain that starts with a brand's host and goes on does not match",
       _snd("Sam <marcus.webb@hearthlinehome.example.phish.example>")["resolution"] == "none")
    ok("a domain that merely ends with the same letters does not match",
       _snd("x <x@evil-hearthlinehome.example>")["resolution"] == "none")
    _free = {"freemail.example"}
    s = resolve_sender("Sam Ortega <sam.ortega@freemail.example>", _ROSTER, free_mail=_free)
    ok("a free webmail domain is not matched by domain",
       s["resolution"] == "none" and "free_mail_domain" in s["flags"])
    _gm = [{"account_id": "acct-gm-001", "brand_name": "Kiln Studio", "aliases": [],
            "primary_contact": {"name": "Ana", "email": "kiln.studio@freemail.example", "role": "Owner"}}]
    ok("a contact's mailbox domain is not a domain basis, on the free list or off it",
       resolve_sender("Ana <kiln.studio@freemail.example>", _gm, free_mail=_free)["resolution"] == "contact_email"
       and resolve_sender("Other <someone@freemail.example>", _gm, free_mail=_free)["resolution"] == "none"
       and resolve_sender("Other <someone@freemail.example>", _gm, free_mail=())["resolution"] == "none")
    ok("the free webmail list holds the large providers",
       {"gmail.com", "outlook.com", "yahoo.com", "icloud.com", "hotmail.com"} <= FREE_MAIL_DOMAINS)

    def _site(url):
        return [{"account_id": "acct-site-001", "brand_name": "Oakline Tools", "aliases": [],
                 "website": url, "primary_contact": {}}]
    s = _snd("Press <press@oaklinetools.example>", _site("https://www.oaklinetools.example/"))
    ok("a homepage website host makes the domain a candidate",
       s["resolution"] == "domain_candidate" and s["candidates"][0]["account_id"] == "acct-site-001")
    ok("a website with a port is read by its host",
       _snd("press@oaklinetools.example", _site("https://oaklinetools.example:8443/"))["resolution"]
       == "domain_candidate")
    ok("a website that is a page on another host, or that has a user part, is not a domain basis",
       _snd("promo@social.example", _site("https://www.social.example/oaklinetools"))["resolution"] == "none"
       and _snd("x@evil.example", _site("https://oaklinetools.example@evil.example/"))["resolution"] == "none"
       and _snd("x@oaklinetools.example", _site("https://oaklinetools.example@evil.example/"))["resolution"]
       == "none")
    ok("a website host on, or under, a free webmail domain is not a domain basis",
       resolve_sender("x@mail.freemail.example", _site("https://freemail.example/"),
                      free_mail=_free)["resolution"] == "none"
       and resolve_sender("x@shop.freemail.example", _site("https://shop.freemail.example/"),
                          free_mail=_free)["resolution"] == "none"
       and resolve_sender("x@shop.freemail.example", _site("https://shop.freemail.example/"),
                          free_mail=())["resolution"] == "domain_candidate")
    _dup = [dict(_ROSTER[0]), {"account_id": "acct-dup-001", "brand_name": "Other Brand", "aliases": [],
                               "primary_contact": {"name": "Marcus Webb",
                                                   "email": "marcus.webb@hearthlinehome.example"}}]
    s = _snd("marcus.webb@hearthlinehome.example", _dup)
    ok("an address on two accounts is not resolved",
       s["resolved"] is None and "address_on_several_accounts" in s["flags"] and len(s["candidates"]) == 2)
    ok("no address, an over-long header and an empty store are reported, not matched",
       "no_address" in _snd("not an address")["flags"]
       and "header_too_long" in _snd("a" * (SENDER_HEADER_MAX + 1))["flags"]
       and _snd("marcus.webb@hearthlinehome.example", [])["resolution"] == "none")
    s = _snd("=?utf-8?b?SGVhcnRobGluZSBIb21l?= <billing@phish.example>")
    ok("an encoded display name is decoded before the spoof check",
       "display_name_names_another_account" in s["flags"] and s["sender"]["name"] == "Hearthline Home")
    red_s = redact(_snd("Marcus Webb <marcus.webb@hearthlinehome.example>"))
    ok("a redacted sender result masks the brand, the contact and the address",
       red_s["resolved"]["brand_name"] == "H.H." and red_s["sender"]["email"].startswith("m***@")
       and red_s["resolved"]["contact"]["name"] == "M.W.")

    # redaction
    red = redact({"name": "Marcus Webb", "email": "marcus.webb@hearthlinehome.example",
                  "account_id": "acct-hearthline-001"})
    ok("name redacts to initials", red["name"] == "M.W.")
    ok("email masked", red["email"] == "m***@h***.example")
    ok("account_id stays clear", red["account_id"] == "acct-hearthline-001")

    # P64 whole-path boundary case: a >NAME_MAX (255-byte) --records arg must yield the clean
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
    ap.add_argument("--sender", metavar="FROM", help="the account an email From header belongs to")
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
    elif args.sender is not None:
        result = resolve_sender(args.sender, accts)
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
