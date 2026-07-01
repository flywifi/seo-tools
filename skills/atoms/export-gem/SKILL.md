---
name: export-gem
atom: true
description: "Packages Creator OS spokes into a Google Gemini Gem — produces a system instruction and up to 10 knowledge files respecting Gem platform constraints. Do NOT use for OpenAI Custom GPT packaging (use export-gpt), Claude skill development (work directly in the repo), or runtime content generation (use the appropriate content spoke)."
load:
  - shared/brand-engine.md
  - shared/adaptation-engine.md
---

# export-gem

Package selected Creator OS spokes into a Google Gemini Gem by producing a system instruction
document and a set of knowledge files that respect Gem platform constraints.

## Purpose

The creator may want to deploy a subset of Creator OS capabilities as a standalone Gemini Gem —
for quick access on mobile, for sharing with a collaborator, or for contexts where Claude is not
available. This atom reads the brand voice and identity from `shared/brand-engine.md`, applies
platform adaptation rules from `shared/adaptation-engine.md`, and produces the two artifacts a Gem
requires: a system instruction and a set of knowledge files. It enforces the Gem constraint of a
maximum of 10 knowledge files.

## When to invoke

- "Package my content skills as a Gemini Gem."
- "Create a Gem for my SEO workflow."
- "Export Creator OS to Gemini."
- "Build a Gem with just the keyword and title atoms."
- "I want a Gem version of my content pipeline."
- Invoke directly or from the packaging spoke when the target platform is Gemini.

## Do NOT use for

- OpenAI Custom GPT packaging. Use `export-gpt`.
- Claude skill authoring or editing. Work directly in the repo.
- Runtime content generation (titles, captions, scripts). Use the appropriate content spoke.
- Exporting raw data or analytics. Use `data-query` or the relevant analytics spoke.

## Inputs

```json
{
  "gem_name": "string — display name for the Gem (e.g., 'Creator Content Assistant')",
  "focus_spokes": ["string — spoke names to include"] 
}
```

- `gem_name`: required. The name that will appear in the Gemini Gem directory. Keep it under 50
  characters.
- `focus_spokes`: required. Array of spoke names to include, or the string `"all"` to include
  every spoke. Each spoke named must exist under `skills/`. When `"all"` is specified, include
  all spokes listed in the creator-core hub's downstream registry.

## Procedure

### Step 1: resolve spokes and collect source material

For each spoke in `focus_spokes`:
- Verify the spoke exists under `skills/`.
- Read its `SKILL.md` for capability description, trigger phrases, and procedure.
- Read its `workflow.json` to identify which atoms it composes.
- Collect the atoms' `SKILL.md` files for their input/output contracts.

If `focus_spokes` is `"all"`, enumerate all spokes from the creator-core hub's downstream list.

If any named spoke does not exist, add it to `warnings` and skip it.

### Step 2: read brand and adaptation context

Read `shared/brand-engine.md` to extract:
- Brand voice attributes (warm, knowledgeable, approachable, slightly moody).
- Content pillars and niche definition.
- Tone and language rules.

Read `shared/adaptation-engine.md` to extract:
- Gemini-specific adaptation rules (token limits, formatting conventions, instruction style).
- Platform constraints for Gems.

### Step 3: compose the system instruction

Build a single system instruction document that:
- Opens with the brand identity and voice definition.
- Lists the capabilities the Gem provides (one section per included spoke).
- Includes routing logic: how to classify a request and dispatch to the right capability.
- Embeds key protocols inline (no-fabrication rules, formatting rules) since the Gem cannot
  reference external files.
- Stays within Gemini's system instruction token limits as specified by the adaptation engine.

Write the system instruction to `implementation/gemini/gems/<gem_name>/system_instruction.md`.

### Step 4: compose knowledge files

Package supporting reference material into knowledge files. Each knowledge file is a single
document covering one domain:
- Brand voice reference (from brand-engine).
- Audience personas (from audience-engine, if relevant to included spokes).
- Platform specs (from platform-engine, if relevant).
- One file per content pillar or capability cluster as needed.

Enforce the Gem constraint: **maximum 10 knowledge files**. If the material exceeds 10 files:
- Merge related domains into combined files (e.g., combine all platform specs into one file).
- Prioritize files by relevance to the included spokes.
- Add a warning listing what was merged or excluded.

Write knowledge files to `implementation/gemini/gems/<gem_name>/knowledge/`.

### Step 5: validate and report

- Count total files (system instruction + knowledge files). Confirm total knowledge files are 10
  or fewer.
- Verify the system instruction does not reference files the Gem cannot access.
- Check that brand voice is consistently applied throughout.
- List any spokes that were requested but excluded, and why.

## Output

```json
{
  "gem_name": "Creator Content Assistant",
  "system_instruction_path": "implementation/gemini/gems/creator-content-assistant/system_instruction.md",
  "knowledge_files": [
    "implementation/gemini/gems/creator-content-assistant/knowledge/brand-voice.md",
    "implementation/gemini/gems/creator-content-assistant/knowledge/audience-personas.md"
  ],
  "total_files": 3,
  "spokes_included": ["keyword-research", "title-generate", "caption-write"],
  "spokes_excluded": [],
  "warnings": [],
  "retrieval_gaps": []
}
```

- `system_instruction_path`: path to the generated system instruction file, relative to repo root.
- `knowledge_files`: array of paths to the generated knowledge files.
- `total_files`: system instruction (1) plus number of knowledge files. Knowledge files must not
  exceed 10.
- `spokes_included`: spokes that were successfully packaged.
- `spokes_excluded`: spokes that were requested but could not be included (with reasons in
  `warnings`).
- `warnings`: array of strings describing any constraints hit — merges, exclusions, or size limits.
- `retrieval_gaps`: notes on anything that could not be resolved or packaged.

## Fabrication rules

- Never invent spoke names, capabilities, or platform constraints.
- The system instruction must accurately reflect what the included spokes can do — do not promise
  capabilities that were not packaged into the Gem.
- Do not fabricate Gemini platform limits. Use the constraints documented in
  `shared/adaptation-engine.md`.
- If a spoke's procedure references data or tools the Gem cannot access (MCP servers, local files),
  note the limitation in `warnings` rather than silently omitting the capability.
