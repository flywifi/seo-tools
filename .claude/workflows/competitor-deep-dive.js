export const meta = {
  name: 'competitor-deep-dive',
  description: 'Comprehensive competitive analysis: scan, extract metadata, map entities, identify gaps',
  phases: [
    { title: 'Scan', detail: 'Fetch competitor channel metadata, extract hidden tags and entities' },
    { title: 'Analyze', detail: 'Identify keyword gaps, format gaps, and opportunities' },
    { title: 'Verify', detail: 'Adversarial verification of competitor claims and gap analysis' },
  ],
}

const COMPETITOR_SCHEMA = {
  type: 'object',
  properties: {
    competitor: {
      type: 'object',
      properties: {
        name: { type: 'string' },
        platform: { type: 'string' },
        url: { type: 'string' },
      },
      required: ['name', 'platform'],
    },
    content_pillars: { type: 'array', items: { type: 'string' } },
    video_tags: { type: 'array', items: { type: 'string' } },
    hashtags: { type: 'array', items: { type: 'string' } },
    entity_map: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          entity: { type: 'string' },
          type: { type: 'string' },
          frequency: { type: 'integer' },
          niche_fit: { type: 'string', enum: ['high', 'medium', 'low'] },
        },
        required: ['entity', 'type'],
      },
    },
    keyword_gaps: { type: 'array', items: { type: 'string' } },
    format_gaps: { type: 'array', items: { type: 'string' } },
    sources_consulted: { type: 'array', items: { type: 'string' } },
    retrieval_gaps: { type: 'array', items: { type: 'string' } },
    discovered_sources: { type: 'array', items: { type: 'string' } },
    confidence: { type: 'string', enum: ['high', 'medium', 'low'] },
    minority_report: { type: ['object', 'null'] },
    confidence_evidence: { type: 'object', properties: { overall: { type: 'string' }, basis: { type: 'string' }, source_tier_breakdown: { type: 'object' } } },
    source_citations: { type: 'array', items: { type: 'object', properties: { source_id_or_url: { type: 'string' }, tier: { type: 'string' }, claim_supported: { type: 'string' }, in_source_registry: { type: 'boolean' } }, required: ['source_id_or_url', 'tier', 'claim_supported'] } },
  },
  required: ['competitor', 'sources_consulted', 'retrieval_gaps', 'confidence', 'minority_report', 'confidence_evidence', 'source_citations'],
}

const GAP_SCHEMA = {
  type: 'object',
  properties: {
    keyword_gaps: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          keyword: { type: 'string' },
          competitor_usage: { type: 'string' },
          creator_status: { type: 'string' },
          opportunity_score: { type: 'string', enum: ['high', 'medium', 'low'] },
        },
        required: ['keyword', 'opportunity_score'],
      },
    },
    format_gaps: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          format: { type: 'string' },
          competitor_usage: { type: 'string' },
          recommendation: { type: 'string' },
        },
        required: ['format'],
      },
    },
    opportunities: { type: 'array', items: { type: 'string' } },
    sources_consulted: { type: 'array', items: { type: 'string' } },
    retrieval_gaps: { type: 'array', items: { type: 'string' } },
    minority_report: { type: ['object', 'null'] },
    confidence_evidence: { type: 'object', properties: { overall: { type: 'string' }, basis: { type: 'string' }, source_tier_breakdown: { type: 'object' } } },
    source_citations: { type: 'array', items: { type: 'object', properties: { source_id_or_url: { type: 'string' }, tier: { type: 'string' }, claim_supported: { type: 'string' }, in_source_registry: { type: 'boolean' } }, required: ['source_id_or_url', 'tier', 'claim_supported'] } },
  },
  required: ['keyword_gaps', 'format_gaps', 'opportunities', 'minority_report', 'confidence_evidence', 'source_citations'],
}

const READ_ONLY_RULES = `## Operating rules
You are a READ-ONLY research agent. You MUST NOT create, edit, write, or delete any files.
You MUST NOT run any command that modifies the filesystem, make commits, or push to any branch.
You MAY read files, search with Glob/Grep, run read-only commands, query MCP tools, and use WebFetch/WebSearch.
Return your findings as structured data.`

const targets = Array.isArray(args) ? args : [args || 'moody home decor YouTube competitor']

// Phase 1 + 2: Scan and extract per competitor (pipelined — each competitor flows independently)
phase('Scan')
log(`Analyzing ${targets.length} competitor(s)`)

const profiles = await pipeline(
  targets,
  (target, _, idx) => agent(
    `${READ_ONLY_RULES}

You are a competitor intelligence agent for Creator OS (home decor / DIY niche).

Research this competitor: "${target}"

1. Read shared/web-intel-engine.md for acquisition rules.
2. Use the competitor_scan MCP tool to check for existing snapshot data.
3. If no snapshot exists, use WebFetch to analyze their channel/profile page.
4. Extract: channel name, platform, subscriber range, upload cadence, content pillars,
   recent video titles, description patterns.
5. If YouTube: look for hidden video tags in page metadata (ytInitialPlayerResponse.videoDetails.keywords).
6. Extract hashtags from descriptions.
7. Identify named entities: brands, products, places, techniques.
8. Map their content pillars and compare to the creator's 5 pillars (DIY/makeovers,
   thrifting/antiques, organization, seasonal/holiday, backyard/outdoor).

All metrics are [unverified] unless from a confirmed API response. Never fabricate numbers.`,
    { label: `scan:${idx}`, phase: 'Scan', schema: COMPETITOR_SCHEMA, agentType: 'competitor-analyst' }
  )
)

const validProfiles = profiles.filter(Boolean)
if (validProfiles.length === 0) {
  log('No competitor profiles retrieved.')
  return { targets, profiles: [], gaps: null, status: 'scan_failed' }
}

log(`${validProfiles.length} competitor profile(s) scanned. Running gap analysis.`)

// Phase 3: Analyze — needs all profiles together for cross-competitor comparison
phase('Analyze')

const gaps = await agent(
  `${READ_ONLY_RULES}

You are an SEO gap analysis agent for Creator OS (home decor / DIY niche).

Analyze these competitor profiles and identify gaps and opportunities for the creator:

${JSON.stringify(validProfiles, null, 2)}

The creator's 5 content pillars are: DIY/makeovers, thrifting/antiques, organization,
seasonal/holiday, backyard/outdoor.

1. Read the offline keyword cache via cache_query MCP tool to check which competitor keywords
   the creator already targets.
2. Identify keyword gaps: terms competitors use that the creator does not.
3. Identify format gaps: content types competitors produce that the creator does not.
4. Score each gap opportunity as high/medium/low based on niche relevance and competition.
5. Synthesize 3 to 5 actionable opportunities ranked by impact.

Never fabricate volume data. Label all estimates [estimated].`,
  { label: 'gap-analysis', phase: 'Analyze', schema: GAP_SCHEMA }
)

// Phase 3: Verify — adversarial-verify claims from scan and gap analysis
phase('Verify')
log('Running adversarial verification on competitor findings')

const VERIFICATION_SCHEMA = {
  type: 'object',
  properties: {
    verified_claims: { type: 'integer' },
    flagged_claims: { type: 'array', items: { type: 'object', properties: { claim: { type: 'string' }, issue: { type: 'string' }, severity: { type: 'string' } }, required: ['claim', 'issue'] } },
    confidence_valid: { type: 'boolean' },
    minority_report_adequate: { type: 'boolean' },
    overall_verdict: { type: 'string', enum: ['pass', 'pass_with_flags', 'fail'] },
  },
  required: ['verified_claims', 'flagged_claims', 'overall_verdict'],
}

const verification = await agent(
  `${READ_ONLY_RULES}

You are an adversarial verification agent. Your job is to CHALLENGE and VERIFY the findings
from a competitor analysis, not to agree with them.

Primary agent findings to verify:
${JSON.stringify({ profiles: validProfiles, gaps }, null, 2)}

Verification checklist:
1. For each source_citation: does it exist in canonical-sources/source-registry.json or is it a real URL?
   Use Glob/Grep to check source-registry.json for source IDs.
2. Unsourced numbers: are there specific numbers (view counts, percentages, subscriber counts)
   without a corresponding citation? Flag each one.
3. Confidence-tier alignment: if confidence is "high", is there at least 1 T1 source in the
   source_tier_breakdown? If "medium", at least 1 T2 or 2 T3?
4. Minority report adequacy: if retrieval_gaps exist, should there be a minority_report documenting
   residual uncertainty? Flag if missing.
5. Keyword gaps: are the claimed gaps plausible given the creator's 5 pillars (DIY/makeovers,
   thrifting/antiques, organization, seasonal/holiday, backyard/outdoor)?

Default to flagging if uncertain. It is better to over-flag than to let fabricated claims through.`,
  { label: 'adversarial-verify', phase: 'Verify', schema: VERIFICATION_SCHEMA }
)

return {
  targets,
  profiles: validProfiles,
  gaps,
  verification,
  status: gaps ? 'complete' : 'gaps_analysis_failed',
}
