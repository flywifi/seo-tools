export const meta = {
  name: 'seasonal-planning',
  description: 'Build a seasonal content calendar from trend data and keyword opportunities',
  phases: [
    { title: 'Trends', detail: 'Check seasonal trends and rising topics' },
    { title: 'Keywords', detail: 'Expand trends into keyword targets' },
    { title: 'Calendar', detail: 'Map keywords to publish dates with hub-cluster structure' },
  ],
}

const TREND_SCHEMA = {
  type: 'object',
  properties: {
    season: { type: 'string' },
    rising_topics: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          topic: { type: 'string' },
          direction: { type: 'string', enum: ['rising', 'flat', 'declining', 'unknown'] },
          peak_window: { type: 'string' },
          source: { type: 'string' },
        },
        required: ['topic', 'direction', 'source'],
      },
    },
    sources_consulted: { type: 'array', items: { type: 'string' } },
    retrieval_gaps: { type: 'array', items: { type: 'string' } },
    confidence: { type: 'string', enum: ['high', 'medium', 'low'] },
  },
  required: ['season', 'rising_topics', 'sources_consulted', 'confidence'],
}

const KEYWORD_SCHEMA = {
  type: 'object',
  properties: {
    keywords: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          keyword: { type: 'string' },
          intent: { type: 'string' },
          expansion_method: { type: 'string' },
          niche_relevance: { type: 'string', enum: ['high', 'medium', 'low'] },
          source: { type: 'string' },
        },
        required: ['keyword', 'intent', 'source'],
      },
    },
    sources_consulted: { type: 'array', items: { type: 'string' } },
    retrieval_gaps: { type: 'array', items: { type: 'string' } },
  },
  required: ['keywords', 'sources_consulted'],
}

const CALENDAR_SCHEMA = {
  type: 'object',
  properties: {
    entries: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          topic: { type: 'string' },
          primary_keyword: { type: 'string' },
          cluster_keywords: { type: 'array', items: { type: 'string' } },
          publish_date: { type: 'string' },
          content_format: { type: 'string' },
          hub_or_cluster: { type: 'string', enum: ['hub', 'cluster'] },
          platform_targets: { type: 'array', items: { type: 'string' } },
          notes: { type: 'string' },
        },
        required: ['topic', 'primary_keyword', 'publish_date', 'content_format', 'hub_or_cluster'],
      },
    },
    season: { type: 'string' },
    lead_time_notes: { type: 'string' },
    retrieval_gaps: { type: 'array', items: { type: 'string' } },
  },
  required: ['entries', 'season'],
}

const READ_ONLY_RULES = `## Operating rules
You are a READ-ONLY research agent. You MUST NOT create, edit, write, or delete any files.
You MUST NOT run any command that modifies the filesystem, make commits, or push to any branch.
You MAY read files, search with Glob/Grep, run read-only commands, query MCP tools, and use WebFetch/WebSearch.
Return your findings as structured data.`

const season = args || 'fall'

// Phase 1: Trend check
phase('Trends')
log(`Checking seasonal trends for: ${season}`)

const trends = await agent(
  `${READ_ONLY_RULES}

You are an SEO research agent for Creator OS (moody-vintage home decor / DIY niche).

Research seasonal trends for the "${season}" season in the home decor and DIY niche.

1. Read shared/seo-intelligence-engine.md for seasonal SEO lead times and peak search windows.
2. Read canonical-sources/keyword-library/moody-vintage.json for existing aesthetic keywords.
3. Use WebSearch to check current trend signals for ${season} home decor topics.
4. Use the cache_query MCP tool to find related terms in the offline cache.
5. Identify 10 to 15 rising topics with their peak search windows.
6. Note the publish-by dates (YouTube and Pinterest have different lead times).

Cite every source. Never fabricate trend data. Label direction as rising/flat/declining/unknown.`,
  { label: 'trend-check', phase: 'Trends', schema: TREND_SCHEMA, agentType: 'seo-researcher' }
)

if (!trends) {
  log('Trend check failed.')
  return { season, trends: null, keywords: null, calendar: null, status: 'trend_check_failed' }
}

log(`Found ${trends.rising_topics.length} rising topics. Expanding keywords.`)

// Phase 2: Keyword expansion
phase('Keywords')

const topicList = trends.rising_topics.map(t => t.topic).join(', ')

const keywords = await agent(
  `${READ_ONLY_RULES}

You are an SEO research agent for Creator OS (moody-vintage home decor / DIY niche).

Expand these seasonal topics into publishable keyword targets: ${topicList}

1. Read shared/seo-intelligence-engine.md for the long-tail expansion methodology.
2. For each topic, generate 3 to 5 long-tail keyword variations using:
   - YouTube autocomplete patterns
   - "People Also Ask" patterns
   - Related search patterns
   - Forum and community question patterns
3. Classify each keyword by search intent.
4. Rate niche relevance (high/medium/low) based on the creator's 5 pillars.
5. Use the cache_query MCP tool to check for existing coverage.

Never fabricate volume estimates. All competition data labeled [estimated].`,
  { label: 'keyword-expand', phase: 'Keywords', schema: KEYWORD_SCHEMA, agentType: 'seo-researcher' }
)

if (!keywords) {
  log('Keyword expansion failed.')
  return { season, trends, keywords: null, calendar: null, status: 'keyword_expansion_failed' }
}

log(`${keywords.keywords.length} keywords generated. Building calendar.`)

// Phase 3: Calendar mapping with hub-cluster structure
phase('Calendar')

const calendarInput = {
  season,
  trends: trends.rising_topics,
  keywords: keywords.keywords,
}

const calendar = await agent(
  `${READ_ONLY_RULES}

You are a content planning agent for Creator OS (moody-vintage home decor / DIY niche).

Build a seasonal content calendar from these trend signals and keywords:

${JSON.stringify(calendarInput, null, 2)}

1. Read shared/seo-intelligence-engine.md for the topical authority model (hub + cluster pattern)
   and seasonal lead times.
2. Read shared/platform-engine.md for platform-specific posting rules and format specs.
3. Read pipeline/user-context/content-calendar.local.json if it exists to avoid date conflicts.
4. Group keywords into 2 to 4 hub topics, each with 3 to 5 cluster posts.
5. Assign publish dates respecting lead times:
   - YouTube: publish 2 to 4 weeks before peak search
   - Pinterest: publish 4 to 6 weeks before peak (pins take longer to index)
6. For each entry: topic, primary keyword, cluster keywords, publish date, content format
   (long-form, Short, pin, Reel), hub-or-cluster role, platform targets.
7. The creator's posting cadence: 1 long-form + 3 to 5 Shorts + 1 to 3 pins per project.

Use "to" for all ranges. Never fabricate dates or volume data.`,
  { label: 'calendar-build', phase: 'Calendar', schema: CALENDAR_SCHEMA }
)

return {
  season,
  trends,
  keywords,
  calendar,
  status: calendar ? 'complete' : 'calendar_build_failed',
}
