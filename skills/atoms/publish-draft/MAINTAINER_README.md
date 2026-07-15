---
file: skills/atoms/publish-draft/MAINTAINER_README.md
purpose: preserve the non-negotiable operating rules for publish-draft so it stays stable under iteration.
---

# publish-draft: Maintainer README

## Purpose
This atom formats finalized content into a paste-ready manual posting package — caption, hashtags, numbered upload checklist, media spec reminder, and FTC note — for a specific platform. It is the always-available fallback invoked by schedule-post when no publishing connector is active. It makes zero network calls and requires no API credentials. Its job ends when the creator has everything they need to post manually through the platform's native app or web interface.

## Non-negotiable invariants
- Never calls any connector or API. Zero network access. This atom is purely a formatter.
- If `ftc_disclosure` is non-null, the disclosure must be present in `formatted_caption`.
- Character limits: caption must not silently exceed platform limits. Return a warning if over the limit; never truncate without surfacing the truncation.
- Hashtag caps: Instagram 5, TikTok 3 to 5, Pinterest 2 to 5, YouTube 3 to 15. Never add more than the cap; drop excess and note in `notes`.
- `optimal_posting_time` must be labeled `[estimated]` unless grounded in the creator's own analytics.
- Never fabricate media specs. Source only from `shared/platform-engine.md`.

## Known failure modes
- Character limit exceeded: surfaced as a warning field, not an error. Creator resolves.
- FTC disclosure absent: prepend and flag in `notes`; do not block output.
- Hashtag count over platform cap: truncate and note.
- Unknown platform: return an error note rather than fabricating specs.
- No media_notes provided: posting checklist omits media-specific steps and adds a reminder.

## Fragile fallbacks that must not become defaults
- This atom is the fallback for schedule-post. If it is consistently invoked (rather than a live connector), the creator should be guided to set up direct platform API credentials. Surface a note suggesting credential setup after 3 or more manual posts to the same platform.

## Regression cases to preserve (mapped to evals/evals.json)
1. Instagram Reel: full inputs → formatted_caption with disclosure, 5-hashtag block, numbered checklist, media specs, optimal_posting_time labeled `[estimated]`
2. TikTok: `is_aigc` note in posting checklist (note to manually enable AIGC toggle in app)
3. Pinterest: hashtags as classification signals note, board_name in checklist, 500-char description limit enforced
4. YouTube Short: character limit, hashtags above title note, thumbnail checklist step
5. Character limit exceeded: warning returned, caption not truncated, character_count vs character_limit shown
6. FTC disclosure missing: prepended to formatted_caption, flagged in `notes`
7. No media_notes: checklist generic steps only, reminder added

## Approval-gated changes
- Changes to platform character limits (must be sourced from platform-engine.md update first)
- Changes to hashtag cap values per platform
- Any change to the FTC disclosure prepend behavior

## Minority-report policy
When platform-engine.md and a more recent platform announcement disagree on a spec, the atom uses platform-engine.md and notes `[check platform-engine.md freshness — spec may have changed]` in `notes`. Run `python3 tools/source_currency.py --check --category platform-spec` to flag stale platform specs.

## Update checklist
1. Run `python3 tools/sync_check.py` — all 48 invariants must pass.
2. Verify all path references resolve: `shared/platform-engine.md`, `shared/brand-engine.md`, `protocols/safety.md`, `protocols/formatting-metadata.md`.
3. After any platform character limit or hashtag cap change, update `shared/platform-engine.md` first, then update SKILL.md Inputs and evals.
4. Update `evals/evals.json` if output schema changes.
