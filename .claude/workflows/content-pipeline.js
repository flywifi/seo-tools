export const meta = {
  name: 'content-pipeline',
  description: 'Multi-step content production from keyword research through quality review',
  phases: [
    { title: 'Research', detail: 'Keyword research and search intent analysis' },
    { title: 'Draft', detail: 'Script, hooks, titles, and captions' },
    { title: 'Review', detail: 'Quality gate scoring and revision' },
  ],
}

const SEO_SCHEMA = {
  type: 'object',
  properties: {
    keywords: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          keyword: { type: 'string' },
          intent: { type: 'string' },
          platform_fit: { type: 'object' },
          competition_estimate: { type: 'string' },
          source: { type: 'string' },
        },
        required: ['keyword', 'intent', 'source'],
      },
    },
    trends: { type: 'array', items: { type: 'object' } },
    sources_consulted: { type: 'array', items: { type: 'string' } },
    retrieval_gaps: { type: 'array', items: { type: 'string' } },
    confidence: { type: 'string', enum: ['high', 'medium', 'low'] },
  },
  required: ['keywords', 'sources_consulted', 'retrieval_gaps', 'confidence'],
}

const CONTENT_SCHEMA = {
  type: 'object',
  properties: {
    content_type: { type: 'string' },
    platform: { type: 'string' },
    hook_variants: { type: 'array', items: { type: 'string' } },
    title_options: { type: 'array', items: { type: 'string' } },
    script_sections: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          section_name: { type: 'string' },
          content: { type: 'string' },
          b_roll_notes: { type: 'string' },
        },
        required: ['section_name', 'content'],
      },
    },
    captions: { type: 'object' },
    self_assessment: {
      type: 'object',
      properties: {
        voice_adherence: { type: 'string' },
        formatting_clean: { type: 'boolean' },
        flagged_issues: { type: 'array', items: { type: 'string' } },
      },
    },
    retrieval_gaps: { type: 'array', items: { type: 'string' } },
  },
  required: ['content_type', 'retrieval_gaps'],
}

const REVIEW_SCHEMA = {
  type: 'object',
  properties: {
    composite_score: { type: 'number' },
    dimension_scores: { type: 'object' },
    pass: { type: 'boolean' },
    failing_dimensions: { type: 'array', items: { type: 'string' } },
    revision_notes: { type: 'array', items: { type: 'string' } },
  },
  required: ['composite_score', 'pass'],
}

const topic = args || 'moody vintage home decor video'
const READ_ONLY_RULES = `## Operating rules
You are a READ-ONLY research agent. You MUST NOT create, edit, write, or delete any files.
You MUST NOT run any command that modifies the filesystem, make commits, or push to any branch.
You MAY read files, search with Glob/Grep, run read-only commands, and query MCP tools.
Return your findings as structured data.`

// Phase 1: Research
phase('Research')
log(`Starting keyword research for: ${topic}`)

const research = await agent(
  `${READ_ONLY_RULES}

You are an SEO research agent for Creator OS (moody-vintage home decor / DIY niche, YouTube creator).

Research keywords and search intent for this topic: "${topic}"

1. Read shared/seo-intelligence-engine.md for algorithm signals and SERP feature map.
2. Read shared/platform-engine.md for platform-specific format rules.
3. Use the cache_query MCP tool to search the offline keyword cache for related terms.
4. Use WebSearch to check current trends for this topic.
5. Classify search intent for each keyword found.
6. Note seasonal timing if relevant (read the seasonal lead times in seo-intelligence-engine.md).

Never fabricate volume numbers. Label all estimates [estimated]. Cite every source.`,
  { label: 'seo-research', phase: 'Research', schema: SEO_SCHEMA, agentType: 'seo-researcher' }
)

if (!research) {
  log('SEO research agent returned no results. Proceeding with topic only.')
}

const keywordBrief = research
  ? research.keywords.map(k => `${k.keyword} (${k.intent})`).join(', ')
  : topic

// Phase 2: Draft
phase('Draft')
log(`Drafting content using keyword brief: ${keywordBrief}`)

const draft = await agent(
  `${READ_ONLY_RULES}

You are a content drafting agent for Creator OS. The creator is Alexandra (Alex) Slason,
moody-vintage home decor / DIY niche, Orlando FL.

Draft a video script for this topic: "${topic}"
Keyword brief: ${keywordBrief}

1. Read shared/brand-engine.md and shared/voice-engine.md for voice and brand context.
2. Read pipeline/user-context/voice-profile.local.json if it exists for Alex's real phrases.
3. Write 3 to 5 hook variants that open with the object or the problem.
4. Write 3 to 5 title options incorporating the primary keyword.
5. Write script sections with b-roll notes.
6. Write platform-specific captions (YouTube description, Pinterest pin text).
7. Self-assess: voice adherence, formatting (no em dashes, ranges with "to"), flagged issues.

Voice rules: no em dashes, no opener exclamations, no filler affirmations, no passive CTAs,
no generic aesthetic vocab. Open with the object. Anchor time and budget early.`,
  { label: 'content-draft', phase: 'Draft', schema: CONTENT_SCHEMA, agentType: 'content-writer' }
)

if (!draft) {
  log('Content draft agent returned no results.')
  return { research, draft: null, review: null, status: 'draft_failed' }
}

// Phase 3: Review
phase('Review')
log('Running quality review on draft')

let currentDraft = draft
let review = null
let revisionCount = 0
const MAX_REVISIONS = 2

while (revisionCount <= MAX_REVISIONS) {
  review = await agent(
    `${READ_ONLY_RULES}

You are a quality review agent for Creator OS.

Score this content draft against the 9-dimension quality rubric in protocols/quality-gates.md.

Draft to review:
${JSON.stringify(currentDraft, null, 2)}

1. Read protocols/quality-gates.md for the scoring rubric.
2. Score each of the 9 dimensions 0 to 5: Integrity, Accuracy, Brand and Aesthetic Alignment,
   Audience Fit, Governance, User Intent, Accessibility, Professional Quality, Safety.
3. Check: no dimension below 3, Integrity and Safety each 4+, composite average 4.0+.
4. If the draft fails, provide specific revision notes for each failing dimension.
5. Check formatting: no em dashes in user-facing text, ranges use "to".

Return the composite score, per-dimension scores, pass/fail, and revision notes.`,
    { label: `quality-review-${revisionCount}`, phase: 'Review', schema: REVIEW_SCHEMA }
  )

  if (!review || review.pass) break

  if (revisionCount < MAX_REVISIONS) {
    log(`Quality gate failed (${review.composite_score}). Revision ${revisionCount + 1} of ${MAX_REVISIONS}.`)
    currentDraft = await agent(
      `${READ_ONLY_RULES}

You are a content revision agent for Creator OS. Revise this draft based on quality review feedback.

Original draft:
${JSON.stringify(currentDraft, null, 2)}

Review feedback:
${JSON.stringify(review, null, 2)}

Fix each failing dimension. Maintain Alex's voice (no em dashes, object-first openings,
time/budget anchors, normalize imperfection). Do not add new content beyond what fixes the
failing dimensions.`,
      { label: `revision-${revisionCount + 1}`, phase: 'Review', schema: CONTENT_SCHEMA, agentType: 'content-writer' }
    )
    if (currentDraft) {
      revisionCount++
    } else {
      break
    }
  } else {
    revisionCount++
  }
}

log(review && review.pass
  ? `Quality gate passed (${review.composite_score})`
  : `Quality gate did not pass after ${MAX_REVISIONS} revisions`)

return {
  topic,
  research,
  draft: currentDraft,
  review,
  revisions: revisionCount,
  status: review && review.pass ? 'approved' : 'needs_human_review',
}
