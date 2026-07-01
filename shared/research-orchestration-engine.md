---
file: shared/research-orchestration-engine.md
role: Source of truth for when and how to use subagents for research, how to structure their
  prompts, what schemas to expect back, and how to aggregate their findings. Read by creator-core
  when deciding whether to dispatch inline or fan out to agents, and by every workflow script
  that spawns agents.
load: when the request involves multi-source research, competitive intelligence, citation-chain
  traversal, or any task spanning 3+ sources or platforms
---

# Research Orchestration Engine

## Purpose

Creator OS uses subagents as read-only research tools. Agents gather information, follow citation
chains, query connectors and APIs, and return structured findings. They never create, edit, or
delete files. The main loop aggregates agent output, resolves conflicts, and presents suggestions
to the user. This engine codifies when to spawn agents, how to prompt them, what to expect back,
and how to synthesize findings.

---

## 1. When to spawn agents vs. handle inline

Spawn agents only when the task is large enough to justify the overhead. Small lookups, single-file
reads, and quick keyword checks should be handled inline by the main loop.

### Spawn agents when

- Research spans 3 or more independent sources (e.g., YouTube algorithm docs + TikTok newsroom +
  Pinterest creator hub)
- Multi-platform comparison is needed (e.g., keyword behavior across YouTube, Pinterest, TikTok,
  and Google simultaneously)
- Deep competitor analysis requiring snapshot fetch, metadata extraction, and entity mapping
- Citation-chain traversal: following a source's outlinks to discover child sources at depth 1 or 2
- The task would require the main loop to hold too much intermediate context (e.g., parsing 10
  competitor channel pages and cross-referencing their tag vocabularies)
- Parallel independent research tracks exist (e.g., SEO signals + deal compliance + content gaps
  can be researched simultaneously)

### Handle inline when

- A single cache query, drift check, or staleness report answers the question
- The user asks for a quick keyword lookup or a single-source fact check
- The task involves reading 1 to 2 files and summarizing
- The output is a simple routing decision or classification
- The work can be completed in under 30 seconds of reasoning

### Threshold rule

If the task would require reading from 3 or more distinct sources, or if two or more independent
research tracks could run in parallel, spawn agents. Otherwise, handle inline.

---

## 2. Agent roles and read-only mandate

### Read-only enforcement

Every agent prompt MUST include this instruction block verbatim:

```
## Operating rules
You are a READ-ONLY research agent. You MUST NOT:
- Create, edit, write, or delete any files
- Run any command that modifies the filesystem
- Make commits or push to any branch
- Modify configuration files

You MAY:
- Read files using the Read tool
- Search for files using Glob and Grep
- Run read-only shell commands (git log, git diff, python3 script.py --report)
- Query MCP tools that return data (cache_query, source_staleness, competitor_scan)
- Use WebFetch and WebSearch for external research
- Access connector APIs for data retrieval

Return your findings as structured data. The main loop will decide what to do with them.
```

### Four agent roles

Each role has a defined research scope, engine context, and output schema.

**SEO Researcher** — keyword research, algorithm signals, trend analysis, search intent
classification, topical authority mapping.
- Engines: seo-intelligence-engine, platform-engine, web-intel-engine
- Protocols: no-fabrication, research-citation
- MCP tools: cache_query, source_staleness
- External: WebSearch, WebFetch for live trend data

**Competitor Analyst** — competitive intelligence, hidden metadata extraction, entity mapping,
content gap identification, keyword gap analysis.
- Engines: web-intel-engine, seo-intelligence-engine
- Protocols: no-fabrication, research-citation
- MCP tools: competitor_scan, cache_query, source_staleness
- External: WebFetch for competitor page analysis

**Content Writer** — script drafting, hook writing, title generation, caption writing, pin copy.
- Engines: brand-engine, voice-engine, audience-engine, platform-engine, adaptation-engine
- Protocols: all five (quality-gates, no-fabrication, safety, research-citation, formatting-metadata)
- MCP tools: cache_query, quality_score
- Voice rules: load voice-profile.local.json context into the prompt

**Deal Reviewer** — partnership evaluation, stage evidence checking, usage rights, exclusivity,
deal compliance.
- Engines: pipeline-engine, brand-engine
- Protocols: no-fabrication, safety, quality-gates
- MCP tools: quality_score
- Data: reads from pipeline/deals/ and pipeline/accounts/ only

---

## 3. Structured output schemas

Every agent must return structured JSON conforming to a defined schema. The Workflow tool's
`schema` option enforces this at the tool-call layer so the model retries on mismatch. Inline
agent calls (via the Agent tool) should request the same schema shape in the prompt.

### SEO research result schema

```json
{
  "type": "object",
  "properties": {
    "keywords": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "keyword": { "type": "string" },
          "intent": { "type": "string", "enum": ["informational", "navigational", "commercial", "transactional"] },
          "platform_fit": {
            "type": "object",
            "additionalProperties": { "type": "string", "enum": ["strong", "moderate", "weak", "unknown"] }
          },
          "competition_estimate": { "type": "string" },
          "source": { "type": "string" }
        },
        "required": ["keyword", "intent", "source"]
      }
    },
    "trends": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "signal": { "type": "string" },
          "direction": { "type": "string", "enum": ["rising", "flat", "declining", "unknown"] },
          "confidence": { "type": "string", "enum": ["high", "medium", "low"] },
          "source": { "type": "string" }
        },
        "required": ["signal", "direction", "source"]
      }
    },
    "sources_consulted": { "type": "array", "items": { "type": "string" } },
    "retrieval_gaps": { "type": "array", "items": { "type": "string" } },
    "confidence": { "type": "string", "enum": ["high", "medium", "low"] }
  },
  "required": ["keywords", "sources_consulted", "retrieval_gaps", "confidence"]
}
```

### Competitor analysis result schema

```json
{
  "type": "object",
  "properties": {
    "competitor": {
      "type": "object",
      "properties": {
        "name": { "type": "string" },
        "platform": { "type": "string" },
        "url": { "type": "string" }
      },
      "required": ["name", "platform"]
    },
    "content_pillars": { "type": "array", "items": { "type": "string" } },
    "video_tags": { "type": "array", "items": { "type": "string" } },
    "hashtags": { "type": "array", "items": { "type": "string" } },
    "entity_map": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "entity": { "type": "string" },
          "type": { "type": "string" },
          "frequency": { "type": "integer" },
          "niche_fit": { "type": "string", "enum": ["high", "medium", "low"] }
        },
        "required": ["entity", "type"]
      }
    },
    "keyword_gaps": { "type": "array", "items": { "type": "string" } },
    "format_gaps": { "type": "array", "items": { "type": "string" } },
    "sources_consulted": { "type": "array", "items": { "type": "string" } },
    "retrieval_gaps": { "type": "array", "items": { "type": "string" } },
    "confidence": { "type": "string", "enum": ["high", "medium", "low"] }
  },
  "required": ["competitor", "sources_consulted", "retrieval_gaps", "confidence"]
}
```

### Content draft result schema

```json
{
  "type": "object",
  "properties": {
    "content_type": { "type": "string" },
    "platform": { "type": "string" },
    "hook_variants": { "type": "array", "items": { "type": "string" } },
    "title_options": { "type": "array", "items": { "type": "string" } },
    "script_sections": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "section_name": { "type": "string" },
          "content": { "type": "string" },
          "b_roll_notes": { "type": "string" }
        },
        "required": ["section_name", "content"]
      }
    },
    "captions": {
      "type": "object",
      "additionalProperties": { "type": "string" }
    },
    "self_assessment": {
      "type": "object",
      "properties": {
        "voice_adherence": { "type": "string", "enum": ["strong", "moderate", "weak"] },
        "formatting_clean": { "type": "boolean" },
        "flagged_issues": { "type": "array", "items": { "type": "string" } }
      }
    },
    "retrieval_gaps": { "type": "array", "items": { "type": "string" } }
  },
  "required": ["content_type", "retrieval_gaps"]
}
```

### Deal review result schema

```json
{
  "type": "object",
  "properties": {
    "deal_id": { "type": "string" },
    "stage_ready": { "type": "boolean" },
    "evidence_gaps": { "type": "array", "items": { "type": "string" } },
    "usage_rights": {
      "type": "object",
      "properties": {
        "ownership": { "type": "string" },
        "duration": { "type": "string" },
        "platform_restrictions": { "type": "array", "items": { "type": "string" } },
        "ambiguous_clauses": { "type": "array", "items": { "type": "string" } }
      }
    },
    "exclusivity_conflicts": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "conflicting_deal_id": { "type": "string" },
          "category": { "type": "string" },
          "date_range": { "type": "string" }
        },
        "required": ["conflicting_deal_id", "category"]
      }
    },
    "quality_score": { "type": "number" },
    "quality_pass": { "type": "boolean" },
    "open_flags": { "type": "array", "items": { "type": "string" } },
    "human_review_required": { "type": "boolean" },
    "sources_consulted": { "type": "array", "items": { "type": "string" } },
    "retrieval_gaps": { "type": "array", "items": { "type": "string" } }
  },
  "required": ["deal_id", "stage_ready", "human_review_required", "retrieval_gaps"]
}
```

---

## 4. Recursive extraction protocol

When an agent needs to follow a chain of citations or references to gather complete information,
it follows the same depth-limited, authority-filtered model as `tools/traversal_engine.py`.

### Depth limits

- **Depth 0:** Direct source (the URL or file the agent was asked to research)
- **Depth 1:** Sources cited by or linked from the depth-0 source
- **Depth 2:** Sources cited by depth-1 sources (maximum automatic depth)
- **Depth 3+:** Never traversed automatically. Agent reports the unvisited URLs in
  `retrieval_gaps` for operator review.

### Authority filter

Agents only follow links to domains on the authority allowlist defined in
`tools/traversal_engine.py`. Links to unknown domains are reported in `retrieval_gaps` but not
followed. The allowlist includes platform-official docs (support.google.com,
developers.google.com, creators.tiktok.com, business.pinterest.com), legal (ftc.gov), SEO trade
press (moz.com, ahrefs.com/blog), niche editorial (thespruce.com, apartmenttherapy.com), and
industry benchmarks (influencermarketinghub.com, later.com).

### Deduplication

Agents track visited URLs within each research session to avoid re-fetching the same page.
Normalized URLs (lowercase domain, no UTM parameters, no trailing slash) are compared for
deduplication.

### Operator approval

Agents never add sources to `canonical-sources/source-registry.json` directly. They report
discovered sources in their structured output under a `discovered_sources` array. The main loop
presents these to the operator, who uses `tools/traversal_engine.py --accept <url>` to approve
each one.

---

## 5. Connector and API access

Agents have access to the same MCP tools and connectors as the main loop for read-only research.
The connector registry (`shared/connectors/connectors.json`) determines which tools are available.

### Available to all agents

- `cache_query` — offline FTS5 keyword and entity cache
- `source_staleness` — canonical source freshness report
- `drift_check` — sync guard status
- `get_capabilities` — current feature flag state
- `get_stats_tools` — available statistical computation tools

### Available to specific roles

| Tool | SEO Researcher | Competitor Analyst | Content Writer | Deal Reviewer |
|---|---|---|---|---|
| `competitor_scan` | | Yes | | |
| `quality_score` | | | Yes | Yes |
| `add_competitor` | | Yes | | |
| `configure_tool` | | | | |
| WebSearch / WebFetch | Yes | Yes | | |

### Connector-provided evidence

When connectors are enabled (Google Workspace, Microsoft 365, platform APIs), agents may query
them for research data:
- Gmail/Outlook: read brand pitch emails for deal context (deal-reviewer agent)
- Google Calendar/Outlook Calendar: check content calendar for scheduling conflicts
- Google Sheets/Excel: read analytics exports for statistical analysis
- YouTube Data API: retrieve channel stats, video metadata
- Instagram Graph API: retrieve insights, business discovery
- TikTok Display API: retrieve public video metadata

Agents must not write to any connected service. All connector interactions are read-only.

---

## 6. Information aggregation

After agents return their structured results, the main loop aggregates findings before presenting
to the user. This is never delegated to another agent.

### Aggregation steps

1. **Collect:** Gather all agent results. Filter out null results (agents that failed or were
   skipped).

2. **Validate:** Check each result against its schema. Discard malformed results and note them
   in a warning to the user.

3. **Deduplicate:** When multiple agents surface the same finding (same keyword, same competitor,
   same entity), keep the version with the highest confidence and the most specific source
   attribution.

4. **Resolve conflicts:** When agents disagree on a classification (e.g., one says a keyword's
   intent is "informational" and another says "commercial"):
   - If one agent has a higher-confidence source (T1 vs. T3), prefer it.
   - If sources are equal tier, present both interpretations to the user with the evidence for
     each.
   - Never silently discard a minority finding — record it as a `minority_report`.

5. **Synthesize:** Merge deduplicated, conflict-resolved findings into a coherent recommendation.
   Organize by the user's original question, not by which agent found what.

6. **Attribute:** Every finding in the final output includes provenance: which agent found it,
   from which source, at what confidence level. The user should be able to trace any claim back
   to its origin.

### Provenance format

```json
{
  "finding": "dark moody fall mantel has strong YouTube search intent",
  "found_by": "seo-researcher",
  "source": "YouTube autocomplete + Google Trends",
  "confidence": "high",
  "corroborated_by": ["competitor-analyst entity map"]
}
```

---

## 7. Quality gates on agent output

Agent output passes through the same quality standards as any Creator OS artifact.

### Completeness check

The main loop verifies that every required schema field is populated. Missing fields trigger a
note in the output but do not block the aggregation — the gap is surfaced to the user.

### Source attribution

Every factual claim must include a `source` field. Claims without source attribution are labeled
`[unattributed — verify independently]` in the aggregated output.

### Confidence labeling

All agent output uses the three-level confidence scale:
- **high:** from a T1 official source (platform docs, API response, official blog)
- **medium:** from a T2 source (industry reports, reputable trade press) or corroborated by
  multiple T3 sources
- **low:** from a T3 source (blog post, community forum, single third-party analysis) without
  corroboration

### Fabrication detection

If an agent returns data that cannot be traced to a source (e.g., specific view counts, exact
subscriber numbers, or precise CPM rates without attribution), the main loop labels the data
`[unverified — source not provided]` and does not present it as fact.

---

## 8. Prompt construction patterns

### Context injection

Agent prompts should inject only the engine and protocol content relevant to the agent's role.
Do not load all engines into every agent — follow the same scoping rules as spoke engine loading
in creator-core.

Template structure:

```
You are a [role name] research agent for Creator OS.

## Your task
[specific research question or objective]

## Operating rules
[read-only mandate block from Section 2]

## Context
[relevant engine excerpts — only the sections the agent needs]
[relevant protocol rules — abbreviated to the rules that apply]

## Data sources available
[list of MCP tools and connectors available for this research]

## Output format
Return a single JSON object conforming to this schema:
[schema from Section 3]

Focus on [specific guidance for this research task].
Do not fabricate any data. Use null for unknown values.
Cite your sources in the sources_consulted array.
List anything you could not find in retrieval_gaps.
```

### Context size management

Keep agent prompts under 4,000 tokens of injected context. If an engine is too large to include
in full, extract only the sections the agent needs. For example, a competitor analyst does not
need the seasonal lead times table from seo-intelligence-engine.md — only the algorithm signal
rankings and the entity SEO section.

---

## 9. Workflow integration

This engine is consumed by:
- `skills/creator-core/SKILL.md` — decides when to recommend agent dispatch vs. inline handling
- `.claude/workflows/*.js` — executable workflow scripts that spawn agents
- `.claude/agents/*.md` — agent role definitions that reference the schemas and rules here
- `docs/ARCHITECTURE.md` — references this engine in the agent orchestration section
