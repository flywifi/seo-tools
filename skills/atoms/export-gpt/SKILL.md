---
name: export-gpt
atom: true
description: "Packages Creator OS spokes into an OpenAI Custom GPT — produces instruction text (within the 8K character limit), knowledge files, and optional actions schema. Do NOT use for Gemini Gem packaging (use export-gem), Claude skill development (work directly in the repo), or runtime content generation (use the appropriate content spoke)."
load:
  - shared/brand-engine.md
  - shared/adaptation-engine.md
---

# export-gpt

Package selected Creator OS spokes into an OpenAI Custom GPT by producing instruction text,
knowledge files, and an optional actions schema that respect GPT platform constraints.

## Purpose

The creator may want to deploy a subset of Creator OS capabilities as a standalone Custom GPT —
for sharing with collaborators, for use in the ChatGPT mobile app, or for contexts where Claude is
not available. This atom reads the brand voice and identity from `shared/brand-engine.md`, applies
platform adaptation rules from `shared/adaptation-engine.md`, and produces the artifacts a Custom
GPT requires: instruction text (capped at 8,000 characters), knowledge files, and optionally an
OpenAPI actions schema. It enforces the 8K character instruction limit strictly.

## When to invoke

- "Package my content skills as a Custom GPT."
- "Create a GPT for my SEO workflow."
- "Export Creator OS to ChatGPT."
- "Build a GPT with just the keyword and title atoms."
- "I want a GPT version of my content pipeline with actions."
- Invoke directly or from the packaging spoke when the target platform is OpenAI.

## Do NOT use for

- Gemini Gem packaging. Use `export-gem`.
- Claude skill authoring or editing. Work directly in the repo.
- Runtime content generation (titles, captions, scripts). Use the appropriate content spoke.
- Exporting raw data or analytics. Use `data-query` or the relevant analytics spoke.

## Inputs

```json
{
  "gpt_name": "string — display name for the Custom GPT (e.g., 'Creator Content Engine')",
  "focus_spokes": ["string — spoke names to include"],
  "include_actions": false
}
```

- `gpt_name`: required. The name that will appear in the GPT Store. Keep it under 50 characters.
- `focus_spokes`: required. Array of spoke names to include, or the string `"all"` to include
  every spoke. Each spoke named must exist under `skills/`. When `"all"` is specified, include
  all spokes listed in the creator-core hub's downstream registry.
- `include_actions`: optional, defaults to `false`. If `true`, generate an OpenAPI actions schema
  for any spokes that expose API-callable operations (e.g., data-query, pipeline operations).

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
- OpenAI Custom GPT-specific adaptation rules (instruction character limit, knowledge file
  conventions, actions schema format).
- Platform constraints for Custom GPTs.

### Step 3: compose the instruction text

Build the instruction text as a single string that:
- Opens with the brand identity and voice definition.
- Lists the capabilities the GPT provides (one section per included spoke).
- Includes routing logic: how to classify a request and dispatch to the right capability.
- Embeds key protocols inline (no-fabrication rules, formatting rules) since the GPT cannot
  reference external protocol files.
- References knowledge files by name where the GPT can retrieve them.

**Enforce the 8,000 character limit strictly.** If the instruction text exceeds 8,000 characters:
- Prioritize brand voice and routing logic (always included).
- Compress spoke descriptions to essential trigger phrases and core procedure steps.
- Move detailed procedures and reference data into knowledge files.
- If still over 8K after compression, reduce the number of included spokes and add the excluded
  ones to `warnings`.
- Track the final character count in `instruction_chars`.

Write the instruction text to `implementation/gpt/customs/<gpt_name>/instructions.md`.

### Step 4: compose knowledge files

Package supporting reference material into knowledge files:
- Brand voice reference (from brand-engine).
- Detailed spoke procedures that were compressed out of the instruction text.
- Audience personas (from audience-engine, if relevant).
- Platform specs (from platform-engine, if relevant).
- Protocol summaries (no-fabrication, formatting rules).

OpenAI allows up to 20 knowledge files per GPT. Organize logically — one file per domain or
capability cluster.

Write knowledge files to `implementation/gpt/customs/<gpt_name>/knowledge/`.

### Step 5: generate actions schema (if requested)

If `include_actions` is `true`:
- Identify which included spokes expose operations suitable for API actions.
- Generate an OpenAPI 3.1 schema defining each action's endpoint, parameters, and response format.
- Write the schema to `implementation/gpt/customs/<gpt_name>/actions_schema.json`.

If `include_actions` is `false`, set `actions_schema_path` to null and skip this step.

### Step 6: validate and report

- Verify `instruction_chars` is 8,000 or fewer. If not, the atom has failed — do not emit.
- Confirm all knowledge file references in the instruction text match actual knowledge files.
- Check that brand voice is consistently applied throughout.
- List any spokes that were requested but excluded, and why.

## Output

```json
{
  "gpt_name": "Creator Content Engine",
  "instruction_text": "You are the Creator Content Engine, a warm and knowledgeable assistant...",
  "instruction_chars": 7842,
  "knowledge_files": [
    "implementation/gpt/customs/creator-content-engine/knowledge/brand-voice.md",
    "implementation/gpt/customs/creator-content-engine/knowledge/seo-procedures.md"
  ],
  "actions_schema_path": null,
  "spokes_included": ["keyword-research", "title-generate", "caption-write"],
  "spokes_excluded": [],
  "warnings": [],
  "retrieval_gaps": []
}
```

- `instruction_text`: the full instruction string ready to paste into the Custom GPT builder.
- `instruction_chars`: character count of `instruction_text`. Must be 8,000 or fewer.
- `knowledge_files`: array of paths to the generated knowledge files.
- `actions_schema_path`: path to the OpenAPI actions schema, or null if `include_actions` is
  `false`.
- `spokes_included`: spokes that were successfully packaged.
- `spokes_excluded`: spokes that were requested but could not be included (with reasons in
  `warnings`).
- `warnings`: array of strings describing any constraints hit — character limit compression,
  exclusions, or capability limitations.
- `retrieval_gaps`: notes on anything that could not be resolved or packaged.

## Fabrication rules

- Never invent spoke names, capabilities, or platform constraints.
- The instruction text must accurately reflect what the included spokes can do — do not promise
  capabilities that were not packaged into the GPT.
- Do not fabricate OpenAI platform limits. Use the constraints documented in
  `shared/adaptation-engine.md`.
- The 8,000 character instruction limit is hard — never emit an instruction that exceeds it.
- If a spoke's procedure references data or tools the GPT cannot access (MCP servers, local files),
  note the limitation in `warnings` rather than silently omitting the capability.
