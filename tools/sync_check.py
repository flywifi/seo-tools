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
      templates are committed. Runs `git ls-files` read-only; skips cleanly outside a git repo.
"""
import json
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
KNOWN_ROOTS = ("shared", "protocols", "skills", "pipeline", "tools", "docs", ".claude")


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


LOCAL_FILE_RE = re.compile(r"\.local(\.|$)")


def check_local_privacy():
    """Invariant 19: no personal *.local.* file is tracked by git.

    The creator's real context (contract records, obligation register, deal-playbook,
    channel/voice profile, credentials, config overrides) lives in gitignored *.local.* files
    that git pull never touches. This asserts none of them ever entered git, so a stray
    `git add -A` cannot leak or commit personal data. Read-only; skips cleanly if git is
    unavailable or this is not a git checkout.
    """
    try:
        out = subprocess.run(
            ["git", "ls-files"], cwd=str(ROOT), capture_output=True, text=True, timeout=30
        )
    except (OSError, subprocess.SubprocessError):
        return  # git unavailable; cannot check, do not fail
    if out.returncode != 0:
        return  # not a git repo; skip cleanly
    for line in out.stdout.splitlines():
        path = line.strip()
        if not path:
            continue
        basename = path.rsplit("/", 1)[-1]
        if LOCAL_FILE_RE.search(basename):
            problem(
                f"privacy: personal local file is tracked by git and must be gitignored: {path}"
            )


def main():
    manifest = load_manifest()
    check_canonical(manifest)
    check_skills()
    check_formatting()
    check_references()
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
    if PROBLEMS:
        print(f"DRIFT GUARD: {len(PROBLEMS)} problem(s) found\n")
        for item in PROBLEMS:
            print(f"  - {item}")
        return 1
    print("DRIFT GUARD: clean (all invariants hold)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
