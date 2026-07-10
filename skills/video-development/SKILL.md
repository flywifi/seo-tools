---
name: video-development
description: "develop one video concept into a full production package: hook, title options, outline, thumbnail concept, SEO-aware description, and at least three short-form clip extractions. Use when the user has a concept and wants to build it out. Do NOT use to generate fresh ideas (use content-strategy) or to write the full word-for-word script (use script-writer when present)."
---

# video-development

Develops a single concept into a production package. Every concept yields at least 3 standalone
short-form clips alongside the long-form outline.

## When to use this skill
Triggers: "develop this idea," "build out this video," "give me the title, hook, and outline." Do NOT
generate new ideas (use content-strategy) or write the full spoken script.

## Inputs
A concept (from content-strategy or the user), the target persona, and platform targets.

## Core procedure
Follow `shared/method.md`; compose atoms via `workflow.json`.
1. Build the keyword cluster (keyword-cluster) for the title and description.
2. Write the hook (hook-write) that lands the promise in the first 15 to 30 seconds.
3. Generate title options (title-generate), human readable first, primary keyword front-loaded.
4. Design the thumbnail concept (thumbnail-concept), aligned to the title.
5. Extract at least 3 standalone short-form clips (short-extract), each with its own hook.
6. Assemble the outline (intro and hook, problem and before, process and key decisions, reveal and
   payoff, recap, outro and CTA) and an SEO-aware description.
7. Gate the package (govern-artifact).

## Output contract
A production package: hook, title options, outline sections, thumbnail concept, SEO description (1 to
2 primary keywords in the title and the opening 200 characters), and 3 or more short-form clips. Obeys
`protocols/formatting-metadata.md`.

## Engines and protocols loaded
`shared/brand-engine.md`, `shared/audience-engine.md`, `shared/platform-engine.md`,
`shared/adaptation-engine.md`, `shared/web-intel-engine.md`. Protocols: `protocols/research-citation.md`,
`protocols/no-fabrication.md`, `protocols/formatting-metadata.md`, `protocols/quality-gates.md`.

## Atoms used
keyword-cluster, hook-write, title-generate, thumbnail-concept, short-extract, govern-artifact. A user
can call hook-write, title-generate, or short-extract directly.

## Standalone usability
Produces a complete production package even when shortform-repurposing or script-writer is not
available; the clip list is usable on its own.

## Failure modes
- Returning fewer than 3 short-form clips.
- Clips that depend on the full video for context.
- Overpromising titles or thumbnails the video does not deliver.

## Cross-modality
Class: C.
Runs on: Claude Desktop/Code (native, MCP + the tool module); claude.ai via a hosted remote-MCP connector; Custom GPT / Gemini only when the tool is hosted behind a remote MCP or an Action; Gems: no.
Mechanism: Core package build is pure reasoning over the engines plus scoop-cache lookups (platform specs, keyword library); the footage_breakdown lane runs deterministic media compute in tools/videoedit/mediaprobe.py via the silence_scan and scene_scan MCP tools (ffmpeg silencedetect / PyAV RMS; PySceneDetect / ffmpeg scdet).
Fallback: Without a local runtime or hosted MCP seam, silence-scan and scene-scan degrade to the transcript gap/chapter-suggestion floor and the rest of the package is built by reasoning over supplied transcript, probe data, and specs; media facts that cannot be probed are flagged unverified, never fabricated.
See `shared/cross-modality-engine.md`.
