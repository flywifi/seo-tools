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
  48. Doc-count truth (P49 WS2): live architecture/setup docs must state the true global totals
      (spokes, invariants) computed by tools/count_truth.py; historical phase-logs are out of scope.
  49. Doc symbol references (P52): a `<!-- verify: path[::symbol] -->` marker in a maintainer/SKILL/doc
      file asserts the named code still exists (path resolves; a ::symbol must be a module-level
      def/class/assignment or Class.method). Extends invariant 5 from paths to symbols.
  50. Tools-layer maintainer coverage (P52): each designated high-value tools subtree
      (TOOLS_MAINTAINER_DIRS) must carry a MAINTAINER_README.md (invariant 3 covers skills/ only).
  51. Doc freshness (P52, advisory): when a code file a doc documents (tools/doc_freshness.py
      DOC_SOURCES) changes sha since the doc-freshness manifest was reconciled, the doc is surfaced as
      possibly stale (a content-hash signal, not a prose diff).
  52. Doc-declared source registration (P55): every id a maintainer/SKILL/doc file declares in a
      fenced ```sources block or an inline `<!-- source: id -->` marker must exist in
      canonical-sources/source-registry.json with a matching url; unparseable blocks fail. Fail-closed
      like invariant 23: a doc citation forces a tracked registry entry.
  53. Connector resolver smoke (P63): shared/connectors/connectors.py::resolve executes cleanly over
      the committed connectors.json (resolve({}) — the pure default-flag path). Invariants 18/23/41
      only inspect the registry statically; this one runs it, so a malformed entry the resolver
      cannot process (e.g. a missing default_flag) fails the build instead of shipping.
  54. Payload-loader robustness (P63): tools/finance.py::_read_json and
      tools/obligations.py::_load_json keep their try/except guard so a bad CLI payload path or
      inline JSON yields the clean {"error","next_step"} envelope, never a raw traceback. The
      sibling of invariant 35 for the two offline money/legal CLIs.
  55. Surface-origin completeness (P64): the compute-job origin vocabulary
      (tools/handoff/queue.py ALLOWED_ORIGINS == the shared/schemas/compute-job.json enum) is
      fully claimed by the cross-modality surface model — every origin appears in at least one
      transitions.json surface's `origins` list or the documented _residual_origin_note. The
      independent-oracle reconciliation that would have caught the missing Cowork surface the day
      the cowork origin shipped.
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
# High-value tools subtrees required to carry a MAINTAINER_README.md (invariant 50). The skills-only
# maintainer requirement (invariant 3) does not reach tools/, so these are declared explicitly.
TOOLS_MAINTAINER_DIRS = ("tools/publishing", "tools/handoff")


def _reference_scan_files():
    """The files whose backticked paths + verify markers the guard validates (invariants 5, 49):
    every skills SKILL.md + MAINTAINER_README.md, docs/*.md, the root README.md, and each tools
    maintainer README. (P52 expanded this from skills/ only to also cover docs and tools docs.)"""
    files = []
    skills = ROOT / "skills"
    if skills.exists():
        for skill_dir in sorted(skills.rglob("*")):
            if not skill_dir.is_dir():
                continue
            for filename in ("SKILL.md", "MAINTAINER_README.md"):
                target = skill_dir / filename
                if target.exists():
                    files.append(target)
    docs = ROOT / "docs"
    if docs.exists():
        files.extend(sorted(docs.rglob("*.md")))
    root_readme = ROOT / "README.md"
    if root_readme.exists():
        files.append(root_readme)
    for d in TOOLS_MAINTAINER_DIRS:
        target = ROOT / d / "MAINTAINER_README.md"
        if target.exists():
            files.append(target)
    return files


def check_references():
    """Invariant 5 (expanded): every backticked repo path in a SKILL.md / MAINTAINER_README.md,
    docs/*.md, or README.md must resolve on disk. P52 widened the scope from skills/ only to also
    include docs/ and the tools maintainer READMEs (a doc naming a removed file no longer ships)."""
    for target in _reference_scan_files():
        rel = target.relative_to(ROOT)
        text = target.read_text(encoding="utf-8")
        for match in PATH_RE.finditer(text):
            ref = match.group(1)
            # `.local.` files are gitignored runtime data (created per-user); a doc naming their
            # location is correct even though the file is absent from the repo. Do not flag them.
            if ".local." in ref:
                continue
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
    """Invariant 15: agent output schemas have verification envelope fields.

    The skip set lists DATA CONTRACTS that live in shared/schemas/ but are not agent output
    schemas: the envelope definitions themselves, and compute-job.json (the P60 job ticket/result
    contract; tickets are validated inputs, not agent findings, so a verification envelope would
    be meaningless on them)."""
    schemas_dir = ROOT / "shared" / "schemas"
    if not schemas_dir.exists():
        return
    skip = {"verification-envelope.json", "verification-decision.json", "compute-job.json",
            "injection-scan.json"}  # P62 data contract: the two-pass scan/reconciliation record, not an agent output schema
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
    "pipeline/inbox/inbox-ledger.template.json",
}

# Invariant 20 (second half): file types that must never be tracked anywhere in the repo.
# The list itself lives in tools/secret_scan.py (FORBIDDEN_DATA_SUFFIXES) so the drift guard,
# the --staged pre-commit gate, and CI enforce ONE list that cannot drift apart. It covers
# spreadsheets, delimited/columnar exports, financial application files, credential/key stores,
# databases, backups, email/PIM/contacts, disk images, archives, office binaries, and capture
# media; tiered rationale in ADR 0048.
try:
    from secret_scan import FORBIDDEN_DATA_SUFFIXES as FORBIDDEN_TRACKED_SUFFIXES
except ImportError:  # imported as a module with tools/ not on sys.path
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from secret_scan import FORBIDDEN_DATA_SUFFIXES as FORBIDDEN_TRACKED_SUFFIXES
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
        # A silent skip on the highest-severity invariants would report "clean" while the
        # data-at-rest and secret boundaries got ZERO enforcement (a downloaded non-git copy of
        # the repo hits this path). Say so loudly; CI=1 turns the same condition into a failure.
        print(f"  [ADVISORY] privacy invariant {invariant} DID NOT RUN: git is unavailable "
              f"(not a git checkout, or git is not installed). Data-at-rest and secret "
              f"enforcement is OFF in this run; work inside the git repo, or set CI=1 to make "
              f"this condition fail closed.")


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
        return
    # The scanner exits 0 both when clean AND when it skipped because git is unavailable
    # (a non-git copy of the repo). The skip must not read as a pass here: surface the same
    # loud advisory the filename invariants use, so all three privacy layers report honestly.
    if "git unavailable" in out.stdout:
        _privacy_git_unavailable(21)


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
    "claude_desktop", "claude_code", "claude_web", "cowork_local", "cowork_remote",
    "chatgpt_web_plain", "chatgpt_custom_gpt",
    "chatgpt_projects", "chatgpt_desktop", "gemini_api", "gemini_gems",
}
TRANSITION_SURFACE_REQUIRED = ("label", "vendor", "class_support", "carries", "flags_enforced",
                               "local_machine_required", "store_options", "origins", "setup_steps")
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
    # P60: covers the compute_handoff_enabled capability (named like live_publishing_enabled).
    "compute_handoff_disabled",
    # P61: covers the job_store_writes_enabled capability (the *_disabled/_enabled naming split).
    "job_store_writes_disabled",
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
    executable code (tools/**/*.py); doc bibliographies are out of scope by rule.

    DEV-TRAP: an inline f-string that builds a URL host from a cfg.get(...) call inside the braces
    parses as an undeclared host (the static grep stops at the first quote, capturing a dotted token).
    Compute the host into a plain variable FIRST, then interpolate just that variable, so the captured
    token has no dot and is excluded. See tools/publishing/MAINTAINER_README.md "Contributor gotchas"."""
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


def check_doc_freshness():
    """Invariant 51 (advisory): doc freshness (P52). High-value maintainer/docs are bound to the code
    files they document (tools/doc_freshness.py DOC_SOURCES). When a bound source's sha256 has moved
    since the doc-freshness manifest was last reconciled, this surfaces the doc as possibly stale (a
    content-hash signal, not a prose diff). Non-blocking: re-read the doc, fix any drift, then run
    `python3 tools/doc_freshness.py reconcile` to re-bless it."""
    try:
        import doc_freshness as df
    except Exception as exc:  # noqa: BLE001
        advisory(f"doc-freshness: doc_freshness unimportable: {exc}")
        return
    for e in df.check(ROOT):
        note = e.get("note")
        if note:
            advisory(f"doc-freshness: {note}")
            continue
        changed = ", ".join(e.get("changed_sources", [])) or "-"
        missing = e.get("missing_sources", [])
        msg = (f"doc-freshness: {e.get('doc')} may be stale; documented source(s) changed since "
               f"reconcile: {changed}")
        if missing:
            msg += f"; missing source(s): {', '.join(missing)}"
        advisory(msg + " (re-read the doc, then run tools/doc_freshness.py reconcile)")


def check_doc_count_truth():
    """Invariant 48: doc-count truth (P49 WS2). Recomputes the canonical global totals from the tree
    (tools/count_truth.py) and fails when a live architecture/setup doc states a different number for a
    global total (spokes, invariants). Scope is a CURATED list of files that only ever state global
    totals -- STATE.md phase-logs, ledger entries, and per-spoke 'composes N atoms' claims are out of
    scope (historical / local, not global totals), so they are never scanned."""
    try:
        import count_truth
        truth = count_truth.counts(ROOT)
    except Exception as exc:  # noqa: BLE001
        problem(f"doc-count-truth: count_truth unavailable: {exc}")
        return
    # (relpath, count_key, keyword) -- each digit before <keyword> in <relpath> must equal truth[key].
    checks = [
        ("docs/ARCHITECTURE.md", "spokes", "spokes"),
        ("CLAUDE.md", "spokes", "spokes"),
        ("creator-os-config.json", "spokes", "spokes"),
        ("implementation/gpt/web/README.md", "spokes", "spokes"),
        ("implementation/claude/project/README.md", "spokes", "spokes"),
        ("docs/BRAND-DEALS.md", "invariants", "invariants"),
        ("docs/DOCUMENT-TEMPLATES.md", "invariants", "invariants"),
        ("skills/atoms/post-status/MAINTAINER_README.md", "invariants", "invariants"),
        ("skills/atoms/publish-draft/MAINTAINER_README.md", "invariants", "invariants"),
        ("skills/atoms/schedule-post/MAINTAINER_README.md", "invariants", "invariants"),
    ]
    for rel, key, kw in checks:
        p = ROOT / rel
        if not p.exists():
            continue
        text = p.read_text(encoding="utf-8", errors="ignore")
        for m in re.finditer(rf"(\d+)\s+{kw}\b", text):
            n = int(m.group(1))
            if n != truth[key]:
                problem(f"doc-count-truth: {rel} states '{n} {kw}' but the tree has {truth[key]} "
                        f"{kw}; correct the doc (counts are computed by tools/count_truth.py)")


VERIFY_RE = re.compile(r"<!--\s*verify:\s*(\S+?)\s*-->")


def _module_symbols(pyfile):
    """Module-level symbol names defined in a .py file (def/class/assign) plus Class.method entries.
    Returns None if the file cannot be parsed."""
    import ast
    try:
        tree = ast.parse(pyfile.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return None
    names = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            for tgt in node.targets:
                if isinstance(tgt, ast.Name):
                    names.add(tgt.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
        if isinstance(node, ast.ClassDef):
            for sub in node.body:
                if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    names.add(f"{node.name}.{sub.name}")
    return names


def check_doc_symbol_refs():
    """Invariant 49: doc symbol references (P52). A `<!-- verify: path[::symbol] -->` marker in a
    maintainer/SKILL/doc file asserts the named code still exists: the path must resolve, and a
    ::symbol must be a module-level def/class/assignment (or Class.method) in that .py module. This
    extends the path-only check (invariant 5) to catch a renamed or removed symbol that prose still
    names. Exemptions for dynamically-defined/optional symbols live in tools/doc-verify-allowlist.json
    ({"exempt": ["path::symbol", ...]})."""
    allow = set()
    ap = ROOT / "tools" / "doc-verify-allowlist.json"
    if ap.exists():
        try:
            allow = set(json.loads(ap.read_text(encoding="utf-8")).get("exempt", []))
        except (OSError, json.JSONDecodeError):
            allow = set()
    for target in _reference_scan_files():
        rel = target.relative_to(ROOT)
        for m in VERIFY_RE.finditer(target.read_text(encoding="utf-8")):
            spec = m.group(1)
            if spec in allow:
                continue
            path, _, symbol = spec.partition("::")
            if path.split("/")[0] not in KNOWN_ROOTS:
                problem(f"{rel}: verify marker `{spec}` path is not under a known repo root")
                continue
            resolved = ROOT / path
            if not resolved.exists():
                problem(f"{rel}: verify marker references missing path `{path}`")
                continue
            if symbol:
                if resolved.suffix != ".py":
                    problem(f"{rel}: verify marker `{spec}` names a symbol but `{path}` is not a .py file")
                    continue
                syms = _module_symbols(resolved)
                if syms is None:
                    problem(f"{rel}: verify marker `{spec}`: could not parse `{path}`")
                elif symbol not in syms:
                    problem(f"{rel}: verify marker `{spec}`: symbol `{symbol}` is not defined in `{path}`")


def check_tools_maintainer():
    """Invariant 50: tools-layer maintainer coverage (P52). Each designated high-value tools subtree
    (TOOLS_MAINTAINER_DIRS) must carry a MAINTAINER_README.md. The skills-only maintainer requirement
    (invariant 3) never reaches tools/, so the most security-sensitive code would otherwise have no
    maintainer doc and no guard coverage."""
    for d in TOOLS_MAINTAINER_DIRS:
        base = ROOT / d
        if not base.exists():
            continue
        if not (base / "MAINTAINER_README.md").exists():
            problem(f"{d}: missing MAINTAINER_README.md (required for a declared tools maintainer subtree)")


SOURCES_BLOCK_RE = re.compile(r"^```sources[ \t]*\n(.*?)^```[ \t]*$", re.DOTALL | re.MULTILINE)
SOURCE_MARKER_RE = re.compile(r"<!--\s*source:\s*([A-Za-z0-9][A-Za-z0-9_-]*)\s*-->")


def check_doc_source_registry():
    """Invariant 52: doc-declared source registration (P55). A maintainer/SKILL/doc file that declares
    the external sources its claims rest on - a fenced ```sources block holding a JSON array of
    {id, url, ...} objects, or an inline `<!-- source: id -->` marker tying one claim to one id -
    asserts those sources are TRACKED: every declared id must exist in
    canonical-sources/source-registry.json, and a declared url must equal the registry's url for that
    id. An unparseable block is a failure too (a silent skip would defeat the trigger). Fail-closed
    like invariant 23: citing a source in a doc forces the registry entry, so the currency system
    freshness-checks it from then on. The assist tool is `tools/source_sync.py` (reconcile generates
    the seed file; the human registers it via source_currency seed-sources). Enforcement is opt-in per
    doc - a file with no block and no marker is unaffected. Exemptions for illustrative/example ids
    live in tools/doc-source-allowlist.json ({"exempt": ["the-id", ...]}, each with a written reason
    in _comments)."""
    reg_path = ROOT / "canonical-sources" / "source-registry.json"
    try:
        reg = json.loads(reg_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        problem(f"doc-source-registry: source-registry.json unreadable: {exc}")
        return
    registry = {s.get("id"): s.get("url") for s in reg.get("sources", []) if s.get("id")}
    exempt = set()
    ap = ROOT / "tools" / "doc-source-allowlist.json"
    if ap.exists():
        try:
            exempt = set(json.loads(ap.read_text(encoding="utf-8")).get("exempt", []))
        except (OSError, json.JSONDecodeError):
            exempt = set()
    for target in _reference_scan_files():
        rel = target.relative_to(ROOT)
        text = target.read_text(encoding="utf-8")
        for m in SOURCES_BLOCK_RE.finditer(text):
            try:
                data = json.loads(m.group(1))
            except ValueError as exc:
                problem(f"{rel}: unparseable ```sources block ({exc}); fix the JSON - a broken "
                        f"declaration must not silently skip enforcement")
                continue
            if not isinstance(data, list):
                problem(f"{rel}: ```sources block must be a JSON array of source objects")
                continue
            for item in data:
                if not isinstance(item, dict) or not item.get("id"):
                    problem(f"{rel}: ```sources block entry missing an id")
                    continue
                sid = item["id"]
                if sid in exempt:
                    continue
                if sid not in registry:
                    problem(f"{rel}: declared source id '{sid}' is not in source-registry.json; "
                            f"run `python3 tools/source_sync.py reconcile` and seed the generated "
                            f"file via source_currency seed-sources (or exempt an illustrative id "
                            f"in tools/doc-source-allowlist.json with a reason)")
                elif item.get("url") and item["url"] != registry[sid]:
                    problem(f"{rel}: declared url for '{sid}' disagrees with the registry "
                            f"(declared {item['url']!r}, registry {registry[sid]!r}); reconcile "
                            f"whichever is stale (update-source for the registry side)")
        for mid in SOURCE_MARKER_RE.findall(text):
            if mid not in registry and mid not in exempt:
                problem(f"{rel}: source marker references id '{mid}' which is not in "
                        f"source-registry.json (seed it or exempt it with a reason)")


def check_connector_resolver_smoke():
    """Invariant 53: the connector resolver actually RUNS over the committed registry (P63).

    Invariants 18/23/41 validate connectors.json statically but never execute
    shared/connectors/connectors.py::resolve, which is how a malformed entry (google_drive_hub
    shipping without default_flag, the P63 F-SWEEP-4 defect) crashed --plan/--list/--json and the
    MCP get_connectors tool while the guard stayed green. This check dynamically imports the
    resolver and calls resolve({}) — the pure default-flag path — so any entry the resolver cannot
    process fails the build. Fail-closed: an exception of any kind is a problem, not an advisory."""
    tool = ROOT / "shared" / "connectors" / "connectors.py"
    if not tool.exists():
        problem("connector-resolver: shared/connectors/connectors.py is missing")
        return
    import importlib.util
    spec = importlib.util.spec_from_file_location("_connectors_smoke", tool)
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
        plan = mod.resolve({})
    except Exception as exc:  # noqa: BLE001
        problem(f"connector-resolver: resolve() failed over the committed registry: "
                f"{type(exc).__name__}: {exc}")
        return
    if not isinstance(plan, dict) or "active" not in plan:
        problem("connector-resolver: resolve({}) returned an unexpected shape "
                f"({type(plan).__name__}); expected a plan dict with an 'active' key")


def check_payload_loader_robustness():
    """Invariant 54: CLI filesystem touches on user-supplied paths stay guarded, whole-path (P63,
    widened P64).

    Layer 1 (P63): the named payload loaders keep a try/except in their body (the invariant-35
    sibling). Widened in P64 to cover the loaders C4/C5 guarded in tasks.py and doctemplates.py,
    plus a call-site rule for accounts.py (its guard lives at the caller).
    Layer 2 (P64, the RC5 fix): inside tools/finance.py and tools/obligations.py main/_main, NO
    argparse-derived value may reach exists()/read_text()/write_text()/open() outside a try —
    the P63 guard protected two function bodies while the AUDIT-F2 crash lived one line upstream
    in the dispatch (obligations --scan src.exists()); this layer guards the CLASS, not the line.
    Fail-closed."""
    import ast
    fs_calls = {"exists", "read_text", "write_text", "open", "is_file", "resolve"}
    body_targets = [(ROOT / "tools" / "finance.py", "_read_json"),
                    (ROOT / "tools" / "obligations.py", "_load_json"),
                    (ROOT / "tools" / "tasks.py", "load_register"),
                    (ROOT / "tools" / "doctemplates.py", "_probe_file"),
                    (ROOT / "tools" / "doctemplates.py", "_load_local_json")]
    trees = {}

    def _tree(path):
        if path not in trees:
            try:
                trees[path] = ast.parse(path.read_text(encoding="utf-8"))
            except (OSError, SyntaxError) as exc:
                problem(f"payload-loader: {path.name} unreadable/unparseable: {exc}")
                trees[path] = None
        return trees[path]

    for path, fname in body_targets:
        tree = _tree(path)
        if tree is None:
            continue
        fn = next((n for n in ast.walk(tree)
                   if isinstance(n, ast.FunctionDef) and n.name == fname), None)
        if fn is None:
            problem(f"payload-loader: {path.name} no longer defines {fname}() "
                    f"(a guarded CLI loader); restore it or update invariant 54")
            continue
        if not any(isinstance(n, ast.Try) for n in ast.walk(fn)):
            problem(f"payload-loader: {path.name}::{fname} lost its try/except guard; a bad "
                    f"path would raise a raw traceback again")
    # accounts.py guards at the call site: every _load_records_arg call must sit inside a try.
    acc = _tree(ROOT / "tools" / "accounts.py")
    if acc is not None:
        for fn in (n for n in ast.walk(acc)
                   if isinstance(n, ast.FunctionDef) and n.name == "main"):
            spans = [(t.lineno, t.end_lineno) for t in ast.walk(fn) if isinstance(t, ast.Try)]
            for node in ast.walk(fn):
                if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                        and node.func.id == "_load_records_arg"
                        and not any(s <= node.lineno <= e for s, e in spans)):
                    problem(f"payload-loader: accounts.py:{node.lineno} calls "
                            f"_load_records_arg() outside a try; a bad --records/--deals path "
                            f"would raise a raw traceback")
    # Layer 2: the whole-path scan over finance/obligations dispatch (main/_main).
    for path in (ROOT / "tools" / "finance.py", ROOT / "tools" / "obligations.py"):
        tree = _tree(path)
        if tree is None:
            continue
        for fn in (n for n in ast.walk(tree)
                   if isinstance(n, ast.FunctionDef) and n.name in ("main", "_main")):
            tainted = {"a", "args"}
            for node in ast.walk(fn):
                if isinstance(node, ast.Assign):
                    mentioned = {x.id for x in ast.walk(node.value) if isinstance(x, ast.Name)}
                    if mentioned & tainted:
                        tainted.update(t.id for t in node.targets if isinstance(t, ast.Name))
            spans = [(t.lineno, t.end_lineno) for t in ast.walk(fn) if isinstance(t, ast.Try)]

            def _in_try(ln):
                return any(s <= ln <= e for s, e in spans)

            for node in ast.walk(fn):
                if not isinstance(node, ast.Call) or _in_try(node.lineno):
                    continue
                if isinstance(node.func, ast.Attribute) and node.func.attr in fs_calls:
                    if {x.id for x in ast.walk(node.func.value)
                            if isinstance(x, ast.Name)} & tainted:
                        problem(f"payload-loader: {path.name}:{node.lineno} "
                                f".{node.func.attr}() on an argparse-derived value outside a "
                                f"try (the AUDIT-F2 whole-path rule); wrap it so a bad or "
                                f">255-byte path yields the clean envelope")
                elif isinstance(node.func, ast.Name) and node.func.id == "open":
                    if {x.id for arg in node.args for x in ast.walk(arg)
                            if isinstance(x, ast.Name)} & tainted:
                        problem(f"payload-loader: {path.name}:{node.lineno} open() on an "
                                f"argparse-derived value outside a try (the AUDIT-F2 "
                                f"whole-path rule)")


def check_surface_origin_completeness():
    """Invariant 55: every compute-job origin is claimed by the cross-modality surface model (P64).

    tools/handoff/queue.py::ALLOWED_ORIGINS and the origin enum in
    shared/schemas/compute-job.json are the independent oracle for "where work comes from";
    shared/cross-modality/transitions.json is the model of "where Creator OS runs". AUDIT-F1
    (the cowork origin shipping in P60 while the surface model went two days without a Cowork
    row) happened because nothing reconciled them. This check asserts (a) the two enums are
    identical, and (b) every enum value is claimed by at least one surface's `origins` list or
    the documented `_residual_origin_note`. Fail-closed."""
    import ast
    qp = ROOT / "tools" / "handoff" / "queue.py"
    if not qp.exists():
        problem("origin-completeness: tools/handoff/queue.py is missing")
        return
    try:
        tree = ast.parse(qp.read_text(encoding="utf-8"))
    except SyntaxError as exc:
        problem(f"origin-completeness: queue.py failed to parse: {exc}")
        return
    enum_code = None
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for tgt in node.targets:
                if isinstance(tgt, ast.Name) and tgt.id == "ALLOWED_ORIGINS":
                    try:
                        enum_code = tuple(ast.literal_eval(node.value))
                    except (ValueError, SyntaxError):
                        pass
    if enum_code is None:
        problem("origin-completeness: queue.py no longer defines a literal ALLOWED_ORIGINS tuple")
        return
    sp = ROOT / "shared" / "schemas" / "compute-job.json"
    try:
        schema = json.loads(sp.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        problem(f"origin-completeness: compute-job.json unreadable: {exc}")
        return
    enum_schema = ((((schema.get("$defs") or {}).get("job") or {}).get("properties") or {})
                   .get("origin") or {}).get("enum") or []
    if set(enum_code) != set(enum_schema):
        problem(f"origin-completeness: queue.py ALLOWED_ORIGINS {sorted(enum_code)} != "
                f"compute-job.json origin enum {sorted(enum_schema)}")
    tp = ROOT / "shared" / "cross-modality" / "transitions.json"
    try:
        data = json.loads(tp.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        problem(f"origin-completeness: transitions.json unreadable: {exc}")
        return
    claimed = set()
    for rec in (data.get("surfaces") or {}).values():
        claimed.update(rec.get("origins") or [])
    residual_note = data.get("_residual_origin_note") or ""
    for origin in enum_code:
        if origin in claimed:
            continue
        if f"'{origin}'" in residual_note:
            continue
        problem(f"origin-completeness: origin {origin!r} is in ALLOWED_ORIGINS but no "
                f"transitions surface claims it (add it to a surface's 'origins' list or, for a "
                f"deliberate residual, to _residual_origin_note)")
    unknown = claimed - set(enum_code)
    if unknown:
        problem(f"origin-completeness: transitions surfaces claim origins {sorted(unknown)} "
                f"that are not in ALLOWED_ORIGINS")


def check_invariant_catalog():
    """Invariant 36: invariant-catalog integrity (the keystone, P47). Parses this file and asserts
    (a) every check_* function registered in main() carries an 'Invariant N' docstring label,
    (b) no invariant number is claimed by two checks (catches the historical double-'Invariant 22'),
    (c) the label set is contiguous from 1 to the highest label except for MERGED_INVARIANTS,
    (d) the module header 'Invariants enforced:' enumeration documents exactly the enforced numbers
    plus the merged ones (catches the stale 'header lists 1-23 while code implements more' drift),
    and (e) every check_* function that CARRIES an 'Invariant N' label is actually called in
    main() — without (e) the top-numbered invariant could be silently dropped from main() while
    its dead docstring keeps every count reading correct (the P65 keystone finding).
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

    registered_set = set(registered)
    for fn, nums in sorted(labels_by_func.items()):
        if nums and fn not in registered_set:
            problem(f"invariant-catalog: {fn}() carries 'Invariant {', '.join(map(str, nums))}' "
                    f"but is never called in main(); a labeled check that is not registered is a "
                    f"silently disabled invariant (delete the function or register it)")

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
    check_doc_count_truth()
    check_doc_symbol_refs()
    check_tools_maintainer()
    check_doc_freshness()
    check_doc_source_registry()
    check_connector_resolver_smoke()
    check_payload_loader_robustness()
    check_surface_origin_completeness()
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
