---
file: skills/content-distributor/MAINTAINER_README.md
purpose: preserve the non-negotiable operating rules for content-distributor so it stays stable under iteration.
---

# content-distributor: Maintainer README

## Purpose
`content-distributor` is the social scheduling and distribution spoke. It accepts finalized content (captions, hashtags, media URLs) from `shortform-repurposing` or directly from the creator, resolves the active publishing connector per platform, presents a confirmation table, and on creator approval queues or schedules posts via the connector. When no connector is active for a platform it produces a manual posting package via `publish-draft`. The spoke's job ends when posts are queued or manual packages are delivered; follow-up status checks are delegated to `post-status` (Step 4).

## Non-negotiable invariants

- **Shared:** references `shared/method.md`; self-checks against `protocols/quality-gates.md`; obeys `protocols/no-fabrication.md` and `protocols/formatting-metadata.md`.
- **Human confirmation required before every connector call.** `schedule-post` presents the full confirmation table and halts until the creator explicitly approves. Never auto-post.
- **`human_review_required: true` on every post entry in the output.** No exceptions. Absent or false is a regression.
- **No connector call precedes the compliance check.** FTC disclosure and AIGC flag must be verified before `schedule-post` is invoked (Steps 2 and 3 cannot be reordered).
- **No fabricated post_id, permalink, or status.** All connector return values flow through as-is or are null. The spoke never invents an ID or URL.
- **Manual mode is always available.** When no `content_publishing` connector is active, every platform in `platform_targets` gets a `manual_posting_package` entry. Distribution never blocks.
- **Steps 1 and 2 are conditional, not mandatory.** If captions and hashtags are already provided (Mode A from `shortform-repurposing`), `caption-write` and `hashtag-set` are skipped entirely. Never re-run caption generation when captions are already supplied.
- **`govern-artifact` runs last.** Quality gates (integrity, safety, brand_alignment) are the final step. A gate failure on an already-queued post surfaces the failure in output but cannot unqueue the post; the creator must take manual remediation.

## Known failure modes

- **Silent connector fallback.** If connector resolution fails silently and the spoke posts in manual mode without surfacing the failure reason, the creator is left without actionable information. Connector resolution (Step 1) must always surface which platforms have no active connector and why.
- **FTC disclosure stripped by post-processing.** If a downstream formatting step truncates the caption before the connector call, the prepended disclosure may be silently removed. The spoke must pass the FTC-prefixed caption as-is; no re-formatting between compliance check and connector call.
- **Caption generation in Mode B overwriting provided captions.** If Mode B logic triggers when captions are already supplied, the creator's captions are discarded. The skip condition (`captions_already_provided`) must be evaluated per-platform before invoking `caption-write`.
- **Govern-artifact gate failure not surfaced.** If `govern-artifact` returns a gate failure but the spoke reports success, the creator ships non-compliant content. Gate failures must appear in output and next_steps regardless of whether posts were queued.

## Fragile fallbacks that must not become defaults

- **`publish-draft` as scheduling.** The manual package is a fallback for when no connector is active. It must never be returned as the primary output when a connector is available. The publishing_tier label (`hosted_mcp | direct_api | manual`) must accurately reflect which path was used.
- **Caption generation (Mode B).** Invoking `caption-write` is only valid when no caption was provided for a platform. Mode B is a degraded path for operators who did not run `shortform-repurposing` first. It must be labeled as such in output notes when invoked.
- **Post-status skip.** Step 4 is optional; skipping it is acceptable. But when a connector returns `status: processing` and the creator does not check back, posts may fail silently. The spoke must remind the creator in `next_steps` to run `post-status` for any processing posts.

## Regression cases to preserve

1. **content-distributor-001** (Mode A, all platforms queued via Postiz): captions provided, Postiz active for all platforms, human confirms — all posts return `status: queued`, `publishing_tier: hosted_mcp`; Steps 1 and 2 are skipped; `distribution_summary.queued == platform_count`.
2. **content-distributor-002** (No connector, full manual fallback): no connector active for any platform — all posts return `status: manual_required`; every platform has a populated `manual_posting_packages` entry; nothing blocks distribution.
3. **content-distributor-003** (Mode B, captions generated): no captions provided, `content_brief` given — `caption-write` and `hashtag-set` run per platform before `schedule-post`; generated captions are passed to connector, not placeholder values.
4. **content-distributor-004** (Mixed: 3 platforms queued, 1 manual): Postiz active for Instagram, TikTok, Pinterest; no connector for YouTube — `distribution_summary` shows `queued: 3, manual_required: 1`; YouTube gets a `manual_posting_package`; other platforms do not.
5. **content-distributor-005** (FTC disclosure prepend): `ftc_disclosure: "#gifted"` provided; caption does not contain `#gifted` — `schedule-post` prepends disclosure; `ftc_disclosure_verified: true` in every post entry; govern-artifact confirms disclosure before releasing.
6. **content-distributor-006** (Govern-artifact gate failure): caption fails the safety gate — gate failure appears in `govern_artifact_result` and `next_steps`; all posts that were queued before the gate check retain their `status: queued` but the gate failure is surfaced.
7. **content-distributor-007** (TikTok AIGC flag): `is_aigc: true`, platform includes TikTok — `schedule-post` sets AIGC flag in connector payload; `aigc_flag_set: true` appears in TikTok post entry.

## Approval-gated changes

- **Output schema changes** (`distribution_summary`, `posts[]`, `manual_posting_packages[]`): any field addition, removal, or rename requires a version bump and evals update.
- **Atom wiring changes** (adding, removing, or reordering steps in `workflow.json`): requires review against the skip conditions and the human confirmation gate placement.
- **Connector tier resolution order** (Postiz > Buffer > direct API > manual): any change to this priority requires updating `schedule-post/SKILL.md` and this file.
- **Govern-artifact gate list** (integrity, safety, brand_alignment): any gate addition or removal requires eval coverage for the new gate.

## Minority-report policy

**Chosen interpretation: Mode A skips steps 1 AND 2 even when hashtags are absent.**

Conflict: The plan says "Steps 1 and 2 are skipped when the spoke receives pre-written captions from shortform-repurposing." A literal reading skips both caption-write and hashtag-set. An alternative reading is that hashtag-set should still run if hashtags are absent even when captions are provided.

Chosen: skip both steps unconditionally when captions are provided. If hashtags are absent, `schedule-post` passes `hashtags: null` and the connector either generates them or omits them per platform behavior. `hashtag-set` can be explicitly re-invoked as a shortcut atom if needed.

Reason: the plan explicitly lists the skip condition as `captions_already_provided` without a hashtag carve-out. Keeping the condition simple reduces ambiguity and prevents partial Mode A / Mode B blending.

What would overturn it: a SKILL.md revision that explicitly separates caption and hashtag skip conditions.

## Update checklist

1. Edit the target file.
2. Verify all backticked path references in `SKILL.md` and this file resolve to real files on disk.
3. If `workflow.json` changed: confirm every `atom` value resolves to a directory under `skills/atoms/`.
4. Update `evals/evals.json` to cover any new behavior or changed output keys.
5. Run `python3 tools/sync_check.py` — must exit 0 with all invariants passing.
6. If the output schema changed: update `shared/schemas/distribution-report.json`.
7. Commit with message referencing the spoke and the change type.
