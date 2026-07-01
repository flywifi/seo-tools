export const meta = {
  name: 'content-distribution',
  description: 'Schedule and distribute finalized content across social platforms via the active publishing connector or manual fallback',
  phases: [
    { title: 'Prepare', detail: 'Resolve active publishing connectors and tier per platform' },
    { title: 'Distribute', detail: 'Call schedule-post per platform, enforce FTC/AIGC compliance' },
    { title: 'Verify', detail: 'Check post-status for any posts in processing state' },
    { title: 'Report', detail: 'Assemble distribution report with per-platform outcomes' },
  ],
}

// Read-only research agent operating rules (required by shared/research-orchestration-engine.md)
// Agents in this workflow are READ-ONLY. They read files, query MCP tools, and return structured
// findings. They MUST NOT create, edit, write, or delete files. They MUST NOT commit or push.
// All file writes are performed by the main loop after aggregating agent findings.

// VERIFICATION_SCHEMA — used by the adversarial verification agent in the Prepare phase
// to independently challenge the primary publishing-plan agent's claims.
const VERIFICATION_SCHEMA = {
  type: 'object',
  properties: {
    discrepancies_found: { type: 'boolean' },
    discrepancy_details: { type: 'array', items: { type: 'string' } },
    verdict: { type: 'string', enum: ['pass', 'pass_with_flags', 'fail'] },
    minority_report: { type: ['object', 'null'] },
    confidence_evidence: { type: 'object' },
    source_citations: { type: 'array' },
  },
  required: ['discrepancies_found', 'verdict', 'minority_report', 'confidence_evidence', 'source_citations'],
}

const PUBLISHING_PLAN_SCHEMA = {
  type: 'object',
  properties: {
    platform_plans: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          platform: { type: 'string' },
          tier: { type: 'string', enum: ['direct_api', 'manual'] },
          connector: { type: 'string' },
          will_auto_queue: { type: 'boolean' },
          caption_ready: { type: 'boolean' },
          hashtags_ready: { type: 'boolean' },
        },
        required: ['platform', 'tier', 'connector', 'will_auto_queue'],
      },
    },
    any_connector_active: { type: 'boolean' },
    missing_captions: { type: 'array', items: { type: 'string' } },
    missing_hashtags: { type: 'array', items: { type: 'string' } },
    minority_report: { type: ['object', 'null'] },
    confidence_evidence: {
      type: 'object',
      properties: {
        overall: { type: 'string', enum: ['high', 'medium', 'low'] },
        basis: { type: 'string' },
        source_tier_breakdown: {
          type: 'object',
          properties: {
            t1_count: { type: 'integer' },
            t2_count: { type: 'integer' },
            t3_count: { type: 'integer' },
          },
        },
      },
    },
    source_citations: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          source_id_or_url: { type: 'string' },
          tier: { type: 'string' },
          claim_supported: { type: 'string' },
          in_source_registry: { type: 'boolean' },
        },
      },
    },
  },
  required: ['platform_plans', 'any_connector_active', 'minority_report', 'confidence_evidence', 'source_citations'],
}

const POST_RESULT_SCHEMA = {
  type: 'object',
  properties: {
    platform: { type: 'string' },
    status: { type: 'string', enum: ['awaiting_human_confirmation', 'scheduled', 'manual_required', 'failed', 'skipped'] },
    publishing_tier: { type: 'string' },
    post_id: { type: ['string', 'null'] },
    scheduled_datetime: { type: ['string', 'null'] },
    permalink: { type: ['string', 'null'] },
    ftc_disclosure_verified: { type: 'boolean' },
    aigc_flag_set: { type: 'boolean' },
    human_review_required: { type: 'boolean', enum: [true] },
    error: { type: ['string', 'null'] },
    notes: { type: ['string', 'null'] },
    minority_report: { type: ['object', 'null'] },
    confidence_evidence: { type: 'object' },
    source_citations: { type: 'array' },
  },
  required: ['platform', 'status', 'publishing_tier', 'human_review_required', 'minority_report', 'confidence_evidence', 'source_citations'],
}

const STATUS_CHECK_SCHEMA = {
  type: 'object',
  properties: {
    platform: { type: 'string' },
    post_id: { type: 'string' },
    status: { type: 'string' },
    permalink: { type: ['string', 'null'] },
    engagement_snapshot: { type: ['object', 'null'] },
    notes: { type: ['string', 'null'] },
    minority_report: { type: ['object', 'null'] },
    confidence_evidence: { type: 'object' },
    source_citations: { type: 'array' },
  },
  required: ['platform', 'post_id', 'status', 'minority_report', 'confidence_evidence', 'source_citations'],
}

// ---------------------------------------------------------------------------
// Phase 1: Prepare — resolve publishing plan and check content readiness
// ---------------------------------------------------------------------------

phase('Prepare')

const prepareAgent = await agent(
  `You are a READ-ONLY research agent. You MUST NOT create, edit, write, or delete any files.
You MUST NOT commit or push. Your only job is to read and return structured findings.

TASK: Resolve the content distribution publishing plan.

1. Call the get_publishing_plan MCP tool to determine which platforms have active connectors
   and at what tier (direct_api or manual).

2. Inspect the args object (passed from the caller). It should contain:
   - platform_targets: array of platforms to distribute to
   - captions: object keyed by platform (may be null/missing per platform)
   - hashtags: object keyed by platform (may be null/missing per platform)
   - scheduled_datetimes: optional object keyed by platform
   - ftc_disclosures: optional object keyed by platform
   - is_aigc: boolean (default false)

3. For each platform in platform_targets:
   - Check if a caption is provided (captions[platform] is non-null and non-empty)
   - Check if hashtags are provided (hashtags[platform] is non-null)
   - Merge the publishing tier from the get_publishing_plan result

4. Return the structured publishing plan with per-platform tier assignments and readiness flags.
   Mark missing_captions and missing_hashtags as arrays of platform names.

5. Never fabricate connector state — read from get_publishing_plan only.
   Human confirmation is always required. human_review_required is always true.

ARGS: ${JSON.stringify(args)}`,
  { label: 'prepare:publishing-plan', phase: 'Prepare', schema: PUBLISHING_PLAN_SCHEMA }
)

if (!prepareAgent) {
  log('Prepare phase failed — cannot resolve publishing plan. Aborting.')
  return { error: 'publishing plan resolution failed', args }
}

log(`Publishing plan resolved. Connector active: ${prepareAgent.any_connector_active}. Platforms: ${prepareAgent.platform_plans.map(p => `${p.platform}(${p.tier})`).join(', ')}`)

// ---------------------------------------------------------------------------
// Adversarial verification of the publishing plan
// ---------------------------------------------------------------------------

const planVerifyAgent = await agent(
  `You are a READ-ONLY adversarial verification agent. You MUST NOT create, edit, or write files.

TASK: Independently verify the publishing plan produced by the prepare agent.

Publishing plan to verify:
${JSON.stringify(prepareAgent, null, 2)}

Check:
1. Does the tier assignment for each platform match what get_publishing_plan would return?
   Call get_publishing_plan and compare.
2. Are there any platforms in platform_targets that are missing from the plan?
3. Are missing_captions and missing_hashtags accurate?
4. Are there any compliance concerns (FTC disclosures, AIGC flags) not flagged in the plan?

Return your verdict. If you find discrepancies, note them in minority_report.
Do not fabricate connector state — call get_publishing_plan to verify.`,
  { label: 'verify:publishing-plan', phase: 'Prepare', schema: PUBLISHING_PLAN_SCHEMA }
)

if (planVerifyAgent && planVerifyAgent.minority_report) {
  log(`Plan verification flagged issues: ${JSON.stringify(planVerifyAgent.minority_report)}`)
}

// ---------------------------------------------------------------------------
// Phase 2: Distribute — run schedule-post per platform
// ---------------------------------------------------------------------------

phase('Distribute')

const platformPlans = prepareAgent.platform_plans || []

const postResults = await pipeline(
  platformPlans,
  async (platformPlan) => {
    const plat = platformPlan.platform
    const captionData = args && args.captions ? args.captions[plat] : null
    const hashtagData = args && args.hashtags ? args.hashtags[plat] : null
    const scheduledAt = args && args.scheduled_datetimes ? args.scheduled_datetimes[plat] : null
    const ftcDisclosure = args && args.ftc_disclosures ? args.ftc_disclosures[plat] : null
    const isAigc = args && args.is_aigc ? args.is_aigc : false
    const boardName = args && args.board_names ? args.board_names[plat] : null
    const mediaUrl = args && args.media_urls ? args.media_urls[plat] : null
    const contentType = args && args.content_types ? args.content_types[plat] : 'reel'

    if (!captionData) {
      return {
        platform: plat,
        status: 'skipped',
        publishing_tier: platformPlan.tier,
        post_id: null,
        scheduled_datetime: null,
        permalink: null,
        ftc_disclosure_verified: false,
        aigc_flag_set: false,
        human_review_required: true,
        error: 'No caption provided for this platform.',
        notes: 'Run caption-write atom first, then retry content-distributor.',
        minority_report: null,
        confidence_evidence: { overall: 'high', basis: 'caption absent — skip is correct', source_tier_breakdown: { t1_count: 0, t2_count: 0, t3_count: 0 } },
        source_citations: [],
      }
    }

    return await agent(
      `You are a READ-ONLY research agent. You MUST NOT create, edit, write, or delete files.
You MUST NOT commit or push. Return structured findings only.

TASK: Generate a schedule-post confirmation summary for ${plat}.

IMPORTANT: Human confirmation is ALWAYS required before any post is queued.
This agent produces a confirmation summary — it does NOT actually post anything.

Platform: ${plat}
Content type: ${contentType}
Caption: ${captionData}
Hashtags: ${JSON.stringify(hashtagData)}
Scheduled datetime: ${scheduledAt || 'post immediately'}
FTC disclosure: ${ftcDisclosure || 'none'}
AIGC flag: ${isAigc}
Board name (Pinterest): ${boardName || 'n/a'}
Media URL provided: ${!!mediaUrl}

Publishing tier resolved by prepare phase: ${platformPlan.tier}
Connector: ${platformPlan.connector}

Steps:
1. Verify FTC disclosure: if ftc_disclosure is non-null, confirm it appears in caption.
   If absent from caption, note that it would be prepended.
2. Verify AIGC flag: if is_aigc=true and platform=tiktok, confirm aigc_flag_set=true.
3. Check cross-platform watermark rule: if content_type is reel or short, note if
   content may have been sourced from a competing platform.
4. Build the confirmation summary fields below.
5. Set status to 'manual_required' if tier is manual, otherwise 'awaiting_human_confirmation'.
   Nothing is queued or posted by this workflow — the creator confirms and schedules each
   post in the Scheduling Dashboard (http://localhost:8766). The dashboard click IS the
   human confirmation step.
6. Never fabricate post_id or permalink — both are null until the creator schedules the post.

Return the structured post result.`,
      {
        label: `distribute:${plat}`,
        phase: 'Distribute',
        schema: POST_RESULT_SCHEMA,
      }
    )
  }
)

const validResults = postResults.filter(Boolean)
const awaitingConfirmation = validResults.filter(r => r.status === 'awaiting_human_confirmation' || r.status === 'scheduled').length
const manual = validResults.filter(r => r.status === 'manual_required').length
const failed = validResults.filter(r => r.status === 'failed').length
const skipped = validResults.filter(r => r.status === 'skipped').length

log(`Distribution summary: ${awaitingConfirmation} awaiting human confirmation, ${manual} manual required, ${failed} failed, ${skipped} skipped`)

// ---------------------------------------------------------------------------
// Phase 3: Verify — post-status check for processing posts
// ---------------------------------------------------------------------------

phase('Verify')

// Status checks only apply to posts that actually reached a connector and have a real
// post_id. This workflow never posts (the creator schedules in the dashboard), so post_id
// is null here and this stage is a no-op today. It activates once live publishing populates
// post_id (see tools/publishing/ and the live_publishing_enabled flag).
const processingPosts = validResults.filter(r => r.status === 'scheduled' && r.post_id)

let statusResults = []
if (processingPosts.length > 0) {
  statusResults = await pipeline(
    processingPosts,
    async (post) => {
      return await agent(
        `You are a READ-ONLY research agent. You MUST NOT create, edit, or write files.

TASK: Check post status for ${post.platform} post_id=${post.post_id}.

Call the post_status MCP tool with:
  platform: ${post.platform}
  post_id: ${post.post_id}
  include_engagement_snapshot: false

Return the structured status result. Never fabricate permalink or engagement numbers.
If no connector is active, return status: unknown with the manual check URL.`,
        {
          label: `verify:${post.platform}-${post.post_id}`,
          phase: 'Verify',
          schema: STATUS_CHECK_SCHEMA,
        }
      )
    }
  )
  log(`Status checks complete for ${processingPosts.length} scheduled posts`)
} else {
  log('No scheduled posts with post_ids to verify — skipping status checks')
}

// ---------------------------------------------------------------------------
// Phase 4: Report — assemble distribution report
// ---------------------------------------------------------------------------

phase('Report')

const distributionSummary = {
  total_platforms: platformPlans.length,
  awaiting_human_confirmation: awaitingConfirmation,
  manual_required: manual,
  failed,
  skipped,
}

// Enrich each post with the caption/hashtags/schedule from args so the report is
// importable into the Scheduling Dashboard via POST /api/import-report. The agent's
// POST_RESULT_SCHEMA carries compliance flags but not the caption text itself.
const enrichedPosts = validResults.map(r => {
  const plat = r.platform
  return {
    ...r,
    caption: (args && args.captions ? args.captions[plat] : null) ?? null,
    hashtags: (args && args.hashtags ? args.hashtags[plat] : null) ?? null,
    content_type: (args && args.content_types ? args.content_types[plat] : null) ?? null,
    media_url: (args && args.media_urls ? args.media_urls[plat] : null) ?? null,
    scheduled_datetime: r.scheduled_datetime ?? (args && args.scheduled_datetimes ? args.scheduled_datetimes[plat] : null) ?? null,
  }
})

const manualPackages = validResults
  .filter(r => r.status === 'manual_required')
  .map(r => ({
    platform: r.platform,
    notes: r.notes || 'Use publish-draft atom for a full manual posting package.',
  }))

const nextSteps = []
if (manual > 0) {
  nextSteps.push(`${manual} platform(s) require manual posting. Run publish-draft atom per platform for paste-ready captions and checklists.`)
}
if (skipped > 0) {
  nextSteps.push(`${skipped} platform(s) skipped due to missing captions. Run caption-write atom then retry.`)
}
if (failed > 0) {
  nextSteps.push(`${failed} platform(s) failed. Review error field per post and retry after resolving.`)
}
if (awaitingConfirmation > 0) {
  nextSteps.push(`${awaitingConfirmation} post(s) prepared and awaiting human confirmation. Nothing is queued yet — open the Scheduling Dashboard to review, schedule, and confirm each one.`)
}
nextSteps.push('Run govern-artifact with gates: integrity, safety, brand_alignment before confirming any post.')
nextSteps.push('Open the Scheduling Dashboard to review and schedule posts: http://localhost:8766')
nextSteps.push('To load these posts into the dashboard automatically, POST this report to http://localhost:8766/api/import-report')

return {
  distribution_summary: distributionSummary,
  posts: enrichedPosts,
  status_checks: statusResults.filter(Boolean),
  manual_posting_packages: manualPackages,
  next_steps: nextSteps,
  human_review_required: true,
  publishing_plan: prepareAgent,
  plan_verification: planVerifyAgent,
  dashboard_url: 'http://localhost:8766',
  dashboard_import_url: 'http://localhost:8766/api/import-report',
}
