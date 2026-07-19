#!/usr/bin/env python3
"""Offline fabrication detection for Creator OS agent output.

Validates agent output JSON against structural rules that detect
common fabrication patterns: unsourced numbers, unregistered sources,
confidence-tier misalignment, fabricated URLs, and missing minority
reports. Adapted from educator-tools validate_outputs.py.

Pure stdlib Python. No network calls.

Usage:
  python3 tools/validate_agent_output.py --input result.json --schema seo-research
  python3 tools/validate_agent_output.py --input result.json  (auto-detect schema)
  python3 tools/validate_agent_output.py --help
"""
import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent

SCHEMA_NAMES = {"seo-research", "competitor-analysis", "content-draft", "deal-review"}

NUMBER_RE = re.compile(
    r"\b(?:"
    r"\d{1,3}(?:,\d{3})+(?:\.\d+)?"  # comma-separated thousands
    r"|\d+\.\d+%"                      # percentages with decimal
    r"|\d+%"                            # whole percentages
    r"|\$\d[\d,]*(?:\.\d{2})?"         # dollar amounts
    r"|\d{4,}"                          # 4+ digit bare numbers (view counts, subscriber counts)
    r")\b"
)

LABELS_THAT_EXCUSE = {"[unverified]", "[estimated]", "[guidance-only]", "[computed via"}


def load_source_registry():
    path = ROOT / "canonical-sources" / "source-registry.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    registry = {}
    for src in data.get("sources", []):
        registry[src["id"]] = src
        if src.get("url"):
            registry[src["url"]] = src
    return registry


def load_authority_allowlist():
    path = ROOT / "canonical-sources" / "traversal-config.json"
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    return data.get("authority_domain_allowlist", [])


def check_source_citations(output, registry):
    """Cross-ref each citation's in_source_registry claim against the actual registry."""
    failures = []
    citations = output.get("source_citations", [])
    if not citations:
        return failures
    for i, cite in enumerate(citations):
        src_ref = cite.get("source_id_or_url", "")
        claims_in_registry = cite.get("in_source_registry")
        if claims_in_registry is True and src_ref not in registry:
            failures.append({
                "rule": "source_citation_registry_mismatch",
                "detail": f"Citation {i} claims in_source_registry=true for '{src_ref}' but it is not in source-registry.json",
                "severity": "high"
            })
        if claims_in_registry is False and src_ref in registry:
            failures.append({
                "rule": "source_citation_registry_mismatch",
                "detail": f"Citation {i} claims in_source_registry=false for '{src_ref}' but it IS in source-registry.json",
                "severity": "medium"
            })
    return failures


def check_confidence_tier_match(output):
    """Validate confidence level against source tier counts."""
    failures = []
    evidence = output.get("confidence_evidence")
    if not evidence:
        return failures
    overall = evidence.get("overall", "").lower()
    breakdown = evidence.get("source_tier_breakdown", {})
    t1 = breakdown.get("t1_count", 0)
    t2 = breakdown.get("t2_count", 0)
    t3 = breakdown.get("t3_count", 0)
    if overall == "high" and t1 < 1:
        failures.append({
            "rule": "confidence_tier_mismatch",
            "detail": f"Confidence is 'high' but t1_count={t1} (requires at least 1 T1 source)",
            "severity": "high"
        })
    if overall == "medium" and t2 < 1 and t3 < 2:
        failures.append({
            "rule": "confidence_tier_mismatch",
            "detail": f"Confidence is 'medium' but t2_count={t2}, t3_count={t3} (requires t2 >= 1 or t3 >= 2)",
            "severity": "medium"
        })
    if overall == "high" and t1 + t2 == 0 and t3 > 0:
        failures.append({
            "rule": "confidence_tier_mismatch",
            "detail": "Confidence is 'high' but only T3 sources cited",
            "severity": "high"
        })
    return failures


def _walk_string_values(obj, path=""):
    """Yield (path, string_value) for every string in a nested structure."""
    if isinstance(obj, str):
        yield path, obj
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield from _walk_string_values(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _walk_string_values(v, f"{path}[{i}]")


def check_unsourced_numbers(output):
    """Flag specific numbers (view counts, dollar amounts, percentages) without matching citations."""
    failures = []
    citations = output.get("source_citations", [])
    cited_claims = {c.get("claim_supported", "") for c in citations}

    skip_keys = {"source_tier_breakdown", "t1_count", "t2_count", "t3_count",
                 "verified_claims", "flagged_claims_count", "confidence_evidence"}

    for path, value in _walk_string_values(output):
        parts = path.split(".")
        if any(k in skip_keys for k in parts):
            continue
        if any(label in value for label in LABELS_THAT_EXCUSE):
            continue
        matches = NUMBER_RE.findall(value)
        for num in matches:
            claim_covered = any(num in claim for claim in cited_claims)
            if not claim_covered:
                failures.append({
                    "rule": "unsourced_number",
                    "detail": f"Number '{num}' at {path} has no matching source_citation",
                    "severity": "medium"
                })
    return failures


def check_fabricated_urls(output, allowlist):
    """Check citation URLs against the authority domain allowlist."""
    failures = []
    citations = output.get("source_citations", [])
    if not citations or not allowlist:
        return failures
    for i, cite in enumerate(citations):
        url = cite.get("source_id_or_url", "")
        if not url.startswith("http"):
            continue
        try:
            domain = urlparse(url).netloc.lower()
        except Exception:
            failures.append({
                "rule": "fabricated_url",
                "detail": f"Citation {i} has unparseable URL: '{url}'",
                "severity": "high"
            })
            continue
        is_allowed = any(
            domain == a or domain.endswith("." + a)
            for a in allowlist
        )
        if not is_allowed:
            failures.append({
                "rule": "unknown_domain_url",
                "detail": f"Citation {i} URL domain '{domain}' not in authority allowlist",
                "severity": "low"
            })
    return failures


def check_minority_report_completeness(output):
    """Flag null minority_report when retrieval_gaps exist or confidence is low."""
    failures = []
    mr = output.get("minority_report")
    gaps = output.get("retrieval_gaps", [])
    confidence = output.get("confidence", "")
    evidence = output.get("confidence_evidence", {})
    overall = evidence.get("overall", confidence).lower() if evidence else confidence.lower()

    if mr is None and gaps and len(gaps) > 0:
        failures.append({
            "rule": "minority_report_missing",
            "detail": f"minority_report is null but retrieval_gaps has {len(gaps)} item(s) -- residual_uncertainty should document these",
            "severity": "medium"
        })
    if mr is None and overall == "low":
        failures.append({
            "rule": "minority_report_missing",
            "detail": "minority_report is null but confidence is 'low' -- should document residual uncertainty",
            "severity": "high"
        })
    if isinstance(mr, dict):
        neg = mr.get("negative_findings_checked", [])
        if not neg:
            failures.append({
                "rule": "minority_report_incomplete",
                "detail": "minority_report exists but negative_findings_checked is empty -- should list things explicitly confirmed absent",
                "severity": "low"
            })
    return failures


def detect_schema(output):
    """Auto-detect which schema an output belongs to based on key fields."""
    if "deal_id" in output and "stage_ready" in output:
        return "deal-review"
    if "competitor" in output and "content_pillars" in output:
        return "competitor-analysis"
    if "content_type" in output and ("hook_variants" in output or "script_sections" in output):
        return "content-draft"
    if "keywords" in output:
        return "seo-research"
    return None


def validate(output, schema_name=None):
    registry = load_source_registry()
    allowlist = load_authority_allowlist()

    all_failures = []
    all_failures.extend(check_source_citations(output, registry))
    all_failures.extend(check_confidence_tier_match(output))
    all_failures.extend(check_unsourced_numbers(output))
    all_failures.extend(check_fabricated_urls(output, allowlist))
    all_failures.extend(check_minority_report_completeness(output))

    high_count = sum(1 for f in all_failures if f["severity"] == "high")

    return {
        "schema": schema_name or detect_schema(output) or "unknown",
        "status": "fail" if all_failures else "pass",
        "rule_failures": all_failures,
        "failure_count": len(all_failures),
        "high_severity_count": high_count,
        "human_review_required": high_count > 0
    }


def _main():
    parser = argparse.ArgumentParser(
        description="Validate Creator OS agent output against fabrication detection rules."
    )
    parser.add_argument(
        "--input", required=True,
        help="Path to agent output JSON file"
    )
    parser.add_argument(
        "--schema", choices=sorted(SCHEMA_NAMES),
        help="Schema name (auto-detected if omitted)"
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(json.dumps({"error": f"File not found: {args.input}"}))
        return 1

    try:
        output = json.loads(input_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(json.dumps({"error": f"Invalid JSON: {exc}"}))
        return 1

    result = validate(output, args.schema)
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "pass" else 1


def main():
    """Thin CLI boundary (P66): an unhandled filesystem error from a user-supplied path (for
    example a >255-byte component raising ENAMETOOLONG, which Path.exists() does not suppress)
    becomes the clean {"error","next_step"} envelope instead of a raw traceback."""
    try:
        return _main()
    except OSError as exc:
        print(json.dumps({"error": str(exc),
                          "next_step": "pass a readable file path (this one could not be opened)"}))
        return 1

if __name__ == "__main__":
    sys.exit(main())
