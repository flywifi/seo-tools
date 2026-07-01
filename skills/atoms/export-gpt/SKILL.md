---
name: export-gpt
atom: true
standalone: true
description: "Packages Creator OS for an OpenAI Custom GPT. Respects GPT constraints: 8K character instruction limit, Actions via OpenAPI, Code Interpreter available. Do NOT use for Gemini export (use export-gem) or Claude Desktop/Projects (see implementation/claude/)."
load:
  - shared/brand-engine.md
  - shared/adaptation-engine.md
  - shared/voice-engine.md
  - protocols/formatting-metadata.md
---

# export-gpt

Package Creator OS engines, protocols, and spoke instructions for an OpenAI Custom GPT — a
ChatGPT persona with an instruction field, uploaded knowledge files, optional Actions (OpenAPI
function calling), and optional Code Interpreter access.

## Purpose

The creator maintains parallel deployments of Creator OS across platforms. This atom handles the
Custom GPT target: it compresses the most critical system rules into the 8K-character instruction
limit, selects knowledge files for upload, optionally generates an Actions schema (OpenAPI YAML)
for external tool integration, and outputs the package ready for configuration in the GPT Builder.
It loads `shared/brand-engine.md` and `shared/voice-engine.md` to ensure brand and voice fidelity
survive the compression.

## When to invoke

- "Package Creator OS for ChatGPT."
- "Create a Custom GPT version of my system."
- "Export my skills to a GPT."
- "Update my GPT with the latest engine changes."
- "Build a GPT focused on video development and SEO."
- Invoke directly or from the implementation pipeline when updating the GPT deployment.

## Do NOT use for

- Gemini Gem export — Gems have different constraints (10-file limit, system instruction format).
  Use `export-gem`.
- Claude Desktop or Claude Projects — these use native skill loading. See
  `implementation/claude/`.
- OpenAI API function calling (non-GPT) — see `implementation/gpt/api/` for function YAML files.

## Inputs

```json
{
  "gpt_name": "string — display name for the Custom GPT (e.g., 'Creator OS')",
  "focus_spokes": ["string — spoke names to prioritize"] | "all",
  "include_actions": true
}
```

- `gpt_name`: required. The name for the Custom GPT.
- `focus_spokes`: optional, defaults to `"all"`. Prioritizes specific spokes in the instruction
  and knowledge file selection.
- `include_actions`: optional, defaults to false. When true, generates an OpenAPI schema for
  Actions that connect the GPT to external services (e.g., YouTube Data API, Google Analytics).

## Procedure

### Step 1: inventory and prioritize

Scan the repo for exportable content (same inventory as export-gem Step 1). Build a ranked list:
1. `shared/brand-engine.md` identity and voice sections — must fit in the instruction.
2. `protocols/no-fabrication.md` core rule — must fit in the instruction.
3. `shared/voice-engine.md` anti-AI patterns and voice modes — must fit in the instruction.
4. `protocols/formatting-metadata.md` key rules — must fit in the instruction.
5. Focused spoke SKILL.md files — uploaded as knowledge files.
6. Remaining engines — uploaded as knowledge files.
7. Canonical source files — uploaded as knowledge files if relevant.

### Step 2: compress into 8K instruction

The Custom GPT instruction field has an 8,000-character limit. This is the system prompt that
governs every response.

Strategy:
- Write a dense, imperative-style instruction (not prose paragraphs).
- Open with a "you are" identity block from `shared/brand-engine.md` (approximately 500 characters).
- Include the no-fabrication rule as a single sentence (approximately 100 characters).
- Include the top 10 to 15 anti-AI patterns from `shared/voice-engine.md` (approximately 800
  characters).
- Include voice mode rules (planning vs. published) in compressed form (approximately 600
  characters).
- Include formatting rules from `protocols/formatting-metadata.md` (approximately 300 characters).
- Include spoke-specific instructions for focused spokes (approximately 200 to 400 characters each).
- Reserve approximately 500 characters for a closing "reminders" block that repeats the 5 most
  critical rules.

Track character count throughout. If the instruction exceeds 8,000 characters:
- Move lower-priority spoke instructions to a knowledge file.
- Compress voice rules to the top 5 anti-AI patterns.
- Note truncations in `warnings`.

Write the instruction to `implementation/gpt/web/<gpt_name>/instruction.txt`.

### Step 3: select knowledge files

Custom GPTs support up to 20 knowledge files. Select and prepare:
- Full engine files that did not fit in the instruction.
- SKILL.md files for focused spokes.
- Protocol files.
- Canonical source files relevant to focused spokes.

Write knowledge files to `implementation/gpt/web/<gpt_name>/knowledge/`.

### Step 4: generate Actions schema (if requested)

If `include_actions` is true:
- Generate an OpenAPI 3.1 YAML schema for relevant external APIs.
- Include only APIs that the focused spokes actually use.
- Write to `implementation/gpt/web/<gpt_name>/actions-schema.yaml`.
- Note: Actions require the user to configure authentication separately in the GPT Builder.

### Step 5: emit output and warnings

Flag any issues:
- Instruction text exceeding 8K characters (before or after compression).
- Content truncated or moved to knowledge files.
- Spokes requested in `focus_spokes` that do not exist.
- Actions schema generated for APIs that require authentication the user must configure.

## Output

```json
{
  "gpt_name": "Creator OS",
  "instruction_text": "compressed system instruction text",
  "instruction_chars": 7842,
  "instruction_path": "implementation/gpt/web/creator-os/instruction.txt",
  "knowledge_files": [
    { "name": "brand-engine.md", "path": "shared/brand-engine.md" },
    { "name": "seo-intelligence-engine.md", "path": "shared/seo-intelligence-engine.md" }
  ],
  "knowledge_file_count": 12,
  "actions_schema_path": "implementation/gpt/web/creator-os/actions-schema.yaml",
  "warnings": [
    "voice-engine anti-AI patterns compressed from 25 to 15 to fit instruction limit",
    "pipeline-engine.md excluded from instruction; available as knowledge file"
  ],
  "retrieval_gaps": []
}
```

- `instruction_text`: the full instruction text (included in output for review).
- `instruction_chars`: character count. Must be <= 8000.
- `knowledge_files`: array of objects with name and source path.
- `actions_schema_path`: path to the OpenAPI YAML, or null if `include_actions` was false.
- `warnings`: array of strings noting truncations, exclusions, or configuration requirements.

## Fabrication rules

Inherited from `protocols/no-fabrication.md`:
- Do not invent character counts. Measure from the actual instruction text.
- Do not claim content is in the instruction if it was moved to a knowledge file.
- Do not fabricate API endpoints in the Actions schema. Only include real, documented APIs.
- If a requested spoke does not exist, report it in `warnings` — do not fabricate a SKILL.md.
