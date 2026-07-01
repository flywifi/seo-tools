#!/usr/bin/env python3
"""Resolve Creator OS connector feature flags into an available-evidence plan (offline).

Reads the connector registry (connectors.json) and an optional per-deployment flag config
(creator-os-config.local.json or feature-flags.*.json) and answers: given what's connected,
which evidence sources are ACTIVE, what is the provider chain (primary + fallbacks) per evidence
type, and where are the GAPS?

Encodes the degradation/convergence + override policy from connectors.md. Stdlib only, no network.

Maps simple creator-os-config.json boolean capability flags into connector states automatically
when no explicit connector-level config is present.

Usage:
  python3 shared/connectors/connectors.py --list
  python3 shared/connectors/connectors.py --flags creator-os-config.local.json --plan
  python3 shared/connectors/connectors.py --flags shared/connectors/feature-flags.example.json --plan
  python3 shared/connectors/connectors.py --plan   # uses creator-os-config.local.json if present
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
REGISTRY = HERE / "connectors.json"

ALWAYS_ON = {"manual_paste", "uploaded_file"}

# Maps creator-os-config.json capability flags -> connector IDs they enable
CAPABILITY_TO_CONNECTOR = {
    "youtube_api": "youtube_data_api",
    "instagram_api": "instagram_graph_api",
    "tiktok_api": "tiktok_api",
    "pinterest_api": "pinterest_api",
    "youtube_publishing": "youtube_publish_api",
    "instagram_publishing": "instagram_publish_api",
    "tiktok_publishing": "tiktok_publish_api",
    "pinterest_publishing": "pinterest_publish_api",
    "keyword_cache": "sqlite_cache",
    "playwright": "playwright_render",
    "mcp_server": "mcp_server",
    "google_workspace": "gmail",
    "microsoft_365": "microsoft_outlook_email",
    "wolfram_alpha": "wolfram_alpha_mcp",
    "e2b_sandbox": "e2b_code_interpreter",
    "duckdb_analytics": "duckdb_analytics_mcp",
    "stats_compass": "stats_compass_mcp",
    "jupyter_notebook": "jupyter_notebook_mcp",
    "r_statistics": "r_statistics_mcp",
    "monte_carlo": "monte_carlo_mcp",
    "scikit_learn": "scikit_learn_mcp",
    "video_editing_enabled": "fcpxml_interchange",
    "resolve_scripting": "resolve_api",
    "compressor_presets": "compressor_cli",
    "commandpost_macros": "commandpost_bridge",
}


def load_registry() -> dict:
    return json.loads(REGISTRY.read_text(encoding="utf-8"))


def load_flags(path: str | None) -> dict:
    if not path:
        local = ROOT / "creator-os-config.local.json"
        if local.exists():
            return json.loads(local.read_text(encoding="utf-8"))
        return {}
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _cap_enabled(val):
    """A capability flag is either a bare bool or a {"enabled": bool, ...} object
    (the shipped creator-os-config.json uses the object form; the wizard-written
    creator-os-config.local.json uses bare bools). Returns True/False/None (None = unset)."""
    if isinstance(val, dict):
        return bool(val["enabled"]) if "enabled" in val else None
    if isinstance(val, bool):
        return val
    return None


def _capability_overrides(flags: dict) -> dict:
    """Translate creator-os-config.json capability flags into connector state overrides.
    Handles both the object form ({"enabled": bool}) and the bare-bool form, so the
    shipped config and the wizard-written local config both resolve correctly."""
    caps = flags.get("capabilities", {})
    overrides = {}
    for cap, connector_id in CAPABILITY_TO_CONNECTOR.items():
        state = _cap_enabled(caps.get(cap))
        if state is True:
            overrides[connector_id] = "available"
        elif state is False:
            overrides[connector_id] = "disabled"
    return overrides


def _flag_state(val):
    """A connector flag is either a bare state string OR {state, restricted_evidence[], reason}.
    The latter keeps the connector active while restricting specific evidence types."""
    if isinstance(val, dict):
        return (val.get("state", "available"),
                list(val.get("restricted_evidence", []) or []),
                val.get("reason", ""))
    return val, [], ""


def resolve(flags: dict, registry: dict | None = None) -> dict:
    """Return effective per-connector state, the active set, the per-evidence provider chain,
    gaps, and any restrictions (an active connector held back from specific evidence types)."""
    reg = registry or load_registry()
    conf = dict(flags.get("connectors", {}) or {})
    blocked = set(flags.get("blocked_sources", []) or [])
    allowed = set(flags.get("allowed_sources", []) or [])

    # Merge capability-flag overrides under connector-level config (connector-level wins)
    cap_overrides = _capability_overrides(flags)
    for cid, state in cap_overrides.items():
        if cid not in conf:
            conf[cid] = state

    states: dict[str, str] = {}
    restricted_by_conn: dict[str, set] = {}
    restrictions: dict[str, dict] = {}

    for c in reg["connectors"]:
        cid, default = c["id"], c["default_flag"]
        st, restricted, reason = _flag_state(conf.get(cid, default))
        if cid in ALWAYS_ON and st != "disabled":
            st = "available"
        if cid in blocked:
            st = "disabled"
        if allowed and cid not in allowed and cid not in ALWAYS_ON:
            st = "disabled"
        states[cid] = st
        if restricted:
            restricted_by_conn[cid] = set(restricted)
            restrictions[cid] = {"evidence": sorted(restricted),
                                  "reason": reason or "deployment policy restricts this evidence"}

    active = [c["id"] for c in reg["connectors"] if states[c["id"]] == "available"]

    provides = {c["id"]: set(c.get("provides", [])) for c in reg["connectors"]}
    authoritative = {c["id"]: set(c.get("authoritative_for", [])) for c in reg["connectors"]}

    chains: dict[str, list] = {}
    gaps: list[str] = []
    restricted_notes: list[dict] = []

    for et in reg.get("evidence_types", []):
        provs = [cid for cid in active
                 if et in provides.get(cid, set())
                 and et not in restricted_by_conn.get(cid, set())]
        # Authoritative providers (e.g., youtube_data_api for channel_stats) go first
        provs.sort(key=lambda cid: (0 if et in authoritative.get(cid, set()) else 1))
        if provs:
            chains[et] = provs
        else:
            gaps.append(et)

    for cid, ets in restricted_by_conn.items():
        if states.get(cid) != "available":
            continue
        for et in sorted(ets):
            if et in provides.get(cid, set()):
                restricted_notes.append({
                    "connector": cid,
                    "evidence": et,
                    "reason": restrictions[cid]["reason"],
                    "failure_class": "PERMISSION",
                    "fell_back_to": chains.get(et, []),
                    "now_gap": et not in chains,
                })

    return {
        "states": states,
        "active": active,
        "evidence_chain": chains,
        "gaps": gaps,
        "restrictions": restrictions,
        "restricted_notes": restricted_notes,
        "blocked": sorted(blocked),
        "allowed": sorted(allowed),
        "deployment": flags.get("deployment", "(default — no flags file)"),
    }


def cmd_list() -> None:
    reg = load_registry()
    print(f"connector registry v{reg['version']} ({len(reg['connectors'])} connectors):")
    for c in reg["connectors"]:
        auth = "  AUTHORITATIVE for " + ", ".join(c["authoritative_for"]) if c.get("authoritative_for") else ""
        print(f"  - {c['id']:22} [{c['default_flag']:16}] provides: {', '.join(c.get('provides', []))}{auth}")
    print("\nstates:", " | ".join(reg["states"]))
    print("\nevidence types:", " | ".join(reg["evidence_types"]))
    print("\ndeployment modes:", " | ".join(reg["deployment_modes"].keys()))


def cmd_plan(flags_path: str | None) -> None:
    flags = load_flags(flags_path)
    r = resolve(flags)
    print(f"deployment: {r['deployment']}")
    print("\neffective connector states:")
    for cid, st in r["states"].items():
        mark = "ACTIVE " if st == "available" else "off    "
        print(f"  {mark} {cid:22} {st}")
    print("\nevidence provider chain (primary -> fallbacks):")
    for et, chain in r["evidence_chain"].items():
        print(f"  {et:20} {' -> '.join(chain)}")
    if r["gaps"]:
        print("\nGAPS (no active provider -- lower confidence or ask creator to paste data):")
        print("  " + ", ".join(r["gaps"]))
    if r.get("restricted_notes"):
        print("\nrestricted (active connector, evidence type limited):")
        for n in r["restricted_notes"]:
            dest = (" -> " + ", ".join(n["fell_back_to"])) if n["fell_back_to"] else "  (no other provider -- GAP)"
            print(f"  {n['connector']} x {n['evidence']}: {n['reason']}{dest}")
    if r["blocked"]:
        print("\nblocked_sources:", ", ".join(r["blocked"]))


def main(argv) -> int:
    ap = argparse.ArgumentParser(
        description="Resolve connector feature flags into an evidence plan (offline)."
    )
    ap.add_argument("--list", action="store_true", help="list the connector registry + default flags")
    ap.add_argument("--flags", metavar="CONFIG", help="path to a per-deployment feature-flags or creator-os-config JSON")
    ap.add_argument("--plan", action="store_true", help="show the active connectors + evidence provider chains")
    ap.add_argument("--json", action="store_true", help="output --plan result as JSON instead of human text")
    a = ap.parse_args(argv)
    if a.plan or a.flags:
        if a.json:
            flags = load_flags(a.flags)
            print(json.dumps(resolve(flags), indent=2))
        else:
            cmd_plan(a.flags)
    else:
        cmd_list()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
