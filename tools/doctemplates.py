#!/usr/bin/env python3
"""Creator OS document-template engine (P42): validate, inspect, assemble, and diff
block-structured creator document templates (contracts, rate-card display docs, analytics
overviews, terms/conditions).

The authorship boundary, mechanically enforced here: this tool NEVER authors document text.
Assembly is pure concatenation of stored block bodies plus [BRACKETED_FIELD] substitution.
vetted_text bodies (the creator's attorney-provided language) pass through byte-for-byte apart
from bracket substitution; a selftest proves it. Selection logic only includes, excludes, or
swaps WHOLE blocks under the template's own structural rules (variant groups, never_with,
requires); advisory `applicability.conditions` strings are for the model and are never evaluated
here.

Read-only commands (always available, no flags): validate, list, list-blocks, assemble (prints
JSON), diff, --selftest. Writing an assembled document to disk (--write --out) is gated by the
`document_templates` capability flag; contract-type documents additionally require
`contract_management` and `contract_drafting`. When a flag is off the assembly is computed and
returned with a `_gate` message, and nothing is written (mirrors tools/obligations.py).

Templates are written by the human only; this tool never creates or modifies a template file.
Real templates live in gitignored pipeline/templates/*.local.json; the committed *.template.json
starters are all-null shapes (drift invariant 31). CREATOR_OS_ROOT redirects all paths for
sandboxed runs, exactly like obligations.py.

Usage:
  python3 tools/doctemplates.py validate <template-path-or-id>
  python3 tools/doctemplates.py list
  python3 tools/doctemplates.py list-blocks <template-path-or-id>
  python3 tools/doctemplates.py assemble <template-path-or-id> --select <selections.json>
      [--deal <deal_id>] [--data analytics_export=<path.local.json>] [--fills <fills.json>]
      [--write --out <path.local.md>]
  python3 tools/doctemplates.py diff <proposed.json> <saved.json>
  python3 tools/doctemplates.py --selftest
"""
import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import obligations as _ob  # noqa: E402  (load_config / flag_enabled, the repo flag-gate pattern)

ROOT = Path(os.environ.get("CREATOR_OS_ROOT", str(Path(__file__).resolve().parent.parent)))
TOOL = "tools/doctemplates.py"
DOC_TYPES = ("contract", "rate_card", "analytics_overview", "terms_conditions")
KINDS = ("vetted_text", "plain_language", "data_fill", "table")
RESEARCH_BANNER = ("RESEARCH NOTES. NOT LEGAL ADVICE. REVIEW WITH A LICENSED ATTORNEY IN YOUR "
                   "JURISDICTION BEFORE ACTING.")
GATE_HINT = ("enable it in creator-os-config.local.json or one click at the setup wizard's "
             "/brand-deals screen (python3 tools/wizard.py)")


def _templates_dir():
    return ROOT / "pipeline" / "templates"


def _read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_template(ref):
    """Resolve a template by path or id. Ids resolve local-first: pipeline/templates/<id>.local.json,
    then <id>.template.json. Returns (data, source_path_str). Raises FileNotFoundError."""
    p = Path(ref)
    if p.exists() and p.is_file():
        return _read_json(p), str(p)
    for cand in (_templates_dir() / f"{ref}.local.json", _templates_dir() / f"{ref}.template.json"):
        if cand.exists():
            return _read_json(cand), str(cand)
    raise FileNotFoundError(f"no template at {ref!r} and no pipeline/templates/{ref}.local.json "
                            f"or .template.json")


# --------------------------------------------------------------------------- validate

_BRACKET_RE_CACHE = {}


def _bracket_re(template):
    conv = template.get("fill_conventions") or {}
    op = re.escape(conv.get("bracket_open", "[") or "[")
    cl = re.escape(conv.get("bracket_close", "]") or "]")
    key = (op, cl)
    if key not in _BRACKET_RE_CACHE:
        _BRACKET_RE_CACHE[key] = re.compile(f"{op}([A-Z0-9_]+){cl}")
    return _BRACKET_RE_CACHE[key]


def validate_template(template, filename=""):
    """Returns (errors, warnings). Structural only; never judges body content."""
    errors, warnings = [], []
    if template.get("doc_type") not in DOC_TYPES:
        errors.append(f"doc_type {template.get('doc_type')!r} not in {list(DOC_TYPES)}")
    blocks = template.get("blocks") or []
    ids = [b.get("block_id") for b in blocks]
    for bid in {i for i in ids if ids.count(i) > 1}:
        errors.append(f"duplicate block_id: {bid}")
    id_set = set(ids)
    groups = template.get("variant_groups") or {}
    members = {}
    for b in blocks:
        g = b.get("variant_group")
        if g:
            members.setdefault(g, []).append(b["block_id"])
            if g not in groups:
                errors.append(f"block {b['block_id']} names variant_group {g!r} not declared in "
                              "variant_groups")
    for g, meta in groups.items():
        if g not in members:
            errors.append(f"variant_group {g!r} has no member blocks")
        elif meta.get("default_block") and meta["default_block"] not in members[g]:
            errors.append(f"variant_group {g!r} default_block {meta['default_block']!r} is not a "
                          "member of the group")
    br = _bracket_re(template)
    is_starter = filename.endswith(".template.json")
    for b in blocks:
        bid = b.get("block_id", "<missing>")
        if b.get("kind") not in KINDS:
            errors.append(f"block {bid}: kind {b.get('kind')!r} not in {list(KINDS)}")
        if b.get("body") is not None and b.get("body_ref") is not None:
            errors.append(f"block {bid}: body and body_ref are mutually exclusive")
        for rel in ("never_with", "requires"):
            for other in (b.get("applicability") or {}).get(rel, []):
                if other not in id_set:
                    errors.append(f"block {bid}: {rel} names unknown block {other!r}")
        body = b.get("body")
        declared = {f.get("field") for f in b.get("fill_fields", [])}
        if body is not None:
            body_tokens = {m.group(0) for m in br.finditer(body)}
            for f in declared:
                if f and f not in body_tokens:
                    errors.append(f"block {bid}: declared fill field {f} does not appear in body")
            undeclared = body_tokens - {d for d in declared if d}
            for tok in sorted(undeclared):
                msg = f"block {bid}: bracket token {tok} in body has no fill_fields declaration"
                if b.get("kind") == "vetted_text":
                    errors.append(msg)
                else:
                    warnings.append(msg)
        if is_starter:
            if body is not None:
                errors.append(f"starter block {bid}: body must be null (shape only; real text "
                              "lives in gitignored .local files)")
            if b.get("body_ref") is not None:
                errors.append(f"starter block {bid}: body_ref must be null")
            if (b.get("provenance") or {}).get("source_ref") is not None:
                errors.append(f"starter block {bid}: provenance.source_ref must be null")
    if is_starter and template.get("vetted") is not False:
        errors.append("starter: vetted must be false")
    return errors, warnings


# --------------------------------------------------------------------------- selection

def resolve_selection(template, selections):
    """Structural selection resolution. Returns (active_ids_in_template_order, errors).
    default_on -> variant-group defaults -> variants{} -> include/exclude -> never_with/requires.
    Violations are hard errors; nothing is silently dropped."""
    selections = selections or {}
    errors = []
    blocks = template.get("blocks") or []
    by_id = {b["block_id"]: b for b in blocks}
    groups = template.get("variant_groups") or {}
    members = {}
    for b in blocks:
        if b.get("variant_group"):
            members.setdefault(b["variant_group"], []).append(b["block_id"])

    active = {b["block_id"] for b in blocks if (b.get("applicability") or {}).get("default_on")}
    for g, meta in groups.items():
        mem = set(members.get(g, []))
        active -= mem
        chosen = (selections.get("variants") or {}).get(g, meta.get("default_block"))
        if chosen is not None:
            if chosen not in mem:
                errors.append(f"variant_group {g}: selected block {chosen!r} is not a member")
            else:
                active.add(chosen)
    for bid in selections.get("include", []):
        if bid not in by_id:
            errors.append(f"include names unknown block {bid!r}")
        else:
            active.add(bid)
    for bid in selections.get("exclude", []):
        if bid not in by_id:
            errors.append(f"exclude names unknown block {bid!r}")
        else:
            active.discard(bid)
    for g, meta in groups.items():
        live = [m for m in members.get(g, []) if m in active]
        if len(live) > 1:
            errors.append(f"variant_group {g}: {len(live)} members active ({', '.join(live)}); "
                          "exactly one variant may be included")
        if not live and meta.get("required"):
            errors.append(f"variant_group {g}: required but no member is active")
    for bid in sorted(active):
        app = (by_id[bid].get("applicability") or {})
        for other in app.get("never_with", []):
            if other in active:
                errors.append(f"block {bid} never_with {other}: both active")
        for req in app.get("requires", []):
            if req not in active:
                errors.append(f"block {bid} requires {req}: not active")
    ordered = [b["block_id"] for b in blocks if b["block_id"] in active]
    return ordered, errors


# --------------------------------------------------------------------------- fill sources

def _load_local_json(path):
    p = Path(path)
    if not p.exists():
        return None
    try:
        return _read_json(p)
    except (OSError, json.JSONDecodeError):
        return None


_SEG_RE = re.compile(r"([A-Za-z0-9_]+)|\[([A-Za-z0-9_]+)=([^\]]+)\]|\[(\d+)\]")


def resolve_source_path(data, path):
    """Dotted path with [key=value] list selectors and [N] indexes:
    'rates[format=tiktok_dedicated].base_rate', 'top_performers[0].title', 'brand_name'."""
    if data is None or path is None:
        return None
    cur = data
    for part in path.split("."):
        pos = 0
        while pos < len(part):
            m = _SEG_RE.match(part, pos)
            if not m:
                return None
            name, selk, selv, idx = m.group(1), m.group(2), m.group(3), m.group(4)
            if name is not None:
                if not isinstance(cur, dict) or name not in cur:
                    return None
                cur = cur[name]
            elif idx is not None:
                i = int(idx)
                if not isinstance(cur, list) or i >= len(cur):
                    return None
                cur = cur[i]
            else:
                if not isinstance(cur, list):
                    return None
                cur = next((r for r in cur if isinstance(r, dict)
                            and str(r.get(selk)) == selv), None)
                if cur is None:
                    return None
            pos = m.end()
    return cur


def build_sources(deal_id=None, data_paths=None, root=None):
    """Load the offline fill sources. Missing files resolve to None (every lookup then gaps)."""
    base = Path(root) if root else ROOT
    sources = {
        "profile": _load_local_json(base / "pipeline" / "user-context"
                                    / "creator-profile.local.json"),
        "rate_card": _load_local_json(base / "pipeline" / "finance" / "rate-card.local.json"),
        "deal": _load_local_json(base / "pipeline" / "deals" / f"{deal_id}.local.json")
        if deal_id else None,
        "analytics_export": None,
    }
    for spec in (data_paths or []):
        key, _, path = spec.partition("=")
        if ".local." not in Path(path).name:
            raise ValueError(f"--data {key} path must be a .local. file (never repo data): {path}")
        sources[key] = _load_local_json(path)
    return sources


# --------------------------------------------------------------------------- assemble

def assemble(template, selections, sources=None, fills=None, template_path=""):
    """Pure concatenation + bracket substitution over the selected blocks. Never authors text."""
    sources = sources or {}
    fills = fills or {}
    active, sel_errors = resolve_selection(template, selections)
    doc_type = template.get("doc_type")
    out = {"doc_type": doc_type, "template_id": template.get("template_id"),
           "template_source": template_path, "document_text": None,
           "blocks_used": [], "selection_resolved": active, "selection_errors": sel_errors,
           "gaps": [], "human_review_required": True,
           "computed_by": f"{TOOL} assemble",
           "provenance": {"generated_by": TOOL}}
    if doc_type in ("contract", "terms_conditions"):
        out["ready_to_sign"] = False
        out["recommend_counsel"] = True
    if sel_errors:
        return out
    by_id = {b["block_id"]: b for b in template.get("blocks") or []}
    br = _bracket_re(template)
    pieces = []
    if doc_type in ("contract", "terms_conditions"):
        pieces.append(RESEARCH_BANNER)
    for bid in active:
        b = by_id[bid]
        body = b.get("body")
        if body is None and b.get("body_ref"):
            ref = ROOT / b["body_ref"] if not Path(b["body_ref"]).is_absolute() \
                else Path(b["body_ref"])
            if ".local." not in ref.name:
                out["gaps"].append({"field": None, "source": None, "source_path": b["body_ref"],
                                    "block_id": bid,
                                    "recommended_next_step": "body_ref must point at a gitignored "
                                                             ".local. file"})
                continue
            body = ref.read_text(encoding="utf-8") if ref.exists() else None
        if body is None:
            out["gaps"].append({"field": None, "source": None, "source_path": None,
                                "block_id": bid,
                                "recommended_next_step": f"block '{bid}' has no body; fill the "
                                "template (.local.json) before assembling"})
            continue
        for f in b.get("fill_fields", []):
            token = f.get("field")
            if not token:
                continue
            src, spath = f.get("source"), f.get("source_path")
            if src == "manual":
                value = fills.get(token, fills.get(token.strip("[]")))
            else:
                value = resolve_source_path(sources.get(src), spath)
            if value is not None:
                body = body.replace(token, str(value))
            else:
                out["gaps"].append({
                    "field": token, "source": src, "source_path": spath, "block_id": bid,
                    "recommended_next_step":
                        (f"fill {spath} in creator-profile.local.json" if src == "profile" else
                         f"fill {spath} in rate-card.local.json" if src == "rate_card" else
                         f"supply --fills {token}" if src == "manual" else
                         f"supply the {src} source ({spath})")})
        pieces.append(body)
        out["blocks_used"].append({
            "block_id": bid, "kind": b.get("kind"), "body_source": b.get("body_source"),
            "provenance_tag": ("creator_vetted_text" if b.get("kind") == "vetted_text"
                               else "data_fill" if b.get("kind") in ("data_fill", "table")
                               else "plain_language_summary")})
    out["document_text"] = "\n\n".join(pieces)
    return out


def _write_allowed(config, doc_type):
    """(ok, reason). document_templates always required; contract types also need the two
    contract flags. Compute is never gated; only persistence is."""
    if not _ob.flag_enabled(config, "document_templates"):
        return False, (f"document_templates is off: document computed but NOT written; {GATE_HINT}")
    if doc_type in ("contract", "terms_conditions"):
        for flag in ("contract_management", "contract_drafting"):
            if not _ob.flag_enabled(config, flag):
                return False, (f"{flag} is off: a {doc_type} document is computed but NOT "
                               f"written; {GATE_HINT}")
    return True, ""


# --------------------------------------------------------------------------- diff

def _body_hash(b):
    body = b.get("body")
    return hashlib.sha256(body.encode("utf-8")).hexdigest() if body is not None else None


def diff_templates(proposed, saved):
    """Block-level review diff of a template-ingest proposal against the saved template."""
    pb = {b["block_id"]: b for b in proposed.get("blocks") or []}
    sb = {b["block_id"]: b for b in saved.get("blocks") or []}
    added = sorted(set(pb) - set(sb))
    removed = sorted(set(sb) - set(pb))
    changed = []
    for bid in sorted(set(pb) & set(sb)):
        entry = {"block_id": bid, "changes": []}
        if _body_hash(pb[bid]) != _body_hash(sb[bid]):
            entry["changes"].append("body")
        for key in ("fill_fields", "applicability", "variant_group", "variant_label", "kind"):
            if pb[bid].get(key) != sb[bid].get(key):
                entry["changes"].append(key)
        if entry["changes"]:
            changed.append(entry)
    return {"added_blocks": added, "removed_blocks": removed, "changed_blocks": changed,
            "variant_groups_changed":
                proposed.get("variant_groups") != saved.get("variant_groups"),
            "computed_by": f"{TOOL} diff", "human_review_required": True}


# --------------------------------------------------------------------------- selftest

def _selftest():
    import tempfile

    checks = {"n": 0, "fail": 0}

    def _check(label, ok):
        checks["n"] += 1
        if ok:
            print(f"  [ok] {label}")
        else:
            checks["fail"] += 1
            print(f"  [FAIL] {label}")

    fix = {
        "schema_version": "1.0", "template_id": "fx", "doc_type": "contract", "title": "fx",
        "vetted": True, "fill_conventions": {"bracket_open": "[", "bracket_close": "]"},
        "variant_groups": {"usage": {"required": True, "default_block": "usage_a"}},
        "blocks": [
            {"block_id": "parties", "kind": "vetted_text", "body_source": "creator_upload",
             "body": "This Agreement is between [CREATOR_LEGAL_NAME] and [BRAND_LEGAL_NAME].",
             "fill_fields": [
                 {"field": "[CREATOR_LEGAL_NAME]", "source": "profile",
                  "source_path": "legal_name", "required": True},
                 {"field": "[BRAND_LEGAL_NAME]", "source": "deal",
                  "source_path": "brand_name", "required": True}],
             "applicability": {"default_on": True, "conditions": [], "never_with": [],
                               "requires": []}},
            {"block_id": "usage_a", "kind": "vetted_text", "body_source": "creator_upload",
             "body": "License is organic only for [LICENSE_DURATION].",
             "fill_fields": [{"field": "[LICENSE_DURATION]", "source": "manual",
                              "source_path": None, "required": True}],
             "applicability": {"default_on": True, "conditions": [], "never_with": [],
                               "requires": []},
             "variant_group": "usage", "variant_label": "organic"},
            {"block_id": "usage_b", "kind": "vetted_text", "body_source": "creator_upload",
             "body": "License includes paid media for [LICENSE_DURATION].",
             "fill_fields": [{"field": "[LICENSE_DURATION]", "source": "manual",
                              "source_path": None, "required": True}],
             "applicability": {"default_on": False, "conditions": [], "never_with": [],
                               "requires": []},
             "variant_group": "usage", "variant_label": "paid"},
            {"block_id": "exclusivity", "kind": "vetted_text", "body_source": "creator_upload",
             "body": "Category exclusivity applies for the stated window.",
             "fill_fields": [],
             "applicability": {"default_on": True, "conditions": [], "never_with": [],
                               "requires": []}},
            {"block_id": "boost", "kind": "vetted_text", "body_source": "creator_upload",
             "body": "Brand may boost the content.",
             "fill_fields": [],
             "applicability": {"default_on": False, "conditions": [], "never_with": [],
                               "requires": ["usage_b"]}},
            {"block_id": "rate_row", "kind": "data_fill", "body_source": "system_plain_language",
             "body": "Dedicated video rate: [RATE_LONG_FORM] USD.",
             "fill_fields": [{"field": "[RATE_LONG_FORM]", "source": "rate_card",
                              "source_path": "rates[format=youtube_dedicated_long_form].base_rate",
                              "required": False}],
             "applicability": {"default_on": True, "conditions": [], "never_with": [],
                               "requires": []}},
        ],
        "human_review_required": True,
    }

    errs, warns = validate_template(fix, "fx.local.json")
    _check("validate: clean fixture has no errors", errs == [])

    bad = json.loads(json.dumps(fix))
    bad["blocks"].append(dict(bad["blocks"][0]))
    errs, _ = validate_template(bad, "fx.local.json")
    _check("validate: duplicate block_id caught", any("duplicate block_id" in e for e in errs))

    bad = json.loads(json.dumps(fix))
    bad["blocks"][0]["body"] += " Governed by [GOVERNING_LAW_STATE]."
    errs, _ = validate_template(bad, "fx.local.json")
    _check("validate: undeclared bracket in vetted_text is an error",
           any("no fill_fields declaration" in e for e in errs))

    bad = json.loads(json.dumps(fix))
    bad["blocks"][1]["variant_group"] = "ghost"
    errs, _ = validate_template(bad, "fx.local.json")
    _check("validate: dangling variant_group caught",
           any("not declared in variant_groups" in e for e in errs))

    errs, _ = validate_template(fix, "fx.template.json")
    _check("validate: non-null body in a committed starter is an error",
           any("body must be null" in e for e in errs))

    active, errs = resolve_selection(fix, {})
    _check("select: defaults = parties + usage_a + exclusivity + rate_row",
           active == ["parties", "usage_a", "exclusivity", "rate_row"] and errs == [])

    active, errs = resolve_selection(fix, {"variants": {"usage": "usage_b"},
                                           "exclude": ["exclusivity"]})
    _check("select: variant swap + exclude",
           active == ["parties", "usage_b", "rate_row"] and errs == [])

    _, errs = resolve_selection(fix, {"include": ["usage_b"]})
    _check("select: two members of one variant group is a hard error",
           any("exactly one variant" in e for e in errs))

    _, errs = resolve_selection(fix, {"exclude": ["usage_a"]})
    _check("select: empty required group is a hard error",
           any("required but no member" in e for e in errs))

    _, errs = resolve_selection(fix, {"include": ["boost"]})
    _check("select: requires violation caught (boost without usage_b)",
           any("requires usage_b" in e for e in errs))

    nw = json.loads(json.dumps(fix))
    nw["blocks"][3]["applicability"]["never_with"] = ["rate_row"]
    _, errs = resolve_selection(nw, {})
    _check("select: never_with violation caught", any("never_with" in e for e in errs))

    with tempfile.TemporaryDirectory() as td:
        (Path(td) / "pipeline" / "user-context").mkdir(parents=True)
        (Path(td) / "pipeline" / "finance").mkdir(parents=True)
        (Path(td) / "pipeline" / "deals").mkdir(parents=True)
        (Path(td) / "pipeline" / "user-context" / "creator-profile.local.json").write_text(
            json.dumps({"legal_name": "Fictional Creator LLC", "governing_law_state": None}),
            encoding="utf-8")
        (Path(td) / "pipeline" / "finance" / "rate-card.local.json").write_text(
            json.dumps({"rates": [{"format": "youtube_dedicated_long_form", "base_rate": 600}]}),
            encoding="utf-8")
        (Path(td) / "pipeline" / "deals" / "d1.local.json").write_text(
            json.dumps({"brand_name": "CoolBreeze"}), encoding="utf-8")
        sources = build_sources(deal_id="d1", root=td)
        res = assemble(fix, {"variants": {"usage": "usage_b"}, "exclude": ["exclusivity"]},
                       sources=sources, fills={"[LICENSE_DURATION]": "90 days"})
        text = res["document_text"]
        _check("assemble: contract banner is line 1",
               text.splitlines()[0] == RESEARCH_BANNER)
        _check("assemble: ready_to_sign false + recommend_counsel true",
               res["ready_to_sign"] is False and res["recommend_counsel"] is True)
        _check("assemble: profile + deal + rate_card + manual fills applied",
               "Fictional Creator LLC" in text and "CoolBreeze" in text
               and "600" in text and "90 days" in text)
        expected = fix["blocks"][2]["body"].replace("[LICENSE_DURATION]", "90 days")
        _check("assemble: vetted body byte-equal apart from substitution", expected in text)
        _check("assemble: excluded block text absent",
               "Category exclusivity" not in text)
        _check("assemble: organic-only variant text absent (swapped out)",
               "organic only" not in text)
        _check("assemble: no gaps for filled fields",
               all(g["field"] != "[CREATOR_LEGAL_NAME]" for g in res["gaps"]))

        res2 = assemble(fix, {}, sources=build_sources(root=td), fills={})
        gap_fields = {g["field"] for g in res2["gaps"]}
        _check("assemble: missing deal + manual fills stay bracketed and gapped",
               "[BRAND_LEGAL_NAME]" in res2["document_text"]
               and "[BRAND_LEGAL_NAME]" in gap_fields and "[LICENSE_DURATION]" in gap_fields)

        res3 = assemble(fix, {"include": ["usage_b"]})
        _check("assemble: selection errors abort with no document_text",
               res3["document_text"] is None and res3["selection_errors"])

        ok, reason = _write_allowed({"capabilities": {}}, "rate_card")
        _check("gate: write refused with document_templates off, names flag + wizard route",
               ok is False and "document_templates" in reason and "/brand-deals" in reason)
        ok, reason = _write_allowed(
            {"capabilities": {"document_templates": {"enabled": True}}}, "contract")
        _check("gate: contract type also needs contract_management",
               ok is False and "contract_management" in reason)
        ok, _ = _write_allowed(
            {"capabilities": {"document_templates": {"enabled": True},
                              "contract_management": {"enabled": True},
                              "contract_drafting": {"enabled": True}}}, "contract")
        _check("gate: all flags on allows the write", ok is True)

    prop = json.loads(json.dumps(fix))
    prop["blocks"][0]["body"] = "Changed body [CREATOR_LEGAL_NAME] [BRAND_LEGAL_NAME]."
    prop["blocks"].append({"block_id": "territory", "kind": "vetted_text",
                           "body_source": "creator_upload", "body": "US only.",
                           "fill_fields": [],
                           "applicability": {"default_on": False, "conditions": [],
                                             "never_with": [], "requires": []}})
    d = diff_templates(prop, fix)
    _check("diff: body hash change + added block detected",
           d["added_blocks"] == ["territory"]
           and any(c["block_id"] == "parties" and "body" in c["changes"]
                   for c in d["changed_blocks"]))

    _check("path: [key=value] selector",
           resolve_source_path({"rates": [{"format": "a", "base_rate": 1},
                                          {"format": "b", "base_rate": 2}]},
                               "rates[format=b].base_rate") == 2)
    _check("path: [N] index + missing path is None",
           resolve_source_path({"top": [{"t": "x"}]}, "top[0].t") == "x"
           and resolve_source_path({"top": []}, "top[0].t") is None)

    n, fails = checks["n"], checks["fail"]
    print(f"selftest: {'PASS' if not fails else 'FAIL'} ({n - fails} of {n} checks)")
    return 0 if not fails else 1


# --------------------------------------------------------------------------- CLI

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--selftest", action="store_true")
    sub = ap.add_subparsers(dest="cmd")
    sp = sub.add_parser("validate")
    sp.add_argument("template")
    sub.add_parser("list")
    sp = sub.add_parser("list-blocks")
    sp.add_argument("template")
    sp = sub.add_parser("assemble")
    sp.add_argument("template")
    sp.add_argument("--select", default=None)
    sp.add_argument("--deal", default=None)
    sp.add_argument("--data", action="append", default=[])
    sp.add_argument("--fills", default=None)
    sp.add_argument("--write", action="store_true")
    sp.add_argument("--out", default=None)
    sp = sub.add_parser("diff")
    sp.add_argument("proposed")
    sp.add_argument("saved")
    args = ap.parse_args(argv)

    if args.selftest:
        return _selftest()
    if args.cmd == "validate":
        data, path = load_template(args.template)
        errors, warnings = validate_template(data, Path(path).name)
        print(json.dumps({"template": path, "errors": errors, "warnings": warnings,
                          "computed_by": f"{TOOL} validate"}, indent=2))
        return 1 if errors else 0
    if args.cmd == "list":
        rows = []
        tdir = _templates_dir()
        if tdir.exists():
            for f in sorted(tdir.glob("*.json")):
                try:
                    t = _read_json(f)
                except (OSError, json.JSONDecodeError):
                    rows.append({"file": f.name, "error": "unreadable"})
                    continue
                rows.append({"file": f.name, "template_id": t.get("template_id"),
                             "doc_type": t.get("doc_type"), "vetted": t.get("vetted"),
                             "blocks": len(t.get("blocks") or []),
                             "variant_groups": sorted((t.get("variant_groups") or {}).keys()),
                             "source": "local" if ".local." in f.name else "starter"})
        print(json.dumps({"templates": rows, "computed_by": f"{TOOL} list"}, indent=2))
        return 0
    if args.cmd == "list-blocks":
        data, path = load_template(args.template)
        rows = [{"block_id": b.get("block_id"), "title": b.get("title"), "kind": b.get("kind"),
                 "clause_family": b.get("clause_family"),
                 "variant_group": b.get("variant_group"),
                 "variant_label": b.get("variant_label"),
                 "default_on": (b.get("applicability") or {}).get("default_on"),
                 "conditions": (b.get("applicability") or {}).get("conditions", []),
                 "never_with": (b.get("applicability") or {}).get("never_with", []),
                 "requires": (b.get("applicability") or {}).get("requires", [])}
                for b in data.get("blocks") or []]
        print(json.dumps({"template": path, "blocks": rows,
                          "computed_by": f"{TOOL} list-blocks"}, indent=2))
        return 0
    if args.cmd == "assemble":
        data, path = load_template(args.template)
        selections = _read_json(args.select) if args.select else {}
        fills = _read_json(args.fills) if args.fills else {}
        sources = build_sources(deal_id=args.deal, data_paths=args.data)
        result = assemble(data, selections, sources=sources, fills=fills, template_path=path)
        if args.write:
            cfg = _ob.load_config()
            ok, reason = _write_allowed(cfg, result.get("doc_type"))
            if not ok:
                result["_gate"] = reason
            elif not args.out or ".local." not in Path(args.out).name:
                result["_gate"] = ("refused: --out must be a gitignored .local. path "
                                   "(e.g. assembled-agreement.local.md)")
            elif result["selection_errors"] or result["document_text"] is None:
                result["_gate"] = "refused: selection errors; nothing written"
            else:
                Path(args.out).parent.mkdir(parents=True, exist_ok=True)
                Path(args.out).write_text(result["document_text"], encoding="utf-8")
                result["written_to"] = args.out
        print(json.dumps(result, indent=2))
        return 0
    if args.cmd == "diff":
        print(json.dumps(diff_templates(_read_json(args.proposed), _read_json(args.saved)),
                         indent=2))
        return 0
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
