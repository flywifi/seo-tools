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


def problem(msg):
    PROBLEMS.append(msg)


def load_manifest():
    path = ROOT / "tools" / "sync_manifest.json"
    if not path.exists():
        problem("missing tools/sync_manifest.json")
        return {"engines": [], "protocols": []}
    return json.loads(path.read_text(encoding="utf-8"))


def check_canonical(manifest):
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
    "pipeline/user-context/channel-context.json",
    "pipeline/user-context/content-calendar.json",
    "pipeline/user-context/creator-profile.template.json",
    "pipeline/user-context/deal-playbook.template.json",
    "pipeline/user-context/obligation-register.template.json",
    "pipeline/user-context/task-register.template.json",
    "pipeline/user-context/recurrence-rules.template.json",
    "pipeline/user-context/shipments.template.json",
    "pipeline/user-context/payment-schedule.template.json",
    "pipeline/user-context/rate-card.template.json",
    "pipeline/user-context/setup-context.json",
    "pipeline/user-context/voice-profile.json",
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
    """Invariant 22: construction dictionary integrity (P34).

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
    if PROBLEMS:
        print(f"DRIFT GUARD: {len(PROBLEMS)} problem(s) found\n")
        for item in PROBLEMS:
            print(f"  - {item}")
        return 1
    print("DRIFT GUARD: clean (all invariants hold)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
