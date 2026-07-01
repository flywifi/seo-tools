export const meta = {
  name: 'deal-review',
  description: 'End-to-end brand partnership deal review: evidence, rights, exclusivity, quality',
  phases: [
    { title: 'Load', detail: 'Read deal and account records' },
    { title: 'Audit', detail: 'Check evidence, usage rights, and exclusivity' },
    { title: 'Verify', detail: 'Cross-verify usage rights against exclusivity for contradictions' },
    { title: 'Score', detail: 'Quality gate scoring and final verdict' },
  ],
}

const DEAL_REVIEW_SCHEMA = {
  type: 'object',
  properties: {
    deal_id: { type: 'string' },
    stage_ready: { type: 'boolean' },
    evidence_gaps: { type: 'array', items: { type: 'string' } },
    usage_rights: {
      type: 'object',
      properties: {
        ownership: { type: 'string' },
        duration: { type: 'string' },
        platform_restrictions: { type: 'array', items: { type: 'string' } },
        ambiguous_clauses: { type: 'array', items: { type: 'string' } },
      },
    },
    exclusivity_conflicts: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          conflicting_deal_id: { type: 'string' },
          category: { type: 'string' },
          date_range: { type: 'string' },
        },
        required: ['conflicting_deal_id', 'category'],
      },
    },
    quality_score: { type: 'number' },
    quality_pass: { type: 'boolean' },
    open_flags: { type: 'array', items: { type: 'string' } },
    human_review_required: { type: 'boolean' },
    sources_consulted: { type: 'array', items: { type: 'string' } },
    retrieval_gaps: { type: 'array', items: { type: 'string' } },
    minority_report: { type: ['object', 'null'] },
    confidence_evidence: { type: 'object', properties: { overall: { type: 'string' }, basis: { type: 'string' }, source_tier_breakdown: { type: 'object' } } },
    source_citations: { type: 'array', items: { type: 'object', properties: { source_id_or_url: { type: 'string' }, tier: { type: 'string' }, claim_supported: { type: 'string' }, in_source_registry: { type: 'boolean' } }, required: ['source_id_or_url', 'tier', 'claim_supported'] } },
  },
  required: ['deal_id', 'stage_ready', 'human_review_required', 'retrieval_gaps', 'minority_report', 'confidence_evidence', 'source_citations'],
}

const READ_ONLY_RULES = `## Operating rules
You are a READ-ONLY research agent. You MUST NOT create, edit, write, or delete any files.
You MUST NOT run any command that modifies the filesystem, make commits, or push to any branch.
You MUST NOT write to pipeline/deals/ or pipeline/accounts/.
You MAY read files, search with Glob/Grep, run read-only commands, and query MCP tools (quality_score).
Return your findings as structured data. The main loop handles all pipeline writes.`

const dealId = args || null

if (!dealId) {
  log('No deal ID provided. Pass the deal ID as args.')
  return { error: 'no_deal_id', status: 'failed' }
}

// Phase 1: Load deal and account context
phase('Load')
log(`Loading deal: ${dealId}`)

const context = await agent(
  `${READ_ONLY_RULES}

You are a deal review agent for Creator OS.

Load the deal record and linked account for deal ID: "${dealId}"

1. Search pipeline/deals/ for a JSON file matching this deal ID.
2. Read the deal record. If not found, return deal_id with stage_ready: false and
   note "deal_not_found" in evidence_gaps.
3. Extract the linked account ID from the deal record.
4. Search pipeline/accounts/ for the linked account. If not found, note
   "account_not_found" in evidence_gaps.
5. Read shared/pipeline-engine.md for the stage-transition rules and evidence requirements.
6. Report what stage the deal is in and what evidence fields are required for that stage.

All data must come from pipeline/ records. Never fabricate deal values or brand names.`,
  { label: 'load-deal', phase: 'Load', schema: DEAL_REVIEW_SCHEMA, agentType: 'deal-reviewer' }
)

if (!context) {
  log('Failed to load deal context.')
  return { deal_id: dealId, error: 'load_failed', status: 'failed' }
}

if (context.evidence_gaps && context.evidence_gaps.includes('deal_not_found')) {
  log(`Deal ${dealId} not found in pipeline/deals/.`)
  return context
}

// Phase 2: Audit — usage rights and exclusivity run in parallel
phase('Audit')
log('Auditing usage rights and exclusivity')

const auditResults = await parallel([
  () => agent(
    `${READ_ONLY_RULES}

You are a deal review agent for Creator OS.

Audit the usage rights for deal: "${dealId}"

Deal context:
${JSON.stringify(context, null, 2)}

1. Read the deal record from pipeline/deals/ for contract terms.
2. Check content ownership: who owns the final deliverable?
3. Check licensing duration: how long can the brand use the content?
4. Check platform restrictions: where may the brand redistribute?
5. Flag any ambiguous or missing clauses for human review.
6. Read protocols/safety.md for FTC disclosure requirements.

All data from pipeline/ records only. Never fabricate deal terms.`,
    { label: 'usage-rights', phase: 'Audit', schema: DEAL_REVIEW_SCHEMA, agentType: 'deal-reviewer' }
  ),
  () => agent(
    `${READ_ONLY_RULES}

You are a deal review agent for Creator OS.

Check for exclusivity conflicts for deal: "${dealId}"

Deal context:
${JSON.stringify(context, null, 2)}

1. Read the deal record to identify the product category and exclusivity terms.
2. Search all JSON files in pipeline/deals/ for active deals in the same category.
3. Check for date range overlaps between this deal's exclusivity window and any
   active deal's window.
4. List every conflict with: conflicting deal ID, category, and overlapping date range.
5. If any conflicts exist, set human_review_required to true.

All data from pipeline/ records only. Never fabricate deal IDs or brand names.`,
    { label: 'exclusivity', phase: 'Audit', schema: DEAL_REVIEW_SCHEMA, agentType: 'deal-reviewer' }
  ),
])

const usageRights = auditResults[0]
const exclusivity = auditResults[1]

// Phase 3: Verify — cross-verify usage rights against exclusivity for contradictions
phase('Verify')
log('Cross-verifying usage rights against exclusivity findings')

const VERIFICATION_SCHEMA = {
  type: 'object',
  properties: {
    verified_claims: { type: 'integer' },
    flagged_claims: { type: 'array', items: { type: 'object', properties: { claim: { type: 'string' }, issue: { type: 'string' }, severity: { type: 'string' } }, required: ['claim', 'issue'] } },
    confidence_valid: { type: 'boolean' },
    minority_report_adequate: { type: 'boolean' },
    cross_verification_issues: { type: 'array', items: { type: 'object', properties: { usage_claim: { type: 'string' }, exclusivity_claim: { type: 'string' }, contradiction: { type: 'string' } } } },
    overall_verdict: { type: 'string', enum: ['pass', 'pass_with_flags', 'fail'] },
  },
  required: ['verified_claims', 'flagged_claims', 'overall_verdict'],
}

const crossVerify = await agent(
  `${READ_ONLY_RULES}

You are a cross-verification agent for Creator OS deal reviews. Your job is to find
CONTRADICTIONS between the usage rights audit and the exclusivity check.

Usage rights findings:
${JSON.stringify(usageRights, null, 2)}

Exclusivity findings:
${JSON.stringify(exclusivity, null, 2)}

Cross-verification checklist:
1. Platform restrictions vs exclusivity scope: if usage rights allow the brand to post on
   Platform X, but an exclusivity conflict exists on Platform X, flag the contradiction.
2. Duration vs date range: if usage rights licensing duration extends beyond the exclusivity
   window of a conflicting deal, flag it.
3. Content ownership vs exclusivity: if ownership transfers to the brand but another active
   deal restricts the same content category, flag it.
4. Source citations: verify each cited pipeline/ file actually exists using Glob.
5. Missing data: if either audit returned null or incomplete findings, flag it.

Default to flagging if uncertain. Contradictions require human review.`,
  { label: 'cross-verify', phase: 'Verify', schema: VERIFICATION_SCHEMA, agentType: 'deal-reviewer' }
)

// Phase 4: Score
phase('Score')
log('Running quality gate scoring')

const mergedReview = {
  deal_id: dealId,
  stage_ready: context.stage_ready,
  evidence_gaps: context.evidence_gaps || [],
  usage_rights: usageRights ? usageRights.usage_rights : null,
  exclusivity_conflicts: exclusivity ? exclusivity.exclusivity_conflicts : [],
  open_flags: [
    ...(context.open_flags || []),
    ...(usageRights ? usageRights.open_flags || [] : []),
    ...(exclusivity ? exclusivity.open_flags || [] : []),
  ],
  human_review_required:
    (context.human_review_required) ||
    (usageRights && usageRights.human_review_required) ||
    (exclusivity && exclusivity.human_review_required) ||
    false,
  sources_consulted: [
    ...(context.sources_consulted || []),
    ...(usageRights ? usageRights.sources_consulted || [] : []),
    ...(exclusivity ? exclusivity.sources_consulted || [] : []),
  ],
  retrieval_gaps: [
    ...(context.retrieval_gaps || []),
    ...(usageRights ? usageRights.retrieval_gaps || [] : []),
    ...(exclusivity ? exclusivity.retrieval_gaps || [] : []),
  ],
}

if (crossVerify && crossVerify.overall_verdict === 'fail') {
  mergedReview.human_review_required = true
  mergedReview.open_flags.push('Cross-verification found contradictions between usage rights and exclusivity')
}

const scored = await agent(
  `${READ_ONLY_RULES}

You are a quality review agent for Creator OS.

Score this deal review against the quality gates:

${JSON.stringify(mergedReview, null, 2)}

1. Read protocols/quality-gates.md for the 9-dimension scoring rubric.
2. Score each dimension 0 to 5 for this deal review artifact.
3. Check: no dimension below 3, Integrity and Safety each 4+, composite 4.0+.
4. Use the quality_score MCP tool if available to get deterministic scoring.
5. If scoring fails, note it in retrieval_gaps but still provide your assessment.

This is a CRM artifact, not content. Focus on: data integrity, completeness of evidence,
proper stage-transition compliance, and safety (FTC, legal boundaries).`,
  { label: 'quality-score', phase: 'Score', schema: DEAL_REVIEW_SCHEMA, agentType: 'deal-reviewer' }
)

if (scored) {
  mergedReview.quality_score = scored.quality_score
  mergedReview.quality_pass = scored.quality_pass
}

log(mergedReview.human_review_required
  ? `Deal review complete. Human review required.`
  : `Deal review complete. No conflicts found.`)

return { ...mergedReview, crossVerify }
