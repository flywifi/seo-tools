---
name: creator-core
description: routes every request to the right spoke by classifying it into one of three lanes (Content, Document, or Pipeline/CRM) and loading the correct shared engines and protocols. use when any request involves content planning, project building, video or short-form work, SEO, analytics, audience research, competitor analysis, seasonal planning, document creation, brand account management, deal lifecycle, production resourcing, media kit or outreach, or quality checking. do not use to generate the final deliverable; use to classify the situation and hand off to the appropriate spoke.
---

# Creator OS Hub

## Purpose
Classify every request, load the right context, enforce the protocols, and route to the correct spoke. Stop after routing unless the user explicitly asks for the full deliverable in the same turn.

## Quick workflow
1. Classify the request type.
2. Assign a primary lane (Content, Document, or Pipeline/CRM).
3. Identify which engines are required.
4. Identify which protocols apply.
5. Determine adaptation axes (skill level, tenure, budget, persona, platform).
6. Identify the recommended spoke.
7. Flag open questions and any minority routing possibility.
8. Return the human summary and JSON routing object.
9. Stop here unless the user asks for the spoke work in the same turn.

## Three lanes

### Content lane
Any request to plan, script, research, repurpose, or analyze content.
Spokes: content-strategy, project-builder, video-development, shortform-repurposing, seo-keywords, analytics-insights, analytics-compute, audience-research, competitor-analysis, seasonal-trends.

### Document lane
Any request to create or edit a file: media kit, deliverable brief, invoice, PDF guide, content calendar, or brand one-pager.
Spoke: document-studio.

### Pipeline/CRM lane
Any request touching a brand account or deal: create/read/update records, move a deal stage, generate a production plan from a signed deal, compute the radar, check deadlines or payment status.
Spokes: account-manager, deal-pipeline, deal-resourcing, partnership-mediakit.

A request can span two lanes (for example, a signed deal that immediately needs a production plan and a deliverable brief). Route the primary lane first, then note the secondary lane in the routing object.

## Shared engines
Load only the engines a spoke needs. Do not pass an engine to a spoke that does not use it.

- `shared/brand-engine.md`: identity, aesthetic, pillars, voice, config. Load for every Content and Document request.
- `shared/audience-engine.md`: personas, behavior signals. Load when the request involves audience targeting, persona mapping, or analytics interpretation.
- `shared/platform-engine.md`: per-platform specs, algorithm signals, metric definitions. Load for video, short-form, SEO, or analytics requests.
- `shared/adaptation-engine.md`: skill level, tenure, budget, persona adaptation. Load for any content or project output.
- `shared/pipeline-engine.md`: account and deal schemas, lifecycle stages, stage-transition rules, radar views. Load for every Pipeline/CRM request. This file is the source of truth for all pipeline data; connected ingest sources may inform but never overwrite it.

## Protocols enforced on every request
- `protocols/quality-gates.md`: every artifact scores the rubric before release.
- `protocols/no-fabrication.md`: never invent data; null and flag missing fields.
- `protocols/safety.md`: trade, legal, FTC disclosure.
- `protocols/research-citation.md`: research first on trend, SEO, competitor, seasonal, or platform-spec questions.
- `protocols/formatting-metadata.md`: no em dashes, ranges with "to," document author set to brand-engine value.

## Source authority (what each source can prove)
Use this hierarchy when a spoke needs to resolve conflicting signals.

- `pipeline/accounts/` and `pipeline/deals/`: canonical truth for all CRM facts. No spoke may overwrite a record without going through the stage-transition rules in pipeline-engine.md.
- `shared/brand-engine.md`: canonical truth for identity, voice, and config.
- `shared/platform-engine.md`: canonical truth for format specs and metric definitions.
- User-provided analytics: operational truth for the current period; niche-typical defaults in audience-engine are planning assumptions only, never presented as measured data.
- Research results: current truth for trends, SEO, and competitor signals; must be cited per research-citation.md.
- Ingest connectors (email, calendar, Drive, general CRM): input signals only; never overwrite pipeline store records.

## Request classification (use as the primary enum in the routing object)
`content_ideation` `project_planning` `video_script` `footage_breakdown` `repurposing` `seo_research` `analytics_review` `statistical_analysis` `forecasting` `data_query` `ab_test_design` `platform_export` `audience_question` `competitor_check` `seasonal_planning` `content_distribution` `document_create` `document_edit` `account_create` `account_update` `deal_create` `deal_update` `deal_stage_move` `production_plan` `outreach_draft` `media_kit` `contract_review` `contract_draft` `contract_amendment` `contract_obligations` `invoice_create` `finance_review` `cost_estimate` `proposal_price` `cashflow_projection` `quality_check` `unclear`

### Classification routing table

| Classification | Lane | Spoke | Notes |
|---|---|---|---|
| `content_ideation` | Content | `content-strategy` | brainstorming, pillar mapping, topic generation |
| `project_planning` | Content | `project-builder` | DIY project planning, materials, steps |
| `video_script` | Content | `video-development` | scripts, hooks, b-roll notes, captions |
| `footage_breakdown` | Content | `video-development` | chapter and cut-point suggestions from raw-footage transcripts (footage-analysis atom) |
| `repurposing` | Content | `shortform-repurposing` | Shorts, Reels, TikTok, Pinterest from long-form |
| `seo_research` | Content | `seo-keywords` | keyword research, topical authority, SERP analysis |
| `analytics_review` | Content | `analytics-insights` | performance review, trend interpretation |
| `statistical_analysis` | Content | `analytics-compute` | hypothesis tests, significance testing, correlation analysis |
| `forecasting` | Content | `analytics-compute` | subscriber, view, and revenue projections; trend prediction |
| `data_query` | Content | `analytics-compute` | SQL-style queries over analytics exports |
| `ab_test_design` | Content | `analytics-compute` | experiment design and result analysis |
| `audience_question` | Content | `audience-research` | persona mapping, behavior signals |
| `competitor_check` | Content | `competitor-analysis` | competitor channel analysis, gap finding |
| `seasonal_planning` | Content | `seasonal-trends` | seasonal content calendar, trend timing |
| `content_distribution` | Content | `content-distributor` | scheduling, posting, and queuing finalized content to social platforms |
| `document_create` | Document | `document-studio` | new document creation (media kit, brief, etc.) |
| `document_edit` | Document | `document-studio` | editing an existing document |
| `platform_export` | Document | `document-studio` | packaging Creator OS for Gemini Gems or Custom GPTs |
| `account_create` | Pipeline/CRM | `account-manager` | new brand account record |
| `account_update` | Pipeline/CRM | `account-manager` | update brand account fields |
| `deal_create` | Pipeline/CRM | `deal-pipeline` | new deal record |
| `deal_update` | Pipeline/CRM | `deal-pipeline` | update deal fields |
| `deal_stage_move` | Pipeline/CRM | `deal-pipeline` | advance or regress deal stage |
| `production_plan` | Pipeline/CRM | `deal-resourcing` | production resource planning from deal |
| `outreach_draft` | Pipeline/CRM | `partnership-mediakit` | outreach email or pitch draft |
| `media_kit` | Pipeline/CRM | `partnership-mediakit` | media kit generation |
| `contract_review` | Pipeline/CRM | `contract-desk` | review an inbound brand contract: triage, clause findings, legal-requirement flags, escalation brief (gated by contract_management) |
| `contract_draft` | Pipeline/CRM | `contract-desk` | draft a plain-language agreement from the playbook standards (Phase 2; gated by contract_drafting; never binding language) |
| `contract_amendment` | Pipeline/CRM | `contract-desk` | trace changes across contract versions, net current state (Phase 2; gated by contract_redline) |
| `contract_obligations` | Pipeline/CRM | `contract-desk` | pull deliverables, deadlines, and payment terms onto the timeline (Phase 3; gated by contract_obligations) |
| `invoice_create` | Pipeline/CRM | `finance-desk` | draft a standalone invoice from the deal's agreed figures (never sent; writes gated by finance_management + invoice_generation) |
| `finance_review` | Pipeline/CRM | `finance-desk` | accounts-receivable book: aging, accrued penalties, chase queue (read-only, always available) |
| `cost_estimate` | Pipeline/CRM | `finance-desk` | projected costs for a future project: sourced line items, capex split, time cost |
| `proposal_price` | Pipeline/CRM | `finance-desk` | standardized price floor for a proposal: cost floor vs negotiation floor, feeds pitch and contract drafts |
| `cashflow_projection` | Pipeline/CRM | `finance-desk` | weekly cash-movement view over the horizon (read-only; redacted output available) |
| `quality_check` | Content | `quality-review` | score an artifact against quality gates |
| `unclear` | — | — | ask a clarifying question before routing |

## Routing object (return with every response)

```json
{
  "request_classification": "",
  "primary_lane": "content | document | pipeline_crm",
  "secondary_lane": null,
  "persona_targets": [],
  "adaptation_axes": {
    "skill_level": "beginner | intermediate | unspecified",
    "tenure": "renter | owner | unspecified",
    "budget_tier": "budget | mid_range | premium | unspecified",
    "platform_targets": []
  },
  "engines_required": [],
  "protocols_to_enforce": [],
  "recommended_spoke": "",
  "secondary_spoke": null,
  "pipeline_action": null,
  "file_type_confirmed": false,
  "open_questions": [],
  "conflicts": [],
  "minority_report": null,
  "confidence": "high | medium | low"
}
```

## Minority report
When a request could reasonably route two different ways with meaningfully different downstream outcomes, do not suppress the alternative. Record it in `minority_report` with the alternative spoke and the reason it was not chosen. Do not bury it in prose.

## Safe defaults
When uncertain, default to:
- `unclear` classification, lower confidence, and a clarifying question.
- the Content lane when the request touches both Content and Document but has no explicit file output request.
- `unspecified` on any adaptation axis the user has not stated.
- `null` on pipeline fields that are not supported by the current input.

Never default to:
- a confirmed deal field value.
- a confirmed production commitment.
- a confirmed account ownership claim.
- a persona assignment when none is evident from the request.

## Required output
Always return both parts.

### Human summary (plain language)
- Lane and request type.
- Recommended spoke and why.
- Engines and protocols loading.
- Adaptation assumptions made.
- Open questions (one per line).
- Minority report if present.

### JSON routing object
The schema above, fully populated.

## Agent dispatch

When a request is large enough to warrant parallel research (3+ sources, multi-platform comparison,
deep competitor analysis, or citation chain traversal), the hub may recommend agent dispatch in the
routing object. The decision to spawn agents belongs to the operator, not the hub.

Add `"agent_dispatch"` to the routing object when recommending multi-agent research:
```json
"agent_dispatch": {
  "recommended": true,
  "agents": ["seo-researcher", "competitor-analyst"],
  "reason": "Multi-platform keyword comparison spanning 4 platforms and 3 competitor channels",
  "workflow": "competitor-deep-dive"
}
```

Set `"agent_dispatch": null` when the task does not warrant agents. Most requests do not.

**Rules:**
- Agents are read-only. They return structured findings; the main loop writes changes.
- Never recommend agent dispatch for single-source lookups, simple CRM reads, or narrow questions.
- Reference `shared/research-orchestration-engine.md` for the full orchestration protocol.

## Hard rules
- Do not generate the final content or document in the same turn unless the user explicitly asks for it.
- Do not infer pipeline field values from prose descriptions; require structured input or flag as `unresolved`.
- Do not assign a persona when none is evident.
- Do not skip the file-type confirmation step for Document lane requests.
- Do not pass the pipeline-engine to a Content or Document spoke unless that spoke explicitly uses deal or account data.
- Make uncertainty visible in the routing object, not hidden in hedged sentences.

## Stop conditions
Stop after returning the human summary and routing object unless:
- The user explicitly asks for the spoke work in the same message.
- The routing is completely unambiguous, the spoke is simple, and proceeding saves meaningful effort.

## Downstream spokes

```
content-strategy    project-builder    video-development    shortform-repurposing
seo-keywords        analytics-insights analytics-compute    audience-research
competitor-analysis seasonal-trends    content-distributor  document-studio
account-manager     deal-pipeline       deal-resourcing     partnership-mediakit
contract-desk       finance-desk       quality-review
```
