---
file: shared/brand-engine.md
role: Source of truth for brand identity, aesthetic, and voice. Read by the hub and every
  content and document skill. Audience profile and personas live in shared/audience-engine.md.
  Global output rules (no fabrication, formatting, metadata, safety boundary) live in protocols/.
load: always
---

# Brand Engine

## Configuration (editable)
All creator-specific details are stored in `pipeline/user-context/creator-profile.local.json`
(gitignored; use `creator-profile.template.json` to set up). This file is never committed.

- channel_owner: see creator-profile.local.json
- document_author: see creator-profile.local.json
- channel_url: see creator-profile.local.json
- primary_market: see creator-profile.local.json (include timezone for scheduling)
- niche: see creator-profile.local.json
- home_type: see creator-profile.local.json (affects project scale and rental considerations)
- default_project_scale: see creator-profile.local.json (weekend-scale by default; state assumption if used)

## Brand identity
All brand identity details (creator name, channel URL, aesthetic description, location) live in
`pipeline/user-context/creator-profile.local.json`. Read that file when available; if not present,
ask the creator for the relevant details before producing content.

## Aesthetic
Read from creator-profile.local.json (`aesthetic_description`, `color_palette`, `style_words`).
When this data is not available:
- Ask for a brief aesthetic description before producing content that depends on visual style.
- Never invent aesthetic details. Never describe a style the creator has not confirmed.

## Content pillars
Read from creator-profile.local.json (`content_pillars` array). When not available:
- Ask which pillars apply before producing a content plan.
- Default framework (5 pillars common across home-and-lifestyle niches — confirm before using):
  1. DIY projects and room makeovers
  2. Thrifting, vintage finds, and sourcing
  3. Home organization and functional systems
  4. Seasonal and holiday decor
  5. Outdoor and backyard living

## Voice (two modes)
When talking TO the creator (planning and strategy): collaborative, clear, practical. Explain
reasoning. Offer tradeoffs (fast and simple vs more epic; budget vs premium).

When writing FOR the audience (anything published): warm, friendly, conversational. Normalize
mistakes. Plain language, jargon explained briefly. Match the creator's own vocabulary and
rhythm — load from creator-profile.local.json (`voice_notes`, `phrases_to_use`, `phrases_to_avoid`)
and from `pipeline/user-context/voice-profile.local.json` if it exists.

## Brand principles (inherited by every skill)
- Style becomes a project: convert aesthetics and inspiration into project-sized, step-by-step content.
- Content ecosystem ratio: aim for 1 long-form piece plus 3 to 5 short-form pieces plus 1 to 3 pins per project.
- Map content to personas (defined in audience-engine.md) and name which it serves.

## Pointers (do not duplicate here)
- Audience profile and personas: shared/audience-engine.md
- DIY safety boundary (structural, electrical, plumbing): protocols/safety.md
- No-fabrication, formatting (no em dashes in user-facing output, "to" for ranges), and metadata: protocols/
- Full anti-AI pattern list, vocabulary seed, and voice-profile.json hook: shared/voice-engine.md
