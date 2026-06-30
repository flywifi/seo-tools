---
file: docs/ROUTING_MODEL.md
role: Reference for the Creator OS routing model. Covers the classification enum, the three lanes,
  engine-load rules, protocol enforcement, the routing object schema, the minority report rule,
  and shortcut atoms.
---

# Creator OS Routing Model

The routing model lives in `skills/creator-core/SKILL.md`. This document is a reference companion;
the SKILL.md file is authoritative.

---

## The 21-value request_classification enum

Every request is classified into exactly one of these values before the hub emits the routing object:

| Value | Meaning |
|---|---|
| `content_ideation` | Request for video or content ideas |
| `project_planning` | Full project package from a single concept |
| `video_script` | Script, hook, or chapter development for a long-form video |
| `repurposing` | Extracting short-form content from a long-form source |
| `seo_research` | Keyword research, cluster strategy, or title SEO |
| `analytics_review` | Analytics interpretation, trend reading, or performance review |
| `audience_question` | Persona mapping, audience research, or signal gathering |
| `competitor_check` | Competitive positioning or gap identification |
| `seasonal_planning` | Seasonal topic or aesthetic planning |
| `document_create` | Creating a new file (media kit, calendar, brief, invoice, guide) |
| `document_edit` | Editing or updating an existing file |
| `account_create` | Creating a new brand account record in the pipeline |
| `account_update` | Updating an existing brand account record |
| `deal_create` | Creating a new deal record |
| `deal_update` | Updating deal fields on an existing record |
| `deal_stage_move` | Moving a deal from one stage to another |
| `production_plan` | Generating a production plan from a signed deal |
| `outreach_draft` | Drafting an outreach message or pitch |
| `media_kit` | Generating or updating a media kit |
| `quality_check` | Scoring or reviewing an artifact against the Quality Gates |
| `unclear` | Classification is ambiguous; clarifying question is required |

When the classification is `unclear`, the hub defaults to lower confidence, emits a clarifying
question, and does not route.

---

## Three lanes

### Content lane

**Definition:** any request to plan, script, research, repurpose, or analyze content.

**Eligible classifications:**
`content_ideation`, `project_planning`, `video_script`, `repurposing`, `seo_research`,
`analytics_review`, `audience_question`, `competitor_check`, `seasonal_planning`

**Spokes:**
content-strategy, project-builder, video-development, shortform-repurposing, seo-keywords,
analytics-insights, audience-research, competitor-analysis, seasonal-trends

**Safe default tie-breaker:** when a request touches both Content and Document but has no
explicit file output request, route to the Content lane.

### Document lane

**Definition:** any request to create or edit a file (media kit, deliverable brief, invoice, PDF
guide, content calendar, brand one-pager).

**Eligible classifications:**
`document_create`, `document_edit`

**Spokes:**
document-studio

**File-type confirmation:** the hub must confirm the target file type before routing any
Document lane request. `file_type_confirmed` must be `true` in the routing object before
the spoke is invoked.

### Pipeline/CRM lane

**Definition:** any request touching a brand account or deal: creating and reading and updating
records, moving a deal stage, generating a production plan from a signed deal, computing the radar,
checking deadlines or payment status.

**Eligible classifications:**
`account_create`, `account_update`, `deal_create`, `deal_update`, `deal_stage_move`,
`production_plan`, `outreach_draft`, `media_kit`

**Note:** `quality_check` routes to the quality-review governance skill, not to a lane spoke.
It does not belong to any lane.

**Spokes:**
account-manager, deal-pipeline, deal-resourcing, partnership-mediakit

---

## Engine-load map

The hub loads only the engines the target spoke actually needs. Loading unnecessary engines wastes
context; the hub must not pass an engine to a spoke that does not use it.

| Engine | Loaded for |
|---|---|
| brand-engine.md | Every Content and Document request |
| audience-engine.md | `content_ideation`, `project_planning`, `video_script`, `audience_question`, `analytics_review`, `repurposing`, `seasonal_planning` |
| platform-engine.md | `video_script`, `repurposing`, `seo_research`, `analytics_review`, `seasonal_planning` |
| adaptation-engine.md | Any request that produces a content or project artifact |
| pipeline-engine.md | Every Pipeline/CRM request; never passed to a Content or Document spoke unless that spoke explicitly uses deal or account data |
| web-intel-engine.md | `seo_research`, `competitor_check`, `analytics_review`, `trend_check` operations, `seasonal_planning` |
| docintel-engine.md | Any request that arrives with a file, attachment, or cloud asset |
| transcription-engine.md | `video_script`, `repurposing`, or any request involving audio or video files |
| integrations-engine.md | Any request that fetches from YouTube, Instagram, TikTok, OneDrive, or Google Drive |
| injection-guard-engine.md | Always active as pre-routing middleware on any external content; not passed explicitly to spokes |

---

## Protocol enforcement

Protocols are enforced at two points: by the hub before routing, and by the spoke before generating.

**Protocols enforced on every request regardless of lane or classification:**

| Protocol | What it governs |
|---|---|
| protocols/quality-gates.md | Every artifact scores the rubric before release |
| protocols/no-fabrication.md | Never invent data, metrics, rates, brands, deals, or sources |
| protocols/safety.md | Trade, legal, and FTC disclosure boundaries |
| protocols/research-citation.md | Research-first rule on trend, SEO, competitor, seasonal, and platform-spec questions |
| protocols/formatting-metadata.md | No em dashes, ranges with "to," document author set to brand-engine value |

**Protocol fire conditions by classification:**

| Classification group | Additional protocol behavior |
|---|---|
| `seo_research`, `competitor_check`, `seasonal_planning`, `analytics_review` | research-citation.md is mandatory; any time-sensitive claim must be verified before the artifact ships |
| `deal_create`, `deal_update`, `deal_stage_move`, `account_create`, `account_update` | no-fabrication.md applies strictly to all pipeline field values; pipeline-engine.md stage-transition rules must be satisfied |
| `document_create`, `document_edit` | formatting-metadata.md: document author must be set to the `document_author` value in brand-engine.md |
| `quality_check` | quality-gates.md is the sole protocol; quality-review runs the deterministic scorer |
| Any request with external file or content | injection-guard-engine.md fires before routing; quarantined content never reaches the spoke |

---

## Routing object schema

The hub returns a fully populated routing object with every response.

```json
{
  "request_classification": "string - one of the 21 enum values",
  "primary_lane": "content | document | pipeline_crm",
  "secondary_lane": "content | document | pipeline_crm | null",
  "persona_targets": ["array of named persona strings, empty if none evident"],
  "adaptation_axes": {
    "skill_level": "beginner | intermediate | unspecified",
    "tenure": "renter | owner | unspecified",
    "budget_tier": "budget | mid_range | premium | unspecified",
    "platform_targets": ["youtube | instagram | tiktok | pinterest | empty array"]
  },
  "engines_required": ["array of engine file paths, e.g. shared/brand-engine.md"],
  "protocols_to_enforce": ["array of protocol file paths"],
  "recommended_spoke": "string - spoke name",
  "secondary_spoke": "string | null",
  "pipeline_action": "string | null - e.g. stage_move, record_update, or null for non-CRM",
  "file_type_confirmed": "boolean - true only when document lane and file type is confirmed",
  "open_questions": ["array of strings, one question per item"],
  "conflicts": ["array of strings describing any conflicting signals"],
  "minority_report": "object | null - see minority report rule below",
  "confidence": "high | medium | low"
}
```

**Field rules:**
- `secondary_lane` is non-null only when the request genuinely spans two lanes.
- `persona_targets` is an empty array when no persona is evident; never default to a persona.
- All adaptation axis values default to `unspecified` when the user has not stated them.
- `pipeline_action` is `null` for all Content and Document requests.
- `file_type_confirmed` is `false` by default; the hub must explicitly confirm the file type for
  any Document lane request before setting it to `true`.
- `open_questions` contains one question per line; never bundle multiple questions into one item.
- `confidence` is `low` whenever the classification is `unclear` or any axis is highly ambiguous.

**Hard rules on pipeline fields:**
- Do not infer deal field values from prose descriptions; require structured input or flag as
  `unresolved`.
- Do not confirm account ownership claims without structured input.
- Do not confirm production commitments from a description alone.

---

## Minority report rule

When a request could reasonably route two different ways with meaningfully different downstream
outcomes, the hub does not suppress the alternative. It records the alternative in the
`minority_report` field.

The minority report is an object, not prose:

```json
{
  "minority_report": {
    "alternative_spoke": "string - the spoke not chosen",
    "alternative_lane": "content | document | pipeline_crm",
    "reason_not_chosen": "string - one sentence explaining why the primary routing was preferred"
  }
}
```

The minority report is `null` when the routing is unambiguous. It is never buried in the
plain-language human summary alone; it must appear in the JSON object.

---

## Shortcut atoms

Atoms can be called directly, bypassing the hub and any spoke orchestration, when the user needs
a single operation and the full hub-to-spoke workflow would add unnecessary overhead.

**When to go direct to an atom:**
- The request is clearly scoped to a single operation (for example, "give me five title ideas"
  maps directly to title-generate).
- No lane classification decision is required because the atom's scope is unambiguous.
- No engine load decision is required because the atom has fixed dependencies.
- The user explicitly names the atom by function ("just run keyword clustering on this term").

**When to go through the hub:**
- The request could route to more than one atom or spoke.
- The request involves engine loading decisions (for example, persona mapping requires
  audience-engine.md; skipping the hub risks loading the wrong context).
- The request involves protocol enforcement decisions that the atom does not self-enforce.
- The request spans two lanes.

**Atoms commonly used as shortcuts:**

| Atom | Direct-call trigger |
|---|---|
| idea-generate | "Just give me ideas" with a pillar stated |
| title-generate | "Give me title options for [topic]" |
| keyword-cluster | "Cluster keywords around [seed term]" |
| trend-check | "Is [topic] trending right now?" |
| govern-artifact | "Score this draft against the Quality Gates" |
| gap-record | Explicitly recording a retrieval or parse gap |
| ingest-route | Processing a file before any other action |

Even when an atom is called directly, the protocols still apply. The atom self-enforces
`protocols/no-fabrication.md` and `protocols/formatting-metadata.md`. The govern-artifact atom
enforces `protocols/quality-gates.md` unconditionally.
