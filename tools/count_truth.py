#!/usr/bin/env python3
"""count_truth.py -- compute the canonical Creator OS counts from the tree (P49 WS2).

The single source of truth for "how many spokes / atoms / skills / invariants / scenarios / engines /
protocols / agent roles does Creator OS have right now". Drift invariant 48 uses it to fail the build
when a live doc states a stale number.

  python3 tools/count_truth.py            # print the counts as JSON
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _enforced_invariants(root=ROOT) -> int:
    """Count of invariant numbers the drift guard enforces, using the same rule its own catalog
    check applies: labeled in a check_* docstring AND registered in main(). Retired/merged numbers
    are reserved for contiguity but are not enforced, so they are not counted."""
    import ast
    try:
        src = (root / "tools" / "sync_check.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
    except (OSError, SyntaxError):
        return 0
    label_re = re.compile(r"^Invariants?\s+(\d+(?:\s*(?:,|and)\s*\d+)*)")
    labels_by_func, main_node = {}, None
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        if node.name == "main":
            main_node = node
        if node.name.startswith("check_"):
            m = label_re.match((ast.get_docstring(node) or "").strip())
            labels_by_func[node.name] = [int(n) for n in re.findall(r"\d+", m.group(1))] if m else []
    if main_node is None:
        return 0
    registered = {n.func.id for n in ast.walk(main_node)
                  if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                  and n.func.id.startswith("check_")}
    return len({n for fn in registered for n in labels_by_func.get(fn, [])})


def counts(root=ROOT):
    skills = root / "skills"
    top = [d for d in skills.iterdir() if d.is_dir()] if skills.exists() else []
    spokes = [d.name for d in top if d.name not in ("creator-core", "quality-review", "atoms")]
    atoms = [d for d in (skills / "atoms").iterdir() if d.is_dir()] if (skills / "atoms").exists() else []
    all_skills = list(skills.rglob("SKILL.md"))
    protocols = list((root / "protocols").glob("*.md"))
    engines = list((root / "shared").glob("*-engine.md"))
    roles = list((root / ".claude" / "agents").glob("*.md"))
    # invariants: how many the drift guard actually ENFORCES. Derived exactly the way the guard's
    # own catalog check (invariant 36) derives it -- a number is enforced when a check_* function
    # both CARRIES the label and is REGISTERED in main(). Counting the highest label instead
    # inflated every doc claim by the retired numbers in MERGED_INVARIANTS (P73 D1-1: reported 58,
    # enforced 57, so a doc correctly stating 57 would have FAILED invariant 48).
    invariants = _enforced_invariants(root)
    try:
        scen = json.loads((root / "skills" / "creator-core" / "evals" / "scenarios.json")
                          .read_text(encoding="utf-8")).get("scenarios", [])
    except (OSError, ValueError):
        scen = []
    # MCP tool definitions the server exposes, counted the same way tools/mcp_server.py counts them
    # for its own selftest. Docs quote this number in smoke-test instructions, so it needs a source
    # of truth; without one it drifts silently the way the macOS file count did.
    try:
        mcp_src = (root / "tools" / "mcp_server.py").read_text(encoding="utf-8")
        mcp_tools = len(re.findall(r"(?m)^@mcp\.tool\(\)\s*$", mcp_src))
    except OSError:
        mcp_tools = 0
    # macOS surface files recorded in the P69/P70 completeness manifest (drift invariant 58). Kept
    # here so the number is always derivable from the tree instead of being restated in prose, which
    # is how the earlier 71-vs-72 drift happened.
    try:
        mac = json.loads((root / "canonical-sources" / "mac-surface-manifest.json")
                         .read_text(encoding="utf-8"))
        mac_recorded = len(mac.get("files", {}))
        mac_excluded = len(mac.get("excluded", {}))
    except (OSError, ValueError):
        mac_recorded = mac_excluded = 0
    return {"spokes": len(spokes), "atoms": len(atoms), "skills": len(all_skills),
            "protocols": len(protocols), "engines": len(engines), "agent_roles": len(roles),
            "invariants": invariants, "scenarios": len(scen),
            "mac_surface_files": mac_recorded, "mac_surface_excluded": mac_excluded,
            "mcp_tools": mcp_tools}


def main(argv):
    print(json.dumps(counts(), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
