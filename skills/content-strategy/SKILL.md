---
name: content-strategy
description: generate content ideas, seasonal-aware idea clusters, pillar-aligned video concepts, and competitive positioning for the channel. Use when the user wants ideas, a content plan, what to make next, or how to position against a competitor. Do NOT use to develop one concept into a production package (use video-development) or to build a downloadable calendar file (use document-studio).
---

# content-strategy

The primary idea-generation spoke. Produces idea clusters, not single ideas, so every suggestion
seeds follow-on content.

## When to use this skill
Triggers: "give me video ideas," "what should I make for fall," "ideas for the thrifting pillar,"
"how do I stand out." Do NOT develop one idea into hook, title, and clips (use video-development) or
produce a downloadable calendar file (use document-studio).

## Inputs
Pillar(s), persona(s), seasonal context, and any platform target. Anything unstated is inferred and
stated, or left unspecified.

## Core procedure
Follow `shared/method.md`; compose atoms via `workflow.json`.
1. Classify the pillar (pillar-classify) and map the persona from `shared/audience-engine.md`.
2. Generate an idea batch (idea-generate) as clusters, not single ideas.
3. Verify any trend or seasonal claim (trend-check) through `shared/web-intel-engine.md`; mark data
   older than the freshness window as stale rather than dropping it.
4. Gate the cluster (govern-artifact) before it ships.

## Output contract
An idea cluster: each idea with pillar, format, persona served, hook angle, scale (quick win, medium,
hero), and a follow-on seed. Includes `source_artifacts` and `retrieval_gaps`. Obeys
`protocols/formatting-metadata.md`.

## Engines and protocols loaded
`shared/brand-engine.md`, `shared/audience-engine.md`, `shared/adaptation-engine.md`,
`shared/platform-engine.md`, `shared/web-intel-engine.md`. Protocols: `protocols/research-citation.md`,
`protocols/no-fabrication.md`, `protocols/formatting-metadata.md`, `protocols/quality-gates.md`.

## Atoms used
pillar-classify, idea-generate, trend-check, govern-artifact. A user can call idea-generate or
trend-check directly for a one-off.

## Standalone usability
Produces a complete idea cluster even when no downstream spoke is available, and names the next step
(video-development) as a hint, not a dependency.

## Failure modes
- Recommending a trend without verifying current momentum. trend-check is mandatory for any trend or
  seasonal claim; data older than 14 days for fast-moving categories is marked stale.
- Returning single ideas instead of clusters.
- Drifting off the home decor aesthetic toward bright farmhouse.

## Cross-modality
Class: A.
Runs on: every surface, including a consumer Gemini Gem (knowledge-only). No tool required.
Mechanism: Pure reasoning over the shared brand/audience/platform/adaptation engines + protocols; no tool or data fetch.
Fallback: None needed; reasoning-only. Null-flag any figure the user has not supplied; never invent metrics.
See `shared/cross-modality-engine.md`.