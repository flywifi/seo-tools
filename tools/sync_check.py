#!/usr/bin/env python3
"""Creator OS drift guard.

Asserts repository invariants rather than diffing text. Exit 0 = clean, 1 = drift.
Pure stdlib (yaml import is optional — graceful fallback if absent).
Run from anywhere: `python3 tools/sync_check.py`.

Invariants enforced:
  1.  Canonical engines + protocols (tools/sync_manifest.json) all exist.
  2.  Every SKILL.md has valid frontmatter with a hyphen-case `name` and a `description`.
  3.  Every skill directory with a SKILL.md also carries a MAINTAINER_README.md.
  4.  Formatting rule (protocols/formatting-metadata.md): no em dashes in user-facing output,
      no en dashes (ranges written with "to"), no forbidden tokens in committed .md content.
  5.  Referential integrity: every backticked repo path in SKILL.md and MAINTAINER_README.md
      that starts with a known root and ends in .md/.json/.py/.js exists on disk.
  6.  Hub integrity: every spoke directory is listed in the hub's downstream spokes, and the
      hub carries the routing object schema.
  7.  Workflow atom resolution: every atom named in a workflow.json is an installed atom.
  8.  YAML frontmatter strict validation: every SKILL.md frontmatter parses with yaml.safe_load.
  9.  Atom eval coverage: every atom directory has evals/evals.json with at least 3 test cases.
  10. Workflow phase consistency: meta.phases titles match phase() calls in .claude/workflows/*.js.
  11. (Merged into 5) MAINTAINER_README.md path references resolve; .claude added to known roots.
  12. Atom composition: every atom is composed by a spoke workflow or marked standalone: true.
  13. Routing table completeness: all request_classification values appear in the routing table.
  14. Agent contract blocks: every .claude/agents/*.md has Operating rules, Forbidden tools,
      Allowed tools, and Output format sections; Forbidden tools lists Write, Edit, NotebookEdit.
  15. Schema verification fields: every shared/schemas/*.json (except envelope and decision schemas)
      has minority_report, confidence_evidence, source_citations in its properties.
  16. Workflow verification step: every .claude/workflows/*.js contains an adversarial verification
      marker (VERIFICATION_SCHEMA, adversarial-verify, cross-verify, verify-research,
      verify-seasonal, independent-review).
  17. READ-ONLY mandate: every .claude/agents/*.md contains the verbatim marker
      "You are a READ-ONLY research agent. You MUST NOT:"
  18. Connector capability mapping: every connector in connectors.json that declares a
      requires_capability has that capability mapped in connectors.py
      CAPABILITY_TO_CONNECTOR (no silently-inert capability flags).
  19. Local-context privacy: no personal *.local.* file (the creator's real context: contract
      records, obligation register, playbook, channel/voice profile, credentials, config
      overrides) is tracked by git. Personal data stays on the local machine; only null
      templates are committed. Runs `git ls-files` read-only. Fails closed in CI when git is
      unavailable; warns and skips locally.
  20. Pipeline tracked-file allowlist: every git-tracked file under pipeline/ is on the explicit
      PIPELINE_TRACKED_ALLOWLIST (blank templates and schemas only), and no financial-export or
      secret file type (.csv/.xlsx/.xls/.ofx/.qfx/.pem/.key/.env*) is tracked anywhere in the
      repo. Catches force-adds and gitignore rule gaps. Fails closed in CI.
  21. Content secret scan: tools/secret_scan.py --tracked finds no API keys, private keys,
      credential values, session links, or non-allowlisted email addresses in tracked file
      content (the filename invariants 19 and 20 are blind to content).
  22. Frontmatter load refs: every repo-relative path named in a SKILL.md frontmatter list
      (load:, engines_required:, protocols:) exists on disk. Closes the un-backticked-ref
      hole that invariant 5's backtick-only scan cannot see.
  23. Dependency registry: every pip package in a requirements-*.txt and every MCP-server-backed
      connector in connectors.json has a matching software-dependency / mcp-server entry in
      source-registry.json, so no dependency ships untracked by the currency system.
  24. Task-tracker integrity (P35): tasks store schema/flags stay coherent.
  25. Currency-map integrity (P36): the data-currency map parses and its sources resolve.
  26. Knowledge-only-surface freshness projection (P36): the packaged freshness bundle stays
      consistent with the registry digest.
  27. Jurisdictional-overlay bucket integrity (P37, optional): overlay buckets are well-formed.
  28. Cross-modality declarations (P38/P39): surface class/carries declarations parse.
  29. Implementation schemas (P38): every packaged schema under implementation/ parses.
  30. Construction dictionary integrity (P34): diagram-index licenses/ids, source_ids, code_ref
      edition/section/url, and diagram_ref resolution.
  31. Doc-template starters (P42): committed doc-template starters are pure shape, never content.
  32. Cross-modality transition matrix (P43): matrix, its doc mirror, and the wizard surface agree.
  33. Migration manifest (P44): every pipeline data template's current schema_version has a
      matching CHANGELOG.migrations.json entry.
  34. Video-library starter (P45): committed video-library starters are pure null shape.
  35. Importer robustness (P46): the content-import pagination/zip/create_time/truncation guards
      stay in place (no silent regression).
  36. Invariant-catalog integrity (P47, keystone): every main()-registered check is labeled, labels
      are unique and contiguous (except the merged set), and this header documents them all.
  37. Legal-source category correctness (P47): every source cited by legal-requirement-check carries
      category 'legal-authority'.
  38. Marketplace/plugin version equality (P47): marketplace.json metadata.version and every
      plugins[].version equal versions.json.ecosystem.
  39. versions.json tree coverage (P47, advisory): tracked skills/engines/protocols resolve on disk,
      and flat shared/ engines are either version-tracked or on _tracked_subset_allowlist.
  40. Registry used_by path resolution (P47, advisory): path-like used_by tokens resolve under the
      repo root or canonical-sources/.
  41. Capability->connector target existence (P47, advisory): every CAPABILITY_TO_CONNECTOR target is
      a connector defined in connectors.json.
  42. Registry writer-count integrity (P47, advisory): exactly the five sanctioned tools reference the
      registry writer.
  43. Moving-date calendar (P47, advisory): any moving-dates.json date whose effective/phase_2 has
      passed while verified_after < effective is surfaced.
  44. degraded_behavior/capability parity (P47, advisory): every '<name>_disabled' key maps to a real
      capability (or a documented shared key).
  45. content-vs-digest silent staleness (P47, advisory, loud): registry sources re-verified after the
      freshness baseline as_of are surfaced (the digest excludes content).
  46. URL provenance (P49 WS3): every http(s) literal in tools/**/*.py resolves to a source-registry
      host, the operational-url-allowlist sidecar, or an excluded-by-rule placeholder/schema host.
  47. Knowledge-pack projection staleness (P49 WS7, advisory): when a shared engine/protocol a knowledge
      file projects changes sha since the projection manifest was reconciled, the file is surfaced.
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

ROOT = Path(__file__).resolve().parent.parent
PROBLEMS = []

# Invariant 11 was merged into invariant 5 (see the module docstring): its backticked-path check
# was folded into check_references, so no check_* function carries the label "Invariant 11". Any
# OTHER gap in the 1..N invariant sequence is drift, and Invariant 36 (catalog integrity) fails on
# it. When an invariant is genuinely retired, add its number here with a one-line reason.
MERGED_INVARIANTS = {11}


def problem(msg):
    PROBLEMS.append(msg)


# Advisory notes are non-blocking: they print but never change the exit code (unlike problem()).
# Used by the P47 diagnose-only invariants (coverage, used_by paths, capability->connector, writer
# count) that surface likely-but-not-certain drift without failing the build.
ADVISORIES = []


def advisory(msg):
    ADVISORIES.append(msg)


def load_manifest():
    path = ROOT / "tools" / "sync_manifest.json"
    if not path.exists():
        problem("missing tools/sync_manifest.json")
        return {"engines": [], "protocols": []}
    return json.loads(path.read_text(encoding="utf-8"))


def check_canonical(manifest):
    """Invariant 1: every canonical engine and protocol named in tools/sync_manifest.json exists."""
    for rel in manifest.get("engines", []) + manifest.get("protocols", []):
        if not (ROOT / rel).exists():
            problem(f"canonical file missing: {rel}")


FM_RE = re.compile(r"^---\n(.*?)\n---\n", re.S)
NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def parse_frontmatter(text):
    m = FM_RE.match(text)
    if not m:
        return None
    fm = {}
    for line in m.group(1).splitlines():
        if line and not line.startswith((" ", "-", "\t")) and ":" in line:
            key, _, value = line.partition(":")
            fm[key.strip()] = value.strip()
    return fm


def iter_skill_mds():
    skills = ROOT / "skills"
    if skills.exists():
        yield from sorted(skills.rglob("SKILL.md"))


def check_skills():
    """Invariants 2 and 3."""
    for skill_md in iter_skill_mds():
        rel = skill_md.relative_to(ROOT)
        text = skill_md.read_text(encoding="utf-8")
        fm = parse_frontmatter(text)
        if fm is None:
            problem(f"{rel}: missing YAML frontmatter")
            continue
        name = fm.get("name")
        if not name:
            problem(f"{rel}: frontmatter missing 'name'")
        elif not NAME_RE.match(name):
            problem(f"{rel}: name '{name}' is not hyphen-case")
        elif len(name) > 64:
            problem(f"{rel}: name longer than 64 chars")
        if not fm.get("description"):
            problem(f"{rel}: frontmatter missing 'description'")
        if not (skill_md.parent / "MAINTAINER_README.md").exists():
            problem(f"{rel.parent}: missing MAINTAINER_README.md")


EM_DASH = "—"
EN_DASH = "–"
FORBIDDEN_TOKENS = ["TODO", "FIXME", "PLACEHOLDER", "<<<<<<<", "=======", ">>>>>>>"]
CONTENT_DIRS = ["shared", "protocols", "skills", "docs", "examples", "canonical-sources"]
EM_DASH_DIRS = ["examples"]


def check_formatting():
    """Invariant 4."""
    for name in CONTENT_DIRS:
        base = ROOT / name
        if not base.exists():
            continue
        for md in sorted(base.rglob("*.md")):
            rel = md.relative_to(ROOT)
            text = md.read_text(encoding="utf-8")
            if name in EM_DASH_DIRS and EM_DASH in text:
                problem(f"{rel}: contains an em dash (forbidden in user-facing output by formatting-metadata.md)")
            if EN_DASH in text:
                problem(f"{rel}: contains an en dash (write ranges with 'to')")
            for tok in FORBIDDEN_TOKENS:
                if tok in text:
                    problem(f"{rel}: contains forbidden token {tok!r}")


PATH_RE = re.compile(r"`([A-Za-z0-9_.][A-Za-z0-9_./-]*\.(?:md|json|py|js))`")
KNOWN_ROOTS = ("shared", "protocols", "skills", "pipeline", "tools", "docs", ".claude",
               "canonical-sources")


def check_references():
    """Invariant 5 (expanded): scans SKILL.md and MAINTAINER_README.md; includes .claude root."""
    skills = ROOT / "skills"
    if not skills.exists():
        return
    for skill_dir in sorted(skills.rglob("*")):
        if not skill_dir.is_dir():
            continue
        for filename in ("SKILL.md", "MAINTAINER_README.md"):
            target = skill_dir / filename
            if not target.exists():
                continue
            rel = target.relative_to(ROOT)
            text = target.read_text(encoding="utf-8")
            for match in PATH_RE.finditer(text):
                ref = match.group(1)
                if ref.split("/")[0] in KNOWN_ROOTS and not (ROOT / ref).exists():
                    problem(f"{rel}: references missing path `{ref}`")


def check_frontmatter_loads():
    """Invariant 22: every repo-relative path in a SKILL.md frontmatter load:/engines_required:/
    protocols: list exists on disk. These YAML entries are usually not backticked, so the
    invariant-5 scan never sees them; a dangling load ref means an atom silently loads nothing."""
    skills = ROOT / "skills"
    if not skills.exists():
        return
    list_item = re.compile(r"^\s*-\s*[\"']?([A-Za-z0-9_.][A-Za-z0-9_./-]*\.(?:md|json|py|js))[\"']?\s*$")
    for skill_md in sorted(skills.rglob("SKILL.md")):
        rel = skill_md.relative_to(ROOT)
        text = skill_md.read_text(encoding="utf-8")
        m = FM_RE.match(text)
        if not m:
            continue
        for line in m.group(1).splitlines():
            item = list_item.match(line)
            if not item:
                continue
            ref = item.group(1)
            if ref.split("/")[0] in KNOWN_ROOTS and not (ROOT / ref).exists():
                problem(f"{rel}: frontmatter references missing path {ref}")


def check_hub():
    """Invariant 6."""
    hub = ROOT / "skills" / "creator-core" / "SKILL.md"
    if not hub.exists():
        problem("missing hub skills/creator-core/SKILL.md")
        return
    text = hub.read_text(encoding="utf-8")
    listed = set()
    if "## Downstream spokes" in text:
        listed = set(re.findall(r"[a-z][a-z-]+", text.split("## Downstream spokes")[-1]))
    actual = {
        p.name
        for p in (ROOT / "skills").iterdir()
        if p.is_dir() and p.name not in ("creator-core", "atoms")
    }
    for spoke in sorted(actual):
        if spoke not in listed:
            problem(f"orphan spoke skills/{spoke} not listed in hub downstream spokes")
    if '"request_classification"' not in text:
        problem("hub SKILL.md missing the routing object schema")


def check_workflows():
    """Invariant 7."""
    atoms_dir = ROOT / "skills" / "atoms"
    available = (
        {p.name for p in atoms_dir.iterdir() if p.is_dir()} if atoms_dir.exists() else set()
    )
    for wf in sorted((ROOT / "skills").rglob("workflow.json")):
        rel = wf.relative_to(ROOT)
        try:
            data = json.loads(wf.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            problem(f"{rel}: invalid JSON ({exc})")
            continue
        named = [s.get("atom") for s in data.get("steps", []) if s.get("atom")]
        named += list(data.get("shortcut_atoms", []))
        for atom in named:
            if atom not in available:
                problem(f"{rel}: references unknown atom '{atom}'")


def check_yaml_strict():
    """Invariant 8: YAML frontmatter must parse with yaml.safe_load."""
    if not HAS_YAML:
        return
    for skill_md in iter_skill_mds():
        rel = skill_md.relative_to(ROOT)
        text = skill_md.read_text(encoding="utf-8")
        m = FM_RE.match(text)
        if not m:
            continue
        try:
            yaml.safe_load(m.group(1))
        except yaml.YAMLError as exc:
            first_line = str(exc).split("\n")[0]
            problem(f"{rel}: YAML frontmatter invalid for strict parser: {first_line}")


def check_atom_evals():
    """Invariant 9: every atom has evals/evals.json with at least 3 test cases."""
    atoms_dir = ROOT / "skills" / "atoms"
    if not atoms_dir.exists():
        return
    for atom_dir in sorted(atoms_dir.iterdir()):
        if not atom_dir.is_dir():
            continue
        evals_file = atom_dir / "evals" / "evals.json"
        if not evals_file.exists():
            problem(f"skills/atoms/{atom_dir.name}: missing evals/evals.json")
            continue
        try:
            data = json.loads(evals_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            problem(f"skills/atoms/{atom_dir.name}: evals/evals.json is not valid JSON")
            continue
        cases = data if isinstance(data, list) else data.get("cases", data.get("tests", []))
        if len(cases) < 3:
            problem(f"skills/atoms/{atom_dir.name}: evals/evals.json has {len(cases)} case(s) (minimum 3)")


def check_workflow_phases():
    """Invariant 10: meta.phases titles must match phase() calls in workflow scripts."""
    wf_dir = ROOT / ".claude" / "workflows"
    if not wf_dir.exists():
        return
    for js in sorted(wf_dir.glob("*.js")):
        rel = js.relative_to(ROOT)
        text = js.read_text(encoding="utf-8")
        if "phases:" not in text:
            continue
        phases_block = text.split("phases:")[1].split("]")[0]
        meta_titles = set(re.findall(r"title:\s*['\"]([^'\"]+)['\"]", phases_block))
        call_titles = set(re.findall(r"phase\(['\"]([^'\"]+)['\"]\)", text))
        for title in sorted(meta_titles - call_titles):
            problem(f"{rel}: meta.phases declares '{title}' but no phase('{title}') call found")
        for title in sorted(call_titles - meta_titles):
            problem(f"{rel}: phase('{title}') called but not declared in meta.phases")


def check_atom_composition():
    """Invariant 12: every atom is composed by a spoke or marked standalone: true."""
    atoms_dir = ROOT / "skills" / "atoms"
    if not atoms_dir.exists():
        return
    composed = set()
    for wf in sorted((ROOT / "skills").rglob("workflow.json")):
        if "atoms" in str(wf.relative_to(ROOT)):
            continue
        try:
            data = json.loads(wf.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        for s in data.get("steps", []):
            if s.get("atom"):
                composed.add(s["atom"])
        for a in data.get("shortcut_atoms", []):
            composed.add(a)
    for atom_dir in sorted(atoms_dir.iterdir()):
        if not atom_dir.is_dir():
            continue
        name = atom_dir.name
        if name in composed:
            continue
        skill_md = atom_dir / "SKILL.md"
        if skill_md.exists():
            fm = parse_frontmatter(skill_md.read_text(encoding="utf-8"))
            if fm and fm.get("standalone") == "true":
                continue
        problem(f"skills/atoms/{name}: not composed by any spoke and not marked standalone: true")


def check_routing_table():
    """Invariant 13: all request_classification values appear in the routing table."""
    hub = ROOT / "skills" / "creator-core" / "SKILL.md"
    if not hub.exists():
        return
    text = hub.read_text(encoding="utf-8")
    enum_match = re.search(
        r"## Request classification.*?\n(`[^`]+`(?:\s+`[^`]+`)*)", text
    )
    if not enum_match:
        return
    values = set(re.findall(r"`([^`]+)`", enum_match.group(1)))
    table_match = re.search(
        r"### Classification routing table\n\n\|.*\n\|.*\n((?:\|.*\n)*)", text
    )
    if not table_match:
        problem("hub SKILL.md: classification routing table not found")
        return
    routed = set()
    for row in table_match.group(1).strip().split("\n"):
        cells = [c.strip() for c in row.split("|")]
        if len(cells) >= 3:
            val = cells[1].strip().strip("`")
            if val:
                routed.add(val)
    for val in sorted(values - routed):
        problem(f"hub SKILL.md: request_classification '{val}' not mapped in routing table")


def check_agent_contracts():
    """Invariant 14: agent definitions have required contract sections."""
    agents_dir = ROOT / ".claude" / "agents"
    if not agents_dir.exists():
        return
    required_sections = [
        "## Operating rules",
        "## Forbidden tools (machine-enforced)",
        "## Allowed tools (explicit allowlist)",
        "## Output format",
    ]
    forbidden_tools_must_list = ["Write", "Edit", "NotebookEdit"]
    for md in sorted(agents_dir.glob("*.md")):
        rel = md.relative_to(ROOT)
        text = md.read_text(encoding="utf-8")
        for section in required_sections:
            if section not in text:
                problem(f"{rel}: missing required section '{section}'")
        if "## Forbidden tools (machine-enforced)" in text:
            forbidden_block = text.split("## Forbidden tools (machine-enforced)")[1]
            next_section = forbidden_block.find("\n## ")
            if next_section > 0:
                forbidden_block = forbidden_block[:next_section]
            for tool_name in forbidden_tools_must_list:
                if tool_name not in forbidden_block:
                    problem(f"{rel}: Forbidden tools section missing '{tool_name}'")


def check_schema_verification_fields():
    """Invariant 15: agent output schemas have verification envelope fields."""
    schemas_dir = ROOT / "shared" / "schemas"
    if not schemas_dir.exists():
        return
    skip = {"verification-envelope.json", "verification-decision.json"}
    required_props = ["minority_report", "confidence_evidence", "source_citations"]
    for schema_file in sorted(schemas_dir.glob("*.json")):
        if schema_file.name in skip:
            continue
        rel = schema_file.relative_to(ROOT)
        try:
            data = json.loads(schema_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            problem(f"{rel}: invalid JSON")
            continue
        props = data.get("properties", {})
        for field in required_props:
            if field not in props:
                problem(f"{rel}: missing verification field '{field}' in properties")


def check_workflow_verification():
    """Invariant 16: every workflow has an adversarial verification step."""
    wf_dir = ROOT / ".claude" / "workflows"
    if not wf_dir.exists():
        return
    markers = [
        "VERIFICATION_SCHEMA",
        "adversarial-verify",
        "cross-verify",
        "verify-research",
        "verify-seasonal",
        "independent-review",
    ]
    for js in sorted(wf_dir.glob("*.js")):
        rel = js.relative_to(ROOT)
        text = js.read_text(encoding="utf-8")
        if not any(m in text for m in markers):
            problem(f"{rel}: no adversarial verification marker found")


def check_readonly_mandate():
    """Invariant 17: every agent definition has the READ-ONLY mandate."""
    agents_dir = ROOT / ".claude" / "agents"
    if not agents_dir.exists():
        return
    mandate = "You are a READ-ONLY research agent. You MUST NOT:"
    for md in sorted(agents_dir.glob("*.md")):
        rel = md.relative_to(ROOT)
        text = md.read_text(encoding="utf-8")
        if mandate not in text:
            problem(f"{rel}: missing READ-ONLY mandate marker")


def check_connector_capability_mapping():
    """Invariant 18: every connector that declares a requires_capability has that
    capability mapped in connectors.py CAPABILITY_TO_CONNECTOR, so enabling the flag
    actually activates the connector in the resolver (no silently-inert flags)."""
    reg_path = ROOT / "shared" / "connectors" / "connectors.json"
    py_path = ROOT / "shared" / "connectors" / "connectors.py"
    if not reg_path.exists() or not py_path.exists():
        return
    try:
        reg = json.loads(reg_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        problem("shared/connectors/connectors.json: invalid JSON")
        return
    text = py_path.read_text(encoding="utf-8")
    block = re.search(r"CAPABILITY_TO_CONNECTOR\s*=\s*\{(.*?)\}", text, re.DOTALL)
    mapped = set(re.findall(r'"([^"]+)"\s*:', block.group(1))) if block else set()
    for c in reg.get("connectors", []):
        cap = c.get("requires_capability")
        if cap and cap not in mapped:
            problem(
                f"shared/connectors/connectors.json: connector '{c.get('id')}' "
                f"requires_capability '{cap}' is not mapped in connectors.py "
                f"CAPABILITY_TO_CONNECTOR"
            )


def check_dependency_registry():
    """Invariant 23: every pip package named in a requirements-*.txt and every MCP-server-backed
    connector in connectors.json must have a matching entry in source-registry.json
    (software-dependency / mcp-server). Mirrors invariant 18's connector-mapping discipline, so a
    new dependency or MCP server cannot ship untracked by the dependency-currency system."""
    reg_path = ROOT / "canonical-sources" / "source-registry.json"
    if not reg_path.exists():
        return
    try:
        reg = json.loads(reg_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        problem("canonical-sources/source-registry.json: invalid JSON")
        return
    sources = reg.get("sources", [])

    def norm(p):
        return p.strip().lower().replace("_", "-")

    covered_packages = {norm(s["package"]) for s in sources
                        if s.get("category") == "software-dependency" and s.get("package")}
    # connector ids named in any dependency/mcp-server entry's used_by
    covered_connectors = set()
    for s in sources:
        if s.get("category") in ("software-dependency", "mcp-server"):
            covered_connectors.update(s.get("used_by", []))

    # 1. requirements-*.txt packages
    for req in sorted(ROOT.glob("requirements-*.txt")):
        for line in req.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("-"):
                continue
            name = re.split(r"[<>=!~;\[ ]", line, 1)[0].strip()
            if name and norm(name) not in covered_packages:
                problem(f"{req.name}: package '{name}' has no software-dependency entry in "
                        f"source-registry.json (invariant 23; add it via dependency-sources-seed.json)")

    # 2. MCP-server-backed connectors
    mcp_caps = {"google_workspace", "microsoft_365", "wolfram_alpha", "e2b_sandbox",
                "stats_compass", "duckdb_analytics", "jupyter_notebook", "r_statistics",
                "monte_carlo", "scikit_learn", "mcp_server"}
    conn_path = ROOT / "shared" / "connectors" / "connectors.json"
    if conn_path.exists():
        try:
            conns = json.loads(conn_path.read_text(encoding="utf-8")).get("connectors", [])
        except json.JSONDecodeError:
            conns = []
        for c in conns:
            cid = c.get("id", "")
            cap = c.get("requires_capability", "")
            is_mcp = cid.endswith("_mcp") or cap in mcp_caps
            if is_mcp and cid not in covered_connectors:
                problem(f"connectors.json: MCP-backed connector '{cid}' is not referenced by any "
                        f"mcp-server/software-dependency entry's used_by in source-registry.json "
                        f"(invariant 23)")


LOCAL_FILE_RE = re.compile(r"\.local(\.|$)")

# Invariant 20: the ONLY files allowed to be git-tracked under pipeline/. Blank shapes only.
# Anything else tracked under pipeline/ is treated as a potential real-data leak and fails the
# guard. Extend this list deliberately, never casually.
PIPELINE_TRACKED_ALLOWLIST = {
    "pipeline/accounts/account-schema.json",
    "pipeline/contracts/contract.template.json",
    "pipeline/deals/deal-schema.json",
    "pipeline/editing/edit-package.template.json",
    "pipeline/editing/render-manifest.template.json",
    "pipeline/finance/cost-actuals.template.json",
    "pipeline/finance/cost-estimate.template.json",
    "pipeline/finance/invoice.template.json",
    "pipeline/finance/rate-card.template.json",
    "pipeline/templates/analytics-overview.template.json",
    "pipeline/templates/contract-base.template.json",
    "pipeline/templates/rate-card-display.template.json",
    "pipeline/templates/terms-conditions.template.json",
    "pipeline/user-context/channel-context.json",
    "pipeline/user-context/content-calendar.json",
    "pipeline/user-context/creator-profile.template.json",
    "pipeline/user-context/deal-playbook.template.json",
    "pipeline/user-context/obligation-register.template.json",
    "pipeline/user-context/task-register.template.json",
    "pipeline/user-context/recurrence-rules.template.json",
    "pipeline/user-context/shipments.template.json",
    "pipeline/user-context/payment-schedule.template.json",
    "pipeline/user-context/setup-context.json",
    "pipeline/user-context/voice-profile.json",
    "pipeline/video-library/video-library.template.json",
    "pipeline/video-library/video-library-schema.json",
}

# Invariant 20 (second half): file types that must never be tracked anywhere in the repo
# (financial exports, spreadsheets, secrets, key material).
FORBIDDEN_TRACKED_SUFFIXES = (".csv", ".xlsx", ".xls", ".ofx", ".qfx", ".pem", ".key")
FORBIDDEN_TRACKED_BASENAMES = re.compile(r"^\.env(\.|$)")


def _git_ls_files():
    """Tracked file list, or None when git is unavailable. Privacy invariants FAIL CLOSED in
    CI when this returns None (a privacy check that silently passes without its enforcement
    mechanism is not a boundary); locally they warn and skip."""
    try:
        out = subprocess.run(
            ["git", "ls-files"], cwd=str(ROOT), capture_output=True, text=True, timeout=30
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    return [line.strip() for line in out.stdout.splitlines() if line.strip()]


def _privacy_git_unavailable(invariant):
    if os.environ.get("CI"):
        problem(f"privacy: git unavailable in CI; invariant {invariant} cannot run (fail closed)")
    else:
        print(f"  [warn] git unavailable; privacy invariant {invariant} skipped (local run)")


def check_local_privacy():
    """Invariant 19: no personal *.local.* file is tracked by git.

    The creator's real context (contract records, obligation register, deal-playbook,
    channel/voice profile, credentials, config overrides) lives in gitignored *.local.* files
    that git pull never touches. This asserts none of them ever entered git, so a stray
    `git add -A` cannot leak or commit personal data. Fails closed in CI when git is
    unavailable; warns and skips locally.
    """
    tracked = _git_ls_files()
    if tracked is None:
        _privacy_git_unavailable(19)
        return
    for path in tracked:
        basename = path.rsplit("/", 1)[-1]
        if LOCAL_FILE_RE.search(basename):
            problem(
                f"privacy: personal local file is tracked by git and must be gitignored: {path}"
            )


def check_pipeline_allowlist():
    """Invariant 20: tracked files under pipeline/ must be on the explicit allowlist, and no
    financial-export or secret file type is tracked anywhere.

    The gitignore's allowlist-invert rules stop accidents; this catches force-adds
    (`git add -f`) and rule gaps. A bank CSV, a hand-dropped invoices.json under
    pipeline/finance/, an .env, or key material tracked anywhere fails the guard. Fails closed
    in CI when git is unavailable.
    """
    tracked = _git_ls_files()
    if tracked is None:
        _privacy_git_unavailable(20)
        return
    for path in tracked:
        if path.startswith("pipeline/") and path not in PIPELINE_TRACKED_ALLOWLIST:
            problem(
                f"privacy: tracked file under pipeline/ is not on the allowlist "
                f"(potential real-data leak): {path}"
            )
        basename = path.rsplit("/", 1)[-1].lower()
        if basename.endswith(FORBIDDEN_TRACKED_SUFFIXES) or FORBIDDEN_TRACKED_BASENAMES.match(basename):
            problem(
                f"privacy: forbidden file type is tracked by git "
                f"(financial export / secret material): {path}"
            )


def check_secret_content():
    """Invariant 21: tools/secret_scan.py --tracked finds no secret content in tracked files.

    Invariants 19 and 20 are filename checks; this one reads content: API keys, private-key
    blocks, non-placeholder credential values, session links, non-allowlisted emails, and
    dollar figures inside committed pipeline/ templates. Fails closed in CI when the scanner
    cannot run."""
    scanner = ROOT / "tools" / "secret_scan.py"
    if not scanner.exists():
        problem("privacy: tools/secret_scan.py is missing (invariant 21 cannot run)")
        return
    try:
        out = subprocess.run([sys.executable, str(scanner), "--tracked"],
                             cwd=str(ROOT), capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.SubprocessError) as exc:
        if os.environ.get("CI"):
            problem(f"privacy: secret scan failed to run in CI (fail closed): {exc}")
        else:
            print(f"  [warn] secret scan could not run; invariant 21 skipped (local): {exc}")
        return
    if out.returncode != 0:
        for line in out.stdout.splitlines():
            if line.strip().startswith("- "):
                problem(f"secret content: {line.strip()[2:]}")
        if not any(line.strip().startswith("- ") for line in out.stdout.splitlines()):
            problem(f"privacy: secret scan exited {out.returncode}: {out.stdout.strip()[-300:]}")


def check_construction():
    """Invariant 30: construction dictionary integrity (P34).

    Every diagram-index entry carries a license and an id. Every construction dictionary record carries
    non-empty source_ids; any record that cites code carries the verify-locally boundary; every code_ref
    names a section, an edition, and a url; and every diagram_ref resolves to a diagram-index id. This
    keeps citations edition-aware, keeps bundled diagrams license-tagged, and keeps the boundary on every
    code-bearing answer. No-op when the construction directory is absent."""
    cdir = ROOT / "canonical-sources" / "construction"
    if not cdir.exists():
        return
    idx_ids = set()
    idxf = cdir / "diagram-index.json"
    if idxf.exists():
        try:
            idx = json.loads(idxf.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            problem(f"construction: diagram-index.json unreadable: {exc}")
            idx = []
        for e in idx if isinstance(idx, list) else []:
            if not e.get("id"):
                problem("construction: a diagram-index entry is missing its id")
            else:
                idx_ids.add(e["id"])
            if not e.get("license"):
                problem(f"construction: diagram '{e.get('id', '<no id>')}' has no license in diagram-index.json")
    for jf in sorted(cdir.glob("*.json")):
        if jf.name == "diagram-index.json":
            continue
        try:
            recs = json.loads(jf.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            problem(f"construction: {jf.name} unreadable: {exc}")
            continue
        if not isinstance(recs, list):
            continue
        for r in recs:
            if not isinstance(r, dict):
                continue
            rid = r.get("id", "<no id>")
            if not r.get("source_ids"):
                problem(f"construction: {jf.name}:{rid} has no source_ids")
            code_refs = r.get("code_refs") or []
            if code_refs and not r.get("boundary"):
                problem(f"construction: {jf.name}:{rid} cites code but carries no boundary")
            for ref in code_refs:
                for k in ("section", "edition", "url"):
                    if not ref.get(k):
                        problem(f"construction: {jf.name}:{rid} code_ref is missing '{k}'")
            for d in r.get("diagram_refs") or []:
                if d not in idx_ids:
                    problem(f"construction: {jf.name}:{rid} diagram_ref '{d}' is not in diagram-index.json")


def check_freshness_bundle():
    """Invariant 26: knowledge-only-surface freshness projection (P36).

    The implementation/** knowledge digests that feed Claude Projects, Custom GPT, and Gemini must
    each carry a visible freshness (as_of) stamp and be recorded in the projection manifest
    (implementation/freshness-bundle.json), and the manifest's canonical_digest must still match the
    current canonical data. This means a published baseline can never silently lag canonical: editing
    the tracked sources without re-running build_freshness_bundle --apply fails the guard. No-op when
    the freshness bundle has not been created yet (the tool/manifest are absent)."""
    tool = ROOT / "tools" / "build_freshness_bundle.py"
    manifest = ROOT / "implementation" / "freshness-bundle.json"
    if not tool.exists() or not manifest.exists():
        return
    import importlib.util
    spec = importlib.util.spec_from_file_location("_bfb", tool)
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
        ok, problems = mod.check(ROOT)
    except Exception as exc:  # noqa: BLE001
        problem(f"freshness-bundle: check failed to run: {exc}")
        return
    for p in problems:
        problem(f"freshness-bundle: {p}")


def check_jurisdiction():
    """Invariant 27: jurisdictional-overlay bucket integrity (P37, optional).

    For the optional canonical-sources/jurisdiction/ bucket (no-op if absent): every record is a
    cache-indexable {id, title, non-empty text}; every record declares an overlay_kind in
    {geometry, attribute, versioned-fact}; every record carries a source (non-empty source_ids OR a
    source_reference) and the advisory boundary marker; and any code_refs carry section+edition+url
    (mirroring the construction contract). This keeps every overlay cited and advisory-flagged so it
    can never present as a legal determination."""
    jdir = ROOT / "canonical-sources" / "jurisdiction"
    if not jdir.exists():
        return
    kinds = {"geometry", "attribute", "versioned-fact"}
    for jf in sorted(jdir.glob("*.json")):
        # *.example.json are schema demos, never loaded for production resolution -> not validated here.
        if jf.name.endswith(".example.json"):
            continue
        try:
            recs = json.loads(jf.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            problem(f"jurisdiction: {jf.name} unreadable: {exc}")
            continue
        if not isinstance(recs, list):
            problem(f"jurisdiction: {jf.name} must be a JSON array of overlay records")
            continue
        for r in recs:
            if not isinstance(r, dict):
                continue
            if "_comment" in r and len(r) == 1:
                continue
            rid = r.get("id", "<no id>")
            if not r.get("id") or not r.get("title") or not (r.get("text") or "").strip():
                problem(f"jurisdiction: {jf.name}:{rid} needs id, title, and non-empty text")
            if r.get("overlay_kind") not in kinds:
                problem(f"jurisdiction: {jf.name}:{rid} overlay_kind must be one of {sorted(kinds)}")
            # A versioned-fact with no applicability predicate applies EVERYWHERE (the SLR/rutherford
            # over-fire class): require an explicit scope so a fact cannot leak outside its jurisdiction.
            if r.get("overlay_kind") == "versioned-fact" and not r.get("applicability"):
                problem(f"jurisdiction: {jf.name}:{rid} versioned-fact must declare an 'applicability' "
                        f"predicate (else it over-fires outside its jurisdiction)")
            if not r.get("source_ids") and not r.get("source_reference"):
                problem(f"jurisdiction: {jf.name}:{rid} has no source_ids or source_reference")
            if not r.get("boundary"):
                problem(f"jurisdiction: {jf.name}:{rid} is missing the advisory boundary marker")
            for ref in r.get("code_refs") or []:
                for k in ("section", "edition", "url"):
                    if not ref.get(k):
                        problem(f"jurisdiction: {jf.name}:{rid} code_ref is missing '{k}'")


def check_cross_modality():
    """Invariant 28: cross-modality declarations (P38/P39).

    Every spoke SKILL.md (skills/*/, excluding atoms) must carry a `## Cross-modality` section with a
    real `Class:` (A/B/C) plus `Runs on:`, `Mechanism:`, and `Fallback:` lines, referencing
    shared/cross-modality-engine.md -- so a stub cannot pass and the wizard can guide per-surface
    setup. Every atom (skills/atoms/*/) must carry a `## Cross-modality` line referencing the engine
    (atoms inherit their calling spoke's class)."""
    engine = ROOT / "shared" / "cross-modality-engine.md"
    if not engine.exists():
        problem("cross-modality: shared/cross-modality-engine.md is missing")
        return
    sk = ROOT / "skills"
    if not sk.exists():
        return
    for d in sorted(sk.iterdir()):
        if not d.is_dir() or d.name == "atoms":
            continue
        f = d / "SKILL.md"
        if not f.exists():
            continue
        txt = f.read_text(encoding="utf-8")
        if "## Cross-modality" not in txt:
            problem(f"cross-modality: skills/{d.name}/SKILL.md is missing a '## Cross-modality' section")
            continue
        if "shared/cross-modality-engine.md" not in txt:
            problem(f"cross-modality: skills/{d.name}/SKILL.md must reference shared/cross-modality-engine.md")
        seg = txt.split("## Cross-modality", 1)[1]
        if not re.search(r"Class:\s*[ABC]\b", seg):
            problem(f"cross-modality: skills/{d.name}/SKILL.md ## Cross-modality needs a 'Class: A|B|C'")
        for field in ("Runs on:", "Mechanism:", "Fallback:"):
            if field not in seg:
                problem(f"cross-modality: skills/{d.name}/SKILL.md ## Cross-modality needs a '{field}' line")
    adir = sk / "atoms"
    if adir.exists():
        for d in sorted(adir.iterdir()):
            if not d.is_dir():
                continue
            f = d / "SKILL.md"
            if not f.exists():
                continue
            txt = f.read_text(encoding="utf-8")
            if "## Cross-modality" not in txt:
                problem(f"cross-modality: skills/atoms/{d.name}/SKILL.md is missing a '## Cross-modality' line")
            elif "shared/cross-modality-engine.md" not in txt:
                problem(f"cross-modality: skills/atoms/{d.name}/SKILL.md must reference shared/cross-modality-engine.md")


def check_implementation_schemas():
    """Invariant 29: every packaged schema under implementation/ parses (P38).

    Every .json / .yaml / .yml under implementation/ must parse cleanly, so a malformed GPT Action
    OpenAPI schema or Gemini function declaration can never ship (caught the P38-6 YAML typo class)."""
    impl = ROOT / "implementation"
    if not impl.exists():
        return
    for f in sorted(impl.rglob("*")):
        if not f.is_file():
            continue
        suf = f.suffix.lower()
        if suf == ".json":
            try:
                json.loads(f.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                problem(f"implementation: {f.relative_to(ROOT)} is invalid JSON: {exc}")
        elif suf in (".yaml", ".yml"):
            try:
                import yaml  # noqa: PLC0415
            except ImportError:
                continue  # pyyaml absent -> advisory skip
            try:
                yaml.safe_load(f.read_text(encoding="utf-8"))
            except Exception as exc:  # noqa: BLE001
                problem(f"implementation: {f.relative_to(ROOT)} is invalid YAML: {exc}")


DOC_TEMPLATE_TYPES = {"contract", "rate_card", "analytics_overview", "terms_conditions"}


def check_video_library_starter():
    """Invariant 34: committed video-library starters are pure null shape, never a real video (P45).

    Every tracked pipeline/video-library/*.template.json must parse and carry only null/empty data
    fields: no real platform_video_id, title, url, stats, retention, revenue, or transcript. The
    creator's own catalog (performance, revenue, transcripts) lives ONLY in the gitignored
    index.local.db and *.local.json; this guarantees none of it ever enters git via a starter.
    Mirrors invariant 31 for the content-import store."""
    vdir = ROOT / "pipeline" / "video-library"
    if not vdir.exists():
        return
    null_scalars = ("video_key", "platform", "platform_video_id", "url", "title", "description",
                    "category", "published_at", "duration_s", "retention", "revenue",
                    "transcript_ref", "transcript_text", "source_mode")
    empty_containers = ("tags", "chapters", "most_watched_segments", "stats", "provenance")
    for f in sorted(vdir.glob("*.template.json")):
        rel = f.relative_to(ROOT)
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            problem(f"video-library starter: {rel} is invalid JSON: {exc}")
            continue
        if not data.get("schema_version"):
            problem(f"video-library starter: {rel} must declare a schema_version")
        for k in null_scalars:
            if data.get(k) is not None:
                problem(f"video-library starter: {rel} field {k!r} must be null "
                        "(a committed starter carries no real video data; real data is gitignored)")
        for k in empty_containers:
            v = data.get(k)
            if v not in ([], {}):
                problem(f"video-library starter: {rel} field {k!r} must be empty ([] or {{}}); "
                        "real stats/tags/transcripts live only in the gitignored store")


def check_importer_robustness():
    """Invariant 35: the P46 content-import robustness guards stay in place (no silent regression).

    (a) no unbounded `while True` pagination in tools/importers/*_import.py (loops must be bounded by
        a max_pages / for-range backstop, so a malformed cursor cannot spin forever);
    (b) every zipfile.ZipFile(...) in tools/import_parse.py is lexically inside a try (a corrupt export
        must degrade, never raise BadZipFile);
    (c) tools/importers/tiktok_import.py coerces create_time via _epoch_to_iso, never a raw
        datetime.fromtimestamp(int(...)) that a bad field can crash;
    (d) each paginating importer still surfaces a truncation signal (the token 'truncated') rather than
        silently returning a partial library at its page cap."""
    import ast
    imp_dir = ROOT / "tools" / "importers"
    if not imp_dir.exists():
        return

    # (a) no `while True` in any importer
    for f in sorted(imp_dir.glob("*_import.py")):
        try:
            tree = ast.parse(f.read_text(encoding="utf-8"))
        except (OSError, SyntaxError) as exc:
            problem(f"importer-robustness: {f.name} failed to parse: {exc}")
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.While) and isinstance(node.test, ast.Constant) and node.test.value is True:
                problem(f"importer-robustness: {f.name} has an unbounded 'while True' pagination loop "
                        "(invariant 35: bound it with max_pages / for _ in range(...))")

    # (d) truncation signal preserved in the paginating importers
    for name in ("youtube_import.py", "instagram_import.py", "tiktok_import.py"):
        p = imp_dir / name
        if p.exists() and "truncated" not in p.read_text(encoding="utf-8"):
            problem(f"importer-robustness: {name} no longer surfaces a truncation signal "
                    "(invariant 35: return a truncated flag at the page cap, not a silent completion)")

    # (b) zipfile.ZipFile() must be inside a try in import_parse.py
    ip = ROOT / "tools" / "import_parse.py"
    if ip.exists():
        try:
            iptree = ast.parse(ip.read_text(encoding="utf-8"))
        except (OSError, SyntaxError) as exc:
            problem(f"importer-robustness: import_parse.py failed to parse: {exc}")
            iptree = None
        if iptree is not None:
            bad = []

            class _ZipVisitor(ast.NodeVisitor):
                def __init__(self):
                    self.try_depth = 0

                def visit_Try(self, node):
                    self.try_depth += 1
                    for n in node.body:
                        self.visit(n)
                    self.try_depth -= 1
                    for n in node.handlers + node.orelse + node.finalbody:
                        self.visit(n)

                def visit_Call(self, node):
                    func = node.func
                    if isinstance(func, ast.Attribute) and func.attr == "ZipFile" and self.try_depth == 0:
                        bad.append(getattr(node, "lineno", "?"))
                    self.generic_visit(node)

            _ZipVisitor().visit(iptree)
            if bad:
                problem(f"importer-robustness: import_parse.py calls zipfile.ZipFile() outside a try at "
                        f"line(s) {bad} (invariant 35: open zips via _safe_zip / try-except BadZipFile)")

    # (c) create_time guard in tiktok: any fromtimestamp(...) must sit inside a try (the _epoch_to_iso
    # guard), never a bare call a malformed field can crash.
    tk = imp_dir / "tiktok_import.py"
    if tk.exists():
        try:
            tktree = ast.parse(tk.read_text(encoding="utf-8"))
        except (OSError, SyntaxError) as exc:
            problem(f"importer-robustness: tiktok_import.py failed to parse: {exc}")
            tktree = None
        if tktree is not None:
            unguarded = []

            class _FtsVisitor(ast.NodeVisitor):
                def __init__(self):
                    self.try_depth = 0

                def visit_Try(self, node):
                    self.try_depth += 1
                    for n in node.body:
                        self.visit(n)
                    self.try_depth -= 1
                    for n in node.handlers + node.orelse + node.finalbody:
                        self.visit(n)

                def visit_Call(self, node):
                    func = node.func
                    if isinstance(func, ast.Attribute) and func.attr == "fromtimestamp" and self.try_depth == 0:
                        unguarded.append(getattr(node, "lineno", "?"))
                    self.generic_visit(node)

            _FtsVisitor().visit(tktree)
            if unguarded:
                problem(f"importer-robustness: tiktok_import.py calls datetime.fromtimestamp() outside a try "
                        f"at line(s) {unguarded} (invariant 35: coerce create_time via the _epoch_to_iso guard)")


def check_doc_template_starters():
    """Invariant 31: committed doc-template starters are pure shape, never content (P42).

    Every tracked pipeline/templates/*.template.json must parse, declare a doc_type from the
    known set, and contain NO block body text, body_ref, or real provenance (body null, body_ref
    null, provenance.source_ref null) and vetted must be false. Creator templates (including any
    attorney-vetted contract text) live only in gitignored .local files; this guarantees no
    legalese, real wording, or provenance ever enters git via a starter."""
    tdir = ROOT / "pipeline" / "templates"
    if not tdir.exists():
        return
    for f in sorted(tdir.glob("*.template.json")):
        rel = f.relative_to(ROOT)
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            problem(f"doc-template starter: {rel} is invalid JSON: {exc}")
            continue
        if data.get("doc_type") not in DOC_TEMPLATE_TYPES:
            problem(f"doc-template starter: {rel} doc_type {data.get('doc_type')!r} not in "
                    f"{sorted(DOC_TEMPLATE_TYPES)}")
        if data.get("vetted") is not False:
            problem(f"doc-template starter: {rel} must carry vetted: false (a committed starter "
                    "is never a vetted document)")
        for b in data.get("blocks", []):
            bid = b.get("block_id", "<missing block_id>")
            if b.get("body") is not None:
                problem(f"doc-template starter: {rel} block {bid} has non-null body "
                        "(starters are shape only; real text lives in gitignored .local files)")
            if b.get("body_ref") is not None:
                problem(f"doc-template starter: {rel} block {bid} has non-null body_ref")
            if (b.get("provenance") or {}).get("source_ref") is not None:
                problem(f"doc-template starter: {rel} block {bid} carries real provenance "
                        "(source_ref must be null in a committed starter)")


TRANSITION_SURFACE_KEYS = {
    "claude_desktop", "claude_code", "claude_web", "chatgpt_web_plain", "chatgpt_custom_gpt",
    "chatgpt_projects", "chatgpt_desktop", "gemini_api", "gemini_gems",
}
TRANSITION_SURFACE_REQUIRED = ("label", "vendor", "class_support", "carries", "flags_enforced",
                               "local_machine_required", "store_options", "setup_steps")
TRANSITION_CLASS_VALUES = {"native", "paste", "remote_mcp", "action", "none"}


def check_transitions():
    """Invariant 32: the cross-modality transition matrix, its doc mirror, the wizard surface
    keys, and the packaging version stamps stay consistent (P43).

    (a) transitions.json parses and its surface key set equals TRANSITION_SURFACE_KEYS exactly;
    (b) every surface record carries the required keys with valid class_support values;
    (c) every pair_overrides key is "<a>-><b>" with both ids in the surface set;
    (d) docs/TRANSITIONS.md names every surface label (the human mirror cannot drop a surface);
    (e) tools/wizard.py names every surface id (added with the /transitions screen);
    (f) packaging artifacts carry the "Packaging version:" stamp (added with the stamp phase);
    (g) every spoke Cross-modality Fallback line names ChatGPT (added with the fallback sweep)."""
    p = ROOT / "shared" / "cross-modality" / "transitions.json"
    if not p.exists():
        problem("transitions: shared/cross-modality/transitions.json missing")
        return
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        problem(f"transitions: transitions.json is invalid JSON: {exc}")
        return
    surfaces = data.get("surfaces") or {}
    got = set(surfaces.keys())
    if got != TRANSITION_SURFACE_KEYS:
        problem(f"transitions: surface key set mismatch; missing {sorted(TRANSITION_SURFACE_KEYS - got)}, "
                f"unexpected {sorted(got - TRANSITION_SURFACE_KEYS)}")
    for sid, rec in surfaces.items():
        for key in TRANSITION_SURFACE_REQUIRED:
            if key not in rec:
                problem(f"transitions: surface {sid} missing required key {key!r}")
        for cls, mode in (rec.get("class_support") or {}).items():
            if mode not in TRANSITION_CLASS_VALUES:
                problem(f"transitions: surface {sid} class_support[{cls}]={mode!r} not in "
                        f"{sorted(TRANSITION_CLASS_VALUES)}")
    for pair in (data.get("pair_overrides") or {}):
        if "->" not in pair:
            problem(f"transitions: pair key {pair!r} is not '<from>-><to>'")
            continue
        frm, _, to = pair.partition("->")
        for sid in (frm, to):
            if sid not in TRANSITION_SURFACE_KEYS:
                problem(f"transitions: pair {pair!r} names unknown surface {sid!r}")
    doc = ROOT / "docs" / "TRANSITIONS.md"
    if not doc.exists():
        problem("transitions: docs/TRANSITIONS.md missing (human mirror of the matrix)")
    else:
        doc_text = doc.read_text(encoding="utf-8")
        for sid, rec in surfaces.items():
            label = rec.get("label")
            if label and label not in doc_text:
                problem(f"transitions: docs/TRANSITIONS.md does not mention surface label {label!r}")
    wiz = ROOT / "tools" / "wizard.py"
    if wiz.exists():
        wiz_text = wiz.read_text(encoding="utf-8")
        for sid in TRANSITION_SURFACE_KEYS:
            if f'"{sid}"' not in wiz_text:
                problem(f"transitions: tools/wizard.py does not name surface id {sid!r} "
                        "(the wizard pickers must cover every surface)")
    # (f) packaging artifacts carry the version stamp so pasted packs can be compared with the
    # repo VERSION and re-synced (E12).
    ci = ROOT / "implementation" / "gpt" / "web" / "custom-instructions.md"
    if ci.exists() and not ci.read_text(encoding="utf-8").startswith("Packaging version:"):
        problem("transitions: implementation/gpt/web/custom-instructions.md must start with the "
                "'Packaging version:' stamp line")
    for exp in ("export-gpt", "export-gem"):
        p_exp = ROOT / "skills" / "atoms" / exp / "SKILL.md"
        if p_exp.exists() and "Packaging version:" not in p_exp.read_text(encoding="utf-8"):
            problem(f"transitions: skills/atoms/{exp}/SKILL.md must require the "
                    "'Packaging version:' stamp in its instruction template")
    # (g) every spoke's Cross-modality Fallback line names ChatGPT, so a reader on that surface
    # can see their own degradation path (the P43-7 sweep cannot silently regress).
    for skill_md in sorted((ROOT / "skills").glob("*/SKILL.md")):
        if skill_md.parent.name == "atoms":
            continue
        text = skill_md.read_text(encoding="utf-8")
        if "## Cross-modality" not in text:
            continue
        seg = text.split("## Cross-modality", 1)[1]
        fb = [ln for ln in seg.splitlines() if ln.startswith("Fallback:")]
        if fb and "ChatGPT" not in fb[0]:
            problem(f"transitions: {skill_md.relative_to(ROOT)} Fallback line does not name "
                    "ChatGPT (every spoke states its ChatGPT degradation path)")


def check_currency_map():
    """Invariant 25: currency-map integrity (P36).

    Every `watched_by` source id named in data-currency-map.json (both the canonical-sources `files`
    and the repo-root `embedded_fact_files`) must resolve to a real entry in source-registry.json, so a
    watched data file or embedded-fact prose can never point at a source that does not exist. Every
    embedded_fact_files entry must name a file that exists on disk and carry at least one watched_by.
    And the P36 highest-value embedded-fact artifacts (the connector registry and the integrations
    engine) must be present in embedded_fact_files, so the facts duplicated in prose/config stay tied
    to their upstream source. No-op when the currency map or registry is absent."""
    cmap_path = ROOT / "canonical-sources" / "data-currency-map.json"
    reg_path = ROOT / "canonical-sources" / "source-registry.json"
    if not cmap_path.exists() or not reg_path.exists():
        return
    try:
        cmap = json.loads(cmap_path.read_text(encoding="utf-8"))
        reg = json.loads(reg_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        problem(f"currency-map: unreadable: {exc}")
        return
    reg_ids = {s.get("id") for s in reg.get("sources", []) if isinstance(s, dict)}
    for group in ("files", "embedded_fact_files"):
        for entry in cmap.get(group, []):
            if not isinstance(entry, dict):
                continue
            f = entry.get("file", "<no file>")
            for sid in entry.get("watched_by", []):
                if sid not in reg_ids:
                    problem(f"currency-map: {group} '{f}' watched_by unknown source id '{sid}'")
    # embedded_fact_files must exist on disk and be non-empty-watched
    for entry in cmap.get("embedded_fact_files", []):
        if not isinstance(entry, dict):
            continue
        f = entry.get("file", "")
        if f and not (ROOT / f).exists():
            problem(f"currency-map: embedded_fact_files names a missing file '{f}'")
        if entry.get("status") == "watched" and not entry.get("watched_by"):
            problem(f"currency-map: embedded_fact_files '{f}' is watched but names no watched_by source")
    # the two highest-value embedded-fact artifacts must be tracked
    tracked = {e.get("file") for e in cmap.get("embedded_fact_files", []) if isinstance(e, dict)}
    for required in ("shared/connectors/connectors.json", "shared/integrations-engine.md"):
        if required not in tracked:
            problem(f"currency-map: required embedded-fact artifact '{required}' is not in embedded_fact_files")


def check_task_tracker():
    """Invariant 24: task-tracker integrity (P35).

    The task tracker rests on four gitignored record templates, three offline tools, its canonical
    engine, and four config capabilities. This verifies each piece is present and structurally sound so
    a spoke never composes against a missing store or tool: the task-register / recurrence-rules /
    shipments / payment-schedule templates exist and parse as JSON; tools/tasks.py, tools/shipments.py,
    and tools/coverage_verify.py exist; shared/tasks-engine.md exists; and creator-os-config.json
    declares task_tracking, shipment_tracking, coverage_verification, and task_store_backend. No-op when
    none of the task-tracker files are present (the feature has not been installed)."""
    uc = ROOT / "pipeline" / "user-context"
    templates = [
        "task-register.template.json",
        "recurrence-rules.template.json",
        "shipments.template.json",
        "payment-schedule.template.json",
    ]
    tools = ["tasks.py", "shipments.py", "coverage_verify.py"]
    engine = ROOT / "shared" / "tasks-engine.md"

    present = engine.exists() or any((uc / t).exists() for t in templates) or \
        any((ROOT / "tools" / t).exists() for t in tools)
    if not present:
        return

    for t in templates:
        p = uc / t
        if not p.exists():
            problem(f"task-tracker: missing register template pipeline/user-context/{t}")
            continue
        try:
            json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            problem(f"task-tracker: {t} is not valid JSON: {exc}")
    for t in tools:
        if not (ROOT / "tools" / t).exists():
            problem(f"task-tracker: missing tool tools/{t}")
    if not engine.exists():
        problem("task-tracker: missing canonical engine shared/tasks-engine.md")

    cfg = ROOT / "creator-os-config.json"
    if cfg.exists():
        try:
            caps = (json.loads(cfg.read_text(encoding="utf-8")) or {}).get("capabilities", {})
        except (OSError, json.JSONDecodeError) as exc:
            problem(f"task-tracker: creator-os-config.json unreadable: {exc}")
            caps = {}
        for cap in ("task_tracking", "shipment_tracking", "coverage_verification", "task_store_backend"):
            if cap not in caps:
                problem(f"task-tracker: creator-os-config.json is missing the '{cap}' capability")


def check_migration_manifest():
    """Invariant 33: every pipeline data template's current schema_version has a migration-manifest
    entry, so a schema bump cannot ship without a human-authored why/impact (P44).

    For every tracked pipeline/**/*.template.json that carries a top-level schema_version, the
    CHANGELOG.migrations.json must contain a migration entry whose `template` equals that path and
    whose `to` equals the current schema_version (string compare). Each entry must carry non-empty
    why_it_matters and concrete_impact (no-fabrication: the "why this matters to your data" text is
    authored at ship time, never generated at read time) and a boolean reversible. This lets the
    local .local audit (tools/local_audit.py) narrate impact and forces every future schema_version
    bump to add an explaining entry here."""
    man_path = ROOT / "CHANGELOG.migrations.json"
    if not man_path.exists():
        problem("migration-manifest: CHANGELOG.migrations.json is missing")
        return
    try:
        man = json.loads(man_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        problem(f"migration-manifest: CHANGELOG.migrations.json invalid JSON: {exc}")
        return
    by_key = {}
    for m in man.get("migrations", []):
        if not isinstance(m, dict):
            problem("migration-manifest: a migration entry is not an object")
            continue
        tmpl = m.get("template", "<no template>")
        for req in ("template", "to", "why_it_matters", "concrete_impact", "reversible"):
            if req not in m:
                problem(f"migration-manifest: entry {tmpl} is missing required key '{req}'")
        if not str(m.get("why_it_matters") or "").strip():
            problem(f"migration-manifest: entry {tmpl} has empty why_it_matters (must be human-authored)")
        if not str(m.get("concrete_impact") or "").strip():
            problem(f"migration-manifest: entry {tmpl} has empty concrete_impact")
        if not isinstance(m.get("reversible"), bool):
            problem(f"migration-manifest: entry {tmpl} 'reversible' must be a boolean")
        by_key[(m.get("template"), str(m.get("to")))] = m
    pdir = ROOT / "pipeline"
    if not pdir.exists():
        return
    for f in sorted(pdir.rglob("*.template.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict) or "schema_version" not in data:
            continue
        rel = str(f.relative_to(ROOT))
        sv = str(data["schema_version"])
        if (rel, sv) not in by_key:
            problem(f"migration-manifest: {rel} is at schema_version {sv} but CHANGELOG.migrations.json "
                    f"has no entry with template={rel} and to={sv}; add one (with why_it_matters + "
                    "concrete_impact) so the schema bump is explained to users")


def check_legal_source_category():
    """Invariant 37: legal-source category correctness (P47, seam 12). Every registry source cited by
    the legal-requirement-check atom (its id appears in that source's used_by) must carry category
    'legal-authority'. A legal atom must not rest on a source mis-filed as seo-authority (or anything
    else), which would let a legal claim cite a non-legal source. Re-tag a mis-filed source with
    `python3 tools/source_currency.py update-source <id> --category legal-authority`."""
    reg_path = ROOT / "canonical-sources" / "source-registry.json"
    if not reg_path.exists():
        return
    try:
        reg = json.loads(reg_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        problem(f"legal-source-category: source-registry.json unreadable: {exc}")
        return
    for s in reg.get("sources", []):
        if "legal-requirement-check" in (s.get("used_by") or []):
            cat = s.get("category")
            if cat != "legal-authority":
                problem(f"legal-source-category: source {s.get('id')!r} is cited by "
                        f"legal-requirement-check but its category is {cat!r}, not 'legal-authority'; "
                        f"re-tag it (tools/source_currency.py update-source {s.get('id')} "
                        f"--category legal-authority)")


def check_marketplace_version():
    """Invariant 38: marketplace/plugin version equality (P47, seam 1/6/8; the error half of the
    versions-coverage design). .claude-plugin/marketplace.json metadata.version and every
    plugins[].version must equal versions.json.ecosystem, so a published marketplace card can never
    advertise a version that has drifted from the ecosystem. version.py --check already ties VERSION
    and plugin.json to the ecosystem; this closes the marketplace surface."""
    vj_path = ROOT / "versions.json"
    mp_path = ROOT / ".claude-plugin" / "marketplace.json"
    if not vj_path.exists() or not mp_path.exists():
        return
    try:
        eco = json.loads(vj_path.read_text(encoding="utf-8")).get("ecosystem")
        mp = json.loads(mp_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        problem(f"marketplace-version: unreadable version/marketplace file: {exc}")
        return
    meta_v = (mp.get("metadata") or {}).get("version")
    if meta_v != eco:
        problem(f"marketplace-version: marketplace.json metadata.version ({meta_v!r}) != versions.json "
                f"ecosystem ({eco!r})")
    for p in mp.get("plugins", []):
        if p.get("version") != eco:
            problem(f"marketplace-version: marketplace.json plugin {p.get('name')!r} version "
                    f"({p.get('version')!r}) != ecosystem ({eco!r})")


def check_versions_coverage():
    """Invariant 39 (advisory): versions.json tree coverage (P47, seams 1/6/8). Advisory, not a hard
    gate. (a) Phantom: every skill/engine/protocol NAMED in versions.json resolves to a file on disk
    (no stale version entry pointing at a deleted component). (b) Untracked flat engine: every flat
    shared/*.md engine that versions.json does not track and that is not on versions.json's
    _tracked_subset_allowlist.engines is surfaced, so a newly added top-level engine that nobody
    version-stamped is noticed. Atoms and spokes are intentionally outside versions.json's curated
    subset and are not flagged."""
    vpath = ROOT / "versions.json"
    if not vpath.exists():
        return
    try:
        v = json.loads(vpath.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        advisory(f"versions-coverage: versions.json unreadable: {exc}")
        return
    skill_dirs = ({p.parent.name for p in (ROOT / "skills").rglob("SKILL.md")}
                  if (ROOT / "skills").exists() else set())
    for name in (v.get("skills") or {}):
        if name not in skill_dirs:
            advisory(f"versions-coverage: versions.json tracks skill {name!r} but no "
                     f"skills/**/{name}/SKILL.md exists")
    for name in (v.get("engines") or {}):
        if not (ROOT / "shared" / f"{name}.md").exists():
            advisory(f"versions-coverage: versions.json tracks engine {name!r} but shared/{name}.md "
                     f"does not exist")
    for name in (v.get("protocols") or {}):
        if not (ROOT / "protocols" / f"{name}.md").exists():
            advisory(f"versions-coverage: versions.json tracks protocol {name!r} but "
                     f"protocols/{name}.md does not exist")
    tracked = set(v.get("engines") or {})
    allow = set((v.get("_tracked_subset_allowlist") or {}).get("engines") or [])
    if (ROOT / "shared").exists():
        for ef in sorted((ROOT / "shared").glob("*.md")):
            if ef.stem not in tracked and ef.stem not in allow:
                advisory(f"versions-coverage: flat engine shared/{ef.stem}.md is neither "
                         f"version-tracked in versions.json.engines nor listed in "
                         f"_tracked_subset_allowlist.engines")


def check_used_by_paths():
    """Invariant 40 (advisory): registry used_by path resolution (P47, seam 4). Advisory. Every
    used_by token that looks like a file path (contains '/' or ends in a known extension) must resolve
    on disk, relative to the repo root OR to canonical-sources/ (used_by mixes both bases). Catches a
    used_by pointing at a renamed or deleted tool/engine/data file. Bare identifiers (skill, connector,
    capability names) live in overlapping namespaces and are intentionally not checked here."""
    reg_path = ROOT / "canonical-sources" / "source-registry.json"
    if not reg_path.exists():
        return
    try:
        reg = json.loads(reg_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        advisory(f"used-by-paths: source-registry.json unreadable: {exc}")
        return
    exts = (".py", ".md", ".json", ".txt", ".js", ".yml", ".yaml")
    tokens = {}
    for s in reg.get("sources", []):
        for u in (s.get("used_by") or []):
            if ("/" in u or u.endswith(exts)) and u not in tokens:
                tokens[u] = s.get("id")
    for u, sid in sorted(tokens.items()):
        if not ((ROOT / u).exists() or (ROOT / "canonical-sources" / u).exists()):
            advisory(f"used-by-paths: used_by {u!r} (first seen on source {sid!r}) does not resolve "
                     f"under the repo root or canonical-sources/")


def check_capability_connector_exists():
    """Invariant 41 (advisory): capability->connector target existence (P47, seam 10; the inverse of
    invariant 18). Advisory. Every connector id on the right side of connectors.py
    CAPABILITY_TO_CONNECTOR must exist as a connector in connectors.json, so a capability cannot map to
    a connector that was renamed or removed."""
    import ast

    cpy = ROOT / "shared" / "connectors" / "connectors.py"
    cjson = ROOT / "shared" / "connectors" / "connectors.json"
    if not cpy.exists() or not cjson.exists():
        return
    try:
        conns = json.loads(cjson.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        advisory(f"capability-connector: connectors.json unreadable: {exc}")
        return
    conn_ids = {c.get("id") for c in conns.get("connectors", []) if isinstance(c, dict)}
    try:
        tree = ast.parse(cpy.read_text(encoding="utf-8"))
    except (OSError, SyntaxError) as exc:
        advisory(f"capability-connector: connectors.py unparseable: {exc}")
        return
    mapping = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "CAPABILITY_TO_CONNECTOR" for t in node.targets) \
                and isinstance(node.value, ast.Dict):
            for k, val in zip(node.value.keys, node.value.values):
                if isinstance(k, ast.Constant) and isinstance(val, ast.Constant):
                    mapping[k.value] = val.value
    for cap, target in sorted(mapping.items()):
        if target not in conn_ids:
            advisory(f"capability-connector: capability {cap!r} maps to connector {target!r} which is "
                     f"not defined in connectors.json")


def check_registry_writer_count():
    """Invariant 42 (advisory): registry writer-count integrity (P47, write path). Advisory. Exactly
    five sanctioned tools may write source-registry.json: four import registry_io directly
    (source_currency, traversal_engine, dependency_currency, update_check) and competitor_snapshot
    writes through source_currency's re-exported save_registry. A new tool that references save_registry
    (a new writer) or a vanished one is surfaced so the writer list in registry_io.py + CLAUDE.md stays
    true."""
    tools_dir = ROOT / "tools"
    if not tools_dir.exists():
        return
    expected = {"source_currency", "traversal_engine", "dependency_currency", "update_check",
                "competitor_snapshot"}
    found = set()
    imp_regio = re.compile(r"(?m)^\s*(import registry_io\b|from registry_io import)")
    imp_sc = re.compile(r"\bimport source_currency\b")
    names_save = re.compile(r"\bsave_registry\b")
    for f in sorted(tools_dir.rglob("*.py")):
        if f.stem == "registry_io":
            continue
        try:
            txt = f.read_text(encoding="utf-8")
        except OSError:
            continue
        if names_save.search(txt) and (imp_regio.search(txt) or imp_sc.search(txt)):
            found.add(f.stem)
    extra = sorted(found - expected)
    missing = sorted(expected - found)
    if extra:
        advisory(f"registry-writers: unexpected tool(s) reference the registry writer: {extra}; if "
                 f"legitimate, add them to the sanctioned writer list in registry_io.py + CLAUDE.md")
    if missing:
        advisory(f"registry-writers: expected registry writer(s) not detected: {missing}; the writer "
                 f"list in registry_io.py + CLAUDE.md may be stale")


def check_moving_dates():
    """Invariant 43 (advisory): moving-date calendar (P47). Advisory. Reads
    canonical-sources/moving-dates.json (the docs/FRESHNESS.md 'known moving dates' as dated JSON) and
    surfaces any date whose effective (or phase_2) has passed while it has not been re-verified since it
    took effect (verified_after missing or < effective). Would have caught the NY synthetic-performer
    law sitting as pending after its 2026-06-09 effect date. Time-dependent by design: a future date
    starts surfacing once it passes."""
    import datetime

    mpath = ROOT / "canonical-sources" / "moving-dates.json"
    if not mpath.exists():
        return
    try:
        data = json.loads(mpath.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        advisory(f"moving-dates: moving-dates.json unreadable: {exc}")
        return
    today = datetime.date.today().isoformat()
    for d in data.get("dates", []):
        va = d.get("verified_after")
        for field in ("effective", "phase_2"):
            eff = d.get(field)
            if eff and eff <= today and (not va or va < eff):
                advisory(f"moving-dates: {d.get('id')!r} {field} {eff} has passed but has not been "
                         f"re-verified since (verified_after={va!r}); re-check the source and update "
                         f"(staged fix in volatile-corrections.2026-07-14.json)")


# degraded_behavior keys that cover several capabilities, or a renamed capability, so they are NOT of
# the direct '<capability>_disabled' form. Invariant 44 skips these (e.g. api_disabled covers the
# platform read APIs; publishing_disabled covers the per-platform publishing flags).
SHARED_DEGRADED_KEYS = {
    "api_disabled", "publishing_disabled", "per_platform_publishing_disabled",
    "live_publishing_disabled", "duckdb_disabled", "e2b_disabled", "gem_export_disabled",
    "gpt_export_disabled", "jupyter_disabled", "wolfram_disabled", "stats_general_disabled",
    "video_editing_disabled", "playbook_bootstrap_disabled",
}


def check_degraded_orphans():
    """Invariant 44 (advisory): degraded_behavior/capability parity (P47, seam 5). Advisory. Every
    creator-os-config.json degraded_behavior key of the direct form '<name>_disabled' must correspond
    to a real capability '<name>', UNLESS it is a shared/renamed key on SHARED_DEGRADED_KEYS (which
    cover several capabilities). Surfaces a degraded_behavior entry orphaned by a capability
    rename/removal. Low false-positive: shared keys are skipped, so no per-capability alias map is
    needed."""
    cfg = ROOT / "creator-os-config.json"
    if not cfg.exists():
        return
    try:
        c = json.loads(cfg.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        advisory(f"degraded-orphans: creator-os-config.json unreadable: {exc}")
        return
    caps = set(c.get("capabilities") or {})
    for key in sorted(c.get("degraded_behavior") or {}):
        if key in SHARED_DEGRADED_KEYS:
            continue
        if key.endswith("_disabled"):
            cap = key[: -len("_disabled")]
            if cap not in caps:
                advisory(f"degraded-orphans: degraded_behavior key {key!r} has no matching capability "
                         f"{cap!r} in creator-os-config.json (orphaned by a rename/removal, or add it "
                         f"to SHARED_DEGRADED_KEYS if it deliberately covers several capabilities)")


def check_content_vs_digest():
    """Invariant 45 (advisory, loud): content-vs-digest silent-staleness (P47, seam 3). Advisory and
    intentionally heuristic. The freshness digest is sha256(source ids + currency-map as_of); a real
    upstream content change recorded as a source last_checked / last_changed is NOT a digest input, so
    the packaged knowledge baseline can keep a stale date while invariant 26 still passes. This surfaces
    (as one loud advisory) any registry source re-verified AFTER the freshness bundle's as_of, meaning
    the downloadable baseline may lag detected content and should be re-stamped."""
    reg_path = ROOT / "canonical-sources" / "source-registry.json"
    fb_path = ROOT / "implementation" / "freshness-bundle.json"
    if not reg_path.exists() or not fb_path.exists():
        return
    try:
        reg = json.loads(reg_path.read_text(encoding="utf-8"))
        fb = json.loads(fb_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        advisory(f"content-vs-digest: unreadable registry/freshness file: {exc}")
        return
    as_of = fb.get("as_of") or ""
    if not as_of:
        return
    newer = []
    for s in reg.get("sources", []):
        for field in ("last_changed", "last_checked"):
            d = s.get(field)
            if d and d > as_of:
                newer.append((d, s.get("id"), field))
                break
    if newer:
        newer.sort(reverse=True)
        sample = ", ".join(f"{sid} ({field} {d})" for d, sid, field in newer[:3])
        advisory(f"content-vs-digest: {len(newer)} registry source(s) were re-verified after the "
                 f"freshness baseline as_of {as_of} (e.g. {sample}); the packaged knowledge baseline "
                 f"may lag detected content -> run tools/build_freshness_bundle.py --apply to re-stamp")


def check_url_provenance():
    """Invariant 46: URL provenance (P49 WS3). Every http(s):// literal in tools/**/*.py must be
    ACCOUNTED FOR by exactly one of: (a) a host in canonical-sources/source-registry.json (data/reference
    sources), (b) a base domain in canonical-sources/operational-url-allowlist.json (infra/plumbing
    endpoints, each with a written reason), or (c) an excluded-by-rule host (example/placeholder host,
    localhost, or a schema/XML namespace). Anything else is an undeclared endpoint and fails the build,
    so a typo'd or unvetted URL cannot ship silently. STATIC only: this never fetches a URL. Scope is
    executable code (tools/**/*.py); doc bibliographies are out of scope by rule."""
    import urllib.parse

    reg_path = ROOT / "canonical-sources" / "source-registry.json"
    allow_path = ROOT / "canonical-sources" / "operational-url-allowlist.json"
    try:
        reg = json.loads(reg_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        problem(f"url-provenance: source-registry.json unreadable: {exc}")
        return
    try:
        allow_doc = json.loads(allow_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        problem(f"url-provenance: operational-url-allowlist.json unreadable: {exc}")
        return

    reg_hosts = set()
    for s in reg.get("sources", []):
        u = s.get("url") or ""
        if u.startswith("http"):
            reg_hosts.add(urllib.parse.urlparse(u).netloc.lower().split(":")[0])
    allow_hosts = {e.get("host", "").lower() for e in allow_doc.get("allowed", []) if e.get("host")}
    schema_hosts = {"www.w3.org", "w3.org", "www.opengis.net", "opengis.net",
                    "schema.org", "json-schema.org", "www.google.com/recaptcha"}

    def excluded(h):
        # placeholder / sample / infra-local / schema-namespace hosts are not real endpoints
        return (h in ("localhost", "127.0.0.1") or h.endswith(".") or "example" in h
                or "." not in h or h in schema_hosts)

    def covered(h, allowed):
        return any(h == a or h.endswith("." + a) for a in allowed)

    url_re = re.compile(r'https?://([^/\s"\'\\)>}]+)')
    tools_dir = ROOT / "tools"
    for py in sorted(tools_dir.rglob("*.py")):
        if "__pycache__" in str(py):
            continue
        try:
            text = py.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        seen = set()
        for m in url_re.finditer(text):
            host = m.group(1).split(":")[0].lower()
            if host in seen:
                continue
            seen.add(host)
            if excluded(host) or covered(host, reg_hosts) or covered(host, allow_hosts):
                continue
            problem(f"url-provenance: {py.relative_to(ROOT)} hardcodes an undeclared URL host "
                    f"{host!r}; add it to source-registry.json (if it is a re-checkable data source) or "
                    f"canonical-sources/operational-url-allowlist.json (if it is an operational endpoint, "
                    f"with a reason), or it is a genuine placeholder that the exclusion rules should cover")


def check_projection_staleness():
    """Invariant 47 (advisory): knowledge-pack projection staleness (P49 WS7). The hand-authored
    Claude/GPT/Gemini knowledge files project the shared/*.md engines and protocols/*.md. This advisory
    recomputes each source engine's sha256 and, when one has moved since the projection manifest was last
    reconciled, surfaces the projection files that may now lag their source (a staleness signal, not a
    prose diff). Non-blocking: refresh the projection and run `tools/projection_manifest.py reconcile`."""
    try:
        import projection_manifest as pm
    except Exception as exc:  # noqa: BLE001
        advisory(f"projection-staleness: projection_manifest unimportable: {exc}")
        return
    for e in pm.check(ROOT):
        note = e.get("note")
        if note:
            advisory(f"projection-staleness: {note}")
            continue
        changed = ", ".join(e.get("changed_sources", [])) or "-"
        missing = e.get("missing_sources", [])
        msg = (f"projection-staleness: {e.get('knowledge_file')} may be stale; source(s) changed since "
               f"reconcile: {changed}")
        if missing:
            msg += f"; missing source(s): {', '.join(missing)}"
        advisory(msg + " (refresh the projection, then run tools/projection_manifest.py reconcile)")


def check_invariant_catalog():
    """Invariant 36: invariant-catalog integrity (the keystone, P47). Parses this file and asserts
    (a) every check_* function registered in main() carries an 'Invariant N' docstring label,
    (b) no invariant number is claimed by two checks (catches the historical double-'Invariant 22'),
    (c) the label set is contiguous from 1 to the highest label except for MERGED_INVARIANTS, and
    (d) the module header 'Invariants enforced:' enumeration documents exactly the enforced numbers
    plus the merged ones (catches the stale 'header lists 1-23 while code implements more' drift).
    Keeps the invariant catalog a single source of truth: a mislabeled, unlabeled, or undocumented
    check cannot slip in silently."""
    import ast

    try:
        tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    except (OSError, SyntaxError) as exc:
        problem(f"invariant-catalog: sync_check.py could not be parsed: {exc}")
        return

    label_re = re.compile(r"^Invariants?\s+(\d+(?:\s*(?:,|and)\s*\d+)*)")
    num_re = re.compile(r"\d+")

    labels_by_func = {}
    main_node = None
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        if node.name == "main":
            main_node = node
        if node.name.startswith("check_"):
            m = label_re.match((ast.get_docstring(node) or "").strip())
            labels_by_func[node.name] = [int(n) for n in num_re.findall(m.group(1))] if m else []

    if main_node is None:
        problem("invariant-catalog: could not locate main() to read the registered checks")
        return

    registered = [n.func.id for n in ast.walk(main_node)
                  if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                  and n.func.id.startswith("check_")]

    owner = {}  # invariant number -> the check_* function that carries the label
    for fn in registered:
        nums = labels_by_func.get(fn, [])
        if not nums:
            problem(f"invariant-catalog: {fn}() is registered in main() but its docstring carries no "
                    f"'Invariant N' label; every registered check must be labeled")
            continue
        for n in nums:
            if n in owner:
                problem(f"invariant-catalog: Invariant {n} is claimed by both {owner[n]}() and {fn}(); "
                        f"each invariant number must be unique")
            else:
                owner[n] = fn

    enforced = set(owner)
    if not enforced:
        return

    highest = max(enforced)
    missing = sorted((set(range(1, highest + 1)) - MERGED_INVARIANTS) - enforced)
    if missing:
        problem(f"invariant-catalog: the invariant sequence 1..{highest} is not contiguous; no check "
                f"is labeled {missing} (if intentionally retired, add it to MERGED_INVARIANTS)")
    reused = sorted(enforced & MERGED_INVARIANTS)
    if reused:
        problem(f"invariant-catalog: Invariant(s) {reused} are documented as merged/retired but a check "
                f"claims the number; use the next free number instead")

    header = ast.get_docstring(tree) or ""
    if "Invariants enforced:" in header:
        listed = {int(x) for x in re.findall(r"^\s*(\d+)\.\s", header.split("Invariants enforced:", 1)[1], re.M)}
        documented = enforced | MERGED_INVARIANTS
        undocumented = sorted(documented - listed)
        if undocumented:
            problem(f"invariant-catalog: the module header 'Invariants enforced:' list omits invariant(s) "
                    f"{undocumented}; document every enforced/merged invariant in the header")
        phantom = sorted(listed - documented)
        if phantom:
            problem(f"invariant-catalog: the module header lists invariant(s) {phantom} that no check "
                    f"enforces and that are not in MERGED_INVARIANTS; correct the header enumeration")


def main():
    manifest = load_manifest()
    check_canonical(manifest)
    check_skills()
    check_formatting()
    check_references()
    check_frontmatter_loads()
    check_hub()
    check_workflows()
    check_yaml_strict()
    check_atom_evals()
    check_workflow_phases()
    check_atom_composition()
    check_routing_table()
    check_agent_contracts()
    check_schema_verification_fields()
    check_workflow_verification()
    check_readonly_mandate()
    check_connector_capability_mapping()
    check_local_privacy()
    check_pipeline_allowlist()
    check_secret_content()
    check_dependency_registry()
    check_construction()
    check_task_tracker()
    check_currency_map()
    check_freshness_bundle()
    check_jurisdiction()
    check_cross_modality()
    check_implementation_schemas()
    check_doc_template_starters()
    check_transitions()
    check_migration_manifest()
    check_video_library_starter()
    check_importer_robustness()
    check_legal_source_category()
    check_marketplace_version()
    check_versions_coverage()
    check_used_by_paths()
    check_capability_connector_exists()
    check_registry_writer_count()
    check_moving_dates()
    check_degraded_orphans()
    check_content_vs_digest()
    check_url_provenance()
    check_projection_staleness()
    check_invariant_catalog()
    if ADVISORIES:
        print(f"DRIFT GUARD: {len(ADVISORIES)} advisory note(s) (non-blocking):")
        for item in ADVISORIES:
            print(f"  ~ {item}")
        print()
    if PROBLEMS:
        print(f"DRIFT GUARD: {len(PROBLEMS)} problem(s) found\n")
        for item in PROBLEMS:
            print(f"  - {item}")
        return 1
    print("DRIFT GUARD: clean (all invariants hold)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
