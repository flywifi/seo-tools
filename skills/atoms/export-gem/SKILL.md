---
name: export-gem
atom: true
standalone: true
description: "Packages Creator OS knowledge files and system instruction for a Google Gemini Gem. Respects Gem constraints: 10 knowledge file max, approximately 82% instruction adherence. Do NOT use for GPT export (use export-gpt) or Claude Projects (see implementation/claude/project/)."
load:
  - shared/brand-engine.md
  - shared/adaptation-engine.md
  - shared/voice-engine.md
  - protocols/formatting-metadata.md
---

# export-gem

Package Creator OS engines, protocols, and spoke instructions into a Google Gemini Gem — a custom
Gemini persona with uploaded knowledge files and a system instruction.

## Purpose

The creator maintains parallel deployments of Creator OS across platforms. This atom handles the
Gemini Gem target: it selects the most impactful knowledge files (constrained to Gemini's 10-file
limit), merges and prioritizes engine content, generates a system instruction (whose REQUIRED
first line is the packaging stamp `Packaging version: <VERSION> (packaged <YYYY-MM-DD>)`,
read from the repo `VERSION` file at export time; re-sync steps in `docs/TRANSITIONS.md`)
that works within
Gem's approximately 82% instruction adherence rate, and outputs the package ready for upload. It
loads `shared/brand-engine.md` and `shared/voice-engine.md` to ensure brand and voice fidelity
survive the export.

## When to invoke

- "Package Creator OS for Gemini."
- "Create a Gem version of my system."
- "Export my skills to a Gemini Gem."
- "Update my Gem with the latest engine changes."
- "Build a Gem focused on SEO and content planning."
- Invoke directly or from the implementation pipeline when updating the Gemini deployment.

## Do NOT use for

- GPT export — Custom GPTs have different constraints (8K instruction limit, Actions, Code
  Interpreter). Use `export-gpt`.
- Claude Desktop or Claude Projects — these use native skill loading, not a packaged export.
  See `implementation/claude/project/`.
- Exporting individual atoms — Gems are whole-system packages, not per-atom exports.

## Inputs

```json
{
  "gem_name": "string — display name for the Gem (e.g., 'Creator OS — Content Studio')",
  "focus_spokes": ["string — spoke names to prioritize"] | "all"
}
```

- `gem_name`: required. The name that will appear in the Gemini Gem listing.
- `focus_spokes`: optional, defaults to `"all"`. When set to a list of spoke names, the atom
  prioritizes those spokes' engines and protocols in the knowledge file selection. Useful for
  creating focused Gems (e.g., an SEO-only Gem or a CRM-only Gem) that stay within the 10-file
  limit without sacrificing depth in the focus area.

## Procedure

### Step 1: inventory available knowledge

Scan the repo for exportable files:
- `shared/*.md` — all canonical engines.
- `protocols/*.md` — all governance protocols.
- `skills/<spoke>/SKILL.md` — spoke instructions for focused spokes.
- `canonical-sources/` — reference data files relevant to focused spokes.

Build a ranked list by priority:
1. `shared/brand-engine.md` and `shared/voice-engine.md` — always included (non-negotiable for
   brand fidelity).
2. `protocols/no-fabrication.md` and `protocols/formatting-metadata.md` — always included
   (governance floor).
3. Engines loaded by focused spokes (from their `load:` frontmatter).
4. SKILL.md files for focused spokes.
5. Remaining engines and protocols, ranked by cross-spoke usage count.
6. Canonical source files, if space permits.

### Step 2: merge and fit within 10-file limit

Gemini Gems accept a maximum of 10 knowledge files. If the ranked list exceeds 10:
- Merge related files: combine all protocols into a single `protocols-combined.md`.
- Merge secondary engines into a `engines-supplementary.md`.
- Keep high-priority files (brand-engine, voice-engine, focused spoke SKILL.md) as standalone
  files for better retrieval.
- Record any files excluded from the package in `warnings`.

Track file sizes. While Gems do not enforce a strict per-file size limit, very large files
(> 100KB) may reduce retrieval quality. If a file exceeds 100KB, note it in `warnings`.

### Step 3: generate system instruction

Write the Gem's system instruction — the persistent prompt that governs behavior. Design for
Gemini's approximately 82% instruction adherence:
- Front-load the most critical rules (brand identity, no fabrication, voice rules).
- Use short, imperative sentences. Avoid nested conditionals.
- Repeat the 3 to 5 most important rules at the end of the instruction ("reminder block") to
  increase adherence.
- Reference knowledge files by name so Gemini retrieves them contextually.
- Include a "you are" identity paragraph drawn from `shared/brand-engine.md`.
- Include voice rules from `shared/voice-engine.md` (anti-AI patterns, two voice modes).
- Include the no-fabrication rule in a single imperative sentence.

Write the system instruction to a file at `implementation/gemini/gems/<gem_name>/system-instruction.md`.

### Step 4: assemble output manifest

List all knowledge files with paths and sizes. Verify the count is <= 10. Write the manifest
to `implementation/gemini/gems/<gem_name>/manifest.json`.

### Step 5: emit warnings

Flag any issues:
- Files excluded due to the 10-file limit.
- Files exceeding 100KB.
- Spokes requested in `focus_spokes` that do not exist.
- Instruction adherence risk for complex rules (e.g., conditional formatting that Gemini may
  not follow reliably).

## Output

```json
{
  "gem_name": "Creator OS — Content Studio",
  "system_instruction_path": "implementation/gemini/gems/creator-os-content-studio/system-instruction.md",
  "knowledge_files": [
    { "name": "brand-engine.md", "path": "shared/brand-engine.md", "size_kb": 4.2 },
    { "name": "voice-engine.md", "path": "shared/voice-engine.md", "size_kb": 6.8 },
    { "name": "protocols-combined.md", "path": "implementation/gemini/gems/creator-os-content-studio/protocols-combined.md", "size_kb": 12.1 }
  ],
  "total_files": 8,
  "system_instruction_length_chars": 3200,
  "warnings": [
    "seo-intelligence-engine.md exceeds 100KB; retrieval quality may be reduced",
    "canonical-sources/ files excluded due to 10-file limit"
  ],
  "retrieval_gaps": []
}
```

- `knowledge_files`: array of objects, one per file in the Gem package. Maximum 10.
- `total_files`: count of knowledge files. Must be <= 10.
- `system_instruction_length_chars`: character count of the system instruction.
- `warnings`: array of strings noting any constraints, exclusions, or adherence risks.

## Fabrication rules

Inherited from `protocols/no-fabrication.md`:
- Do not invent file sizes or counts. Measure them from the actual files.
- Do not claim a file is included if it was excluded due to constraints.
- If a requested spoke does not exist, report it in `warnings` — do not fabricate a SKILL.md.

## Cross-modality
Inherits its calling spoke's class (the calling spoke's class); see `shared/cross-modality-engine.md`. An atom carries no independent surface wiring and runs wherever the spoke that composes it runs.
