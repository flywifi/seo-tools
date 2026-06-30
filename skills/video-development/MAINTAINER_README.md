---
file: skills/video-development/MAINTAINER_README.md
purpose: keep video-development producing a full package with at least three standalone clips, never fewer.
---

# video-development: Maintainer README

## Purpose
Develops one concept into a production package (hook, title, outline, thumbnail, SEO description, and
3 or more standalone clips). It does not generate fresh ideas or write the full spoken script.

## Non-negotiable invariants
- Shared: self-checks against `protocols/quality-gates.md`; obeys `protocols/no-fabrication.md` and
  `protocols/formatting-metadata.md`.
- At least 3 short-form clips per concept, each with its own first-3-seconds hook and standalone.
- Title and thumbnail align; no overpromising.
- SEO keywords come from keyword-cluster; verify volume signals, never invent them.

## Known failure modes
- Fewer than 3 clips, or clips that need the full video for context.
- Keyword-stuffed or clickbait titles.
- Overpromising thumbnails.

## Fragile fallbacks that must not become defaults
- Shipping a package with 2 clips because the outline felt short.

## Regression cases to preserve
1. Any concept: at least 3 standalone clips returned.
2. Each clip has its own hook and no "earlier in the video" reference.
3. Title front-loads the primary keyword and aligns with the thumbnail.
4. SEO description carries 1 to 2 primaries in the opening 200 characters.
5. No fabricated performance claims anywhere in the package.

## Approval-gated changes
- The atom wiring in workflow.json and the output contract in SKILL.md.

## Minority-report policy
When two title or thumbnail directions are equally strong, record the chosen one, the alternative,
why, and what would change it.

## Update checklist
- workflow.json references only installed atoms.
- Run python3 tools/sync_check.py.
