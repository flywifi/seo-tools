# 26. P41 Rerun Observations Open Vocabulary

- Date: 2026-07-11
- Status: Accepted

## Context

Brands request arbitrary combinations of posts, video ideas, scripts, story sets, and UGC; the pricing path must degrade honestly per item instead of assuming the six template formats. Strict-unknown-keys keeps the quality gate deterministic.

## Decision

Closed the two CoolBreeze re-run observations and opened the deliverable vocabulary. score.py evaluate() now rejects unknown dimension keys with an explicit error (the nine dimensions in protocols/quality-gates.md are exhaustive; a silently dropped score misleads the caller). finance.py suppresses the generic missing_input gap when the specific no_rate_card_entry gap fired for the same item, in both price_package and the --price CLI handler. The rate-card template documents format keys as open vocabulary and adds null rows for youtube_short, instagram_post_static, instagram_story_set, video_concept_ideas, script_only, and ugc_video_brand_channel; proposal-price, deal-pipeline, pitch-extract, and contract-draft document the mapping rule: map a deliverable to a format key only when unambiguous, otherwise unpriceable with a named gap, never forced into a video format; multi-deliverable agreements enumerate every deliverable. Regression-locked: 3 new finance selftest checks (99/99), a not_matches assertion check in scenario_check, an S4 unknown-dimension leg, and S7 extended to a mixed 3-type package.

## Consequences

Ledger status at record time: `accepted`. Source: `ledger/ledger.json` id `P41-rerun-observations-open-vocabulary`.
