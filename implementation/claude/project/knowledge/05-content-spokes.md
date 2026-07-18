---
name: content-strategy
description: generate content ideas, seasonal-aware idea clusters, pillar-aligned video concepts, and competitive positioning for the channel. Use when the user wants ideas, a content plan, what to make next, or how to position against a competitor. Do NOT use to develop one concept into a production package (use video-development) or to build a downloadable calendar file (use document-studio).
---

_Data freshness: as of 2026-07-18 (Creator OS baseline c7194bb5). Live updates come from your own store; see docs/FRESHNESS.md. Source and updates: github.com/flywifi/seo-tools._

# content-strategy

The primary idea-generation spoke. Produces idea clusters, not single ideas, so every suggestion
seeds follow-on content.

## When to use this skill
Triggers: "give me video ideas," "what should I make for fall," "ideas for the thrifting pillar,"
"how do I stand out." Do NOT develop one idea into hook, title, and clips (use video-development) or
produce a downloadable calendar file (use document-studio).

## Inputs
Pillar(s), persona(s), seasonal context, and any platform target. Anything unstated is inferred and
stated, or left unspecified.

## Core procedure
Follow `shared/method.md`; compose atoms via `workflow.json`.
1. Classify the pillar (pillar-classify) and map the persona from `shared/audience-engine.md`.
2. Generate an idea batch (idea-generate) as clusters, not single ideas.
3. Verify any trend or seasonal claim (trend-check) through `shared/web-intel-engine.md`; mark data
   older than the freshness window as stale rather than dropping it.
4. Gate the cluster (govern-artifact) before it ships.

## Output contract
An idea cluster: each idea with pillar, format, persona served, hook angle, scale (quick win, medium,
hero), and a follow-on seed. Includes `source_artifacts` and `retrieval_gaps`. Obeys
`protocols/formatting-metadata.md`.

## Engines and protocols loaded
`shared/brand-engine.md`, `shared/audience-engine.md`, `shared/adaptation-engine.md`,
`shared/platform-engine.md`, `shared/web-intel-engine.md`. Protocols: `protocols/research-citation.md`,
`protocols/no-fabrication.md`, `protocols/formatting-metadata.md`, `protocols/quality-gates.md`.

## Atoms used
pillar-classify, idea-generate, trend-check, govern-artifact. A user can call idea-generate or
trend-check directly for a one-off.

## Standalone usability
Produces a complete idea cluster even when no downstream spoke is available, and names the next step
(video-development) as a hint, not a dependency.

## Failure modes
- Recommending a trend without verifying current momentum. trend-check is mandatory for any trend or
  seasonal claim; data older than 14 days for fast-moving categories is marked stale.
- Returning single ideas instead of clusters.
- Drifting off the home decor aesthetic toward bright farmhouse.

---

---
name: video-development
description: develop one video concept into a full production package: hook, title options, outline, thumbnail concept, SEO-aware description, and at least three short-form clip extractions. Use when the user has a concept and wants to build it out ("develop this idea," "give me the title, hook, and outline"). Do NOT use to generate fresh ideas (use content-strategy) or to write the full word-for-word script (use script-writer when present).
---

# video-development

Develops a single concept into a production package. Every concept yields at least 3 standalone
short-form clips alongside the long-form outline.

## When to use this skill
Triggers: "develop this idea," "build out this video," "give me the title, hook, and outline." Do NOT
generate new ideas (use content-strategy) or write the full spoken script.

## Inputs
A concept (from content-strategy or the user), the target persona, and platform targets.

## Core procedure
Follow `shared/method.md`; compose atoms via `workflow.json`.
1. Build the keyword cluster (keyword-cluster) for the title and description.
2. Write the hook (hook-write) that lands the promise in the first 15 to 30 seconds.
3. Generate title options (title-generate), human readable first, primary keyword front-loaded.
4. Design the thumbnail concept (thumbnail-concept), aligned to the title.
5. Extract at least 3 standalone short-form clips (short-extract), each with its own hook.
6. Assemble the outline (intro and hook, problem and before, process and key decisions, reveal and
   payoff, recap, outro and CTA) and an SEO-aware description.
7. Gate the package (govern-artifact).

## Output contract
A production package: hook, title options, outline sections, thumbnail concept, SEO description (1 to
2 primary keywords in the title and the opening 200 characters), and 3 or more short-form clips. Obeys
`protocols/formatting-metadata.md`.

## Engines and protocols loaded
`shared/brand-engine.md`, `shared/audience-engine.md`, `shared/platform-engine.md`,
`shared/adaptation-engine.md`, `shared/web-intel-engine.md`. Protocols: `protocols/research-citation.md`,
`protocols/no-fabrication.md`, `protocols/formatting-metadata.md`, `protocols/quality-gates.md`.

## Atoms used
keyword-cluster, hook-write, title-generate, thumbnail-concept, short-extract, govern-artifact. A user
can call hook-write, title-generate, or short-extract directly.

## Standalone usability
Produces a complete production package even when shortform-repurposing or script-writer is not
available; the clip list is usable on its own.

## Failure modes
- Returning fewer than 3 short-form clips.
- Clips that depend on the full video for context.
- Overpromising titles or thumbnails the video does not deliver.

---

---
file: skills/seo-keywords/SKILL.md
name: seo-keywords
description: build a full SEO strategy for a content topic: keyword cluster, search intent, competitive gap analysis, and a recommended title and description skeleton. Optimized for YouTube; also covers Pinterest and TikTok.
load: always
---

# seo-keywords

The SEO strategy spoke for the Content lane. Given a content topic, it produces a verified keyword
cluster, a search intent classification, a competitive gap analysis, and a recommended title and
description skeleton ready for the video-development spoke or direct use.

## Purpose

seo-keywords answers the question: "What keywords should I rank for, who is already ranking, and
what title structure gives the creator the best chance to surface in search and suggested video?" It
is the authoritative SEO input for any Content lane artifact. It does not generate hooks, outlines,
or production packages (use video-development for those). It does not write final copy (it produces
a skeleton). It does not assert exact search volume figures as confirmed fact; all volume signals
are presented as estimated ranges sourced from web-intel retrieval and must be independently
verified before use in an editorial decision.

Platform priority order: YouTube (primary), Pinterest (secondary), TikTok (secondary). The spoke
runs a YouTube-first strategy and adapts signals to Pinterest and TikTok using
`shared/platform-engine.md`. Pinterest and TikTok outputs are labeled as platform-adapted
extensions of the YouTube strategy, not independent SEO studies.

All retrieval passes through `shared/injection-guard-engine.md`. Platform spec freshness window is
3 to 6 months per `protocols/research-citation.md`; specs older than 6 months are marked stale
and flagged for re-verification.

## Inputs

```json
{
  "topic": "string -- the content topic or seed keyword (required)",
  "platform_targets": ["youtube", "pinterest", "tiktok"],
  "persona": "string -- target persona label from shared/audience-engine.md (optional; inferred if omitted)",
  "competitor_count": "integer -- competitors to surface per platform (default: 5, max: 10)"
}
```

- `topic`: a keyword phrase or concept (for example, "home decor bedroom on a budget" or "vintage
  thrift flip DIY").
- `platform_targets`: defaults to all three platforms if omitted. YouTube is always included.
- `persona`: if omitted, the spoke infers from the topic and states the inference explicitly in the
  output so the creator can confirm or override.
- `competitor_count`: passed directly to competitor-scan; controls how many competitors are returned
  per platform call.

## Primary outputs

```json
{
  "skill": "seo-keywords",
  "topic": "string",
  "persona_used": "string",
  "keyword_cluster": {
    "primary": ["1 to 2 exact-phrase keywords recommended for the title"],
    "secondary": ["2 to 4 keywords for the description body and tags"],
    "long_tail": ["4 to 8 keywords for the description, chapter titles, and hashtags"],
    "difficulty_note": "which primaries are high-competition for a new or mid-size channel",
    "volume_estimates": {
      "note": "All figures are estimated ranges from web-intel retrieval. Treat as directional only. Verify with YouTube Studio, Google Trends, or a keyword tool before using in an editorial decision.",
      "primary_range": "example: roughly 10,000 to 50,000 monthly searches [estimated, unverified]",
      "long_tail_range": "example: roughly 500 to 5,000 monthly searches [estimated, unverified]"
    }
  },
  "search_intent": {
    "classified_intent": "informational | navigational | transactional | inspirational",
    "platform_intent_notes": {
      "youtube": "string -- what the searcher expects to find on YouTube for this keyword",
      "pinterest": "string -- what the searcher expects to find on Pinterest for this keyword",
      "tiktok": "string -- what the searcher expects to find on TikTok for this keyword"
    },
    "content_format_implication": "string -- format and structure recommendation implied by the intent classification"
  },
  "competitive_gap_analysis": {
    "youtube": {
      "overserved_angles": ["list of angles already covered by multiple competitors"],
      "underserved_angles": ["list of angles with thin or absent coverage"],
      "gap_summary": "string -- most actionable differentiation opportunity for the creator on YouTube",
      "confidence": "high | medium | low"
    },
    "pinterest": {
      "overserved_angles": [],
      "underserved_angles": [],
      "gap_summary": "string",
      "confidence": "high | medium | low"
    },
    "tiktok": {
      "overserved_angles": [],
      "underserved_angles": [],
      "gap_summary": "string",
      "confidence": "high | medium | low"
    }
  },
  "title_skeleton": {
    "recommended_titles": [
      {
        "title": "string -- primary keyword front-loaded; human readable first",
        "chars": 0,
        "keyword_front_loaded": true,
        "platform": "youtube"
      }
    ],
    "description_skeleton": {
      "opening_200_chars": "string -- primary keyword in first sentence; hook the viewer in the first two lines visible before 'show more'",
      "body_structure": ["keyword-rich paragraph 1 outline", "keyword-rich paragraph 2 outline", "chapter timestamps placeholder", "hashtag block placeholder"],
      "pinterest_description_skeleton": "string -- 150 to 300 character Pinterest description adapted from the YouTube description; keyword at the front",
      "tiktok_caption_skeleton": "string -- under 150 characters; primary keyword or hashtag in the first line"
    }
  },
  "retrieval_gaps": ["any keyword or competitor data that could not be retrieved; manual check required"],
  "fabrication_flags": ["any field that could not be confirmed by retrieval and is marked [unverified]"],
  "source_artifacts": [],
  "human_review_required": true
}
```

Key output guarantees:

- Volume figures are always ranges labeled "[estimated, unverified]". Exact numbers are never
  asserted. The output block includes an explicit note directing the creator to verify with a live
  tool before acting.
- Competitor names, URLs, and scale tiers from competitor-scan are passed through unchanged,
  including their [unverified] labels where present.
- The title skeleton is ready to hand to title-generate for final polish; it is a draft, not a
  finished title.
- `human_review_required` is always true. The govern-artifact gate must pass before any output
  from this spoke is used in a published artifact.

## Atoms composed

1. keyword-cluster: builds the primary, secondary, and long-tail keyword lists for YouTube;
   adapts secondary and long-tail lists for Pinterest and TikTok via platform-engine.
2. search-intent: classifies the dominant search intent for the topic on each platform and derives
   a content format implication.
3. competitor-scan: called once per platform (up to three calls); surfaces overserved and
   underserved angles and generates the gap summary.
4. title-generate: generates 2 to 4 title skeleton options with character counts and
   keyword-front-loading flags.
5. govern-artifact: gates the full strategy package through quality-review before release.

## Engines required

- `shared/platform-engine.md`: platform SEO differences, character limits, spec freshness window
  (3 to 6 months).
- `shared/web-intel-engine.md`: live keyword signal retrieval starting at Level 2 (public
  analytics endpoints) and falling through to Levels 3 and 4 if Level 2 returns thin results.
- `shared/seo-intelligence-engine.md`: topical authority model, algorithm signal hierarchy,
  entity SEO rules, long-tail expansion methodology, SERP feature map, seasonal lead times.

## References

- `shared/platform-engine.md`
- `shared/seo-intelligence-engine.md`
- `protocols/research-citation.md` (platform spec freshness window: 3 to 6 months)
- `protocols/no-fabrication.md`
- `shared/web-intel-engine.md`
- `shared/brand-engine.md` (home decor keyword vocabulary and aesthetic guard)
- `protocols/quality-gates.md` (governs the govern-artifact gate at the end of the workflow)

## Do NOT use for

- Generating hooks, outlines, scripts, or thumbnail concepts. Use video-development for those.
- Writing final copy for a description or caption. This spoke produces skeletons; use
  video-development or document-studio for finished copy.
- Asserting exact search volume figures as verified fact. Volume output from this spoke is always
  an estimated range requiring independent verification.
- Researching the creator's own channel analytics or video performance. Use the platform API
  connection via web-intel-engine Level 1 directly.
- Trend momentum research outside a specific keyword. Use trend-check for broad trend signals.
- Brand partnership or sponsorship research. Use deal-tracker or account-manager spokes.
- Any topic outside the home decor and DIY niche. This spoke's keyword vocabulary
  and competitor pool are calibrated to that niche; off-niche results will be unreliable.

---

---
file: skills/shortform-repurposing/SKILL.md
name: shortform-repurposing
description: "converts a long-form YouTube video project into a short-form package: 3 to 5 Shorts/Reels, per-platform captions, hashtag sets, and Pinterest Pins; does NOT generate the original long-form content."
load: always
---

# shortform-repurposing

## Purpose

Maintains the Creator OS ecosystem ratio of 1 long-form video + 3 to 5 Shorts/Reels + 1 to 3 Pins per project. This spoke handles everything after the long-form video exists: it extracts clips, writes per-platform captions, builds hashtag sets, drafts Pinterest Pins, slots drops onto the calendar, and runs the quality gate before output is returned.

## Inputs

| Field | Type | Required | Notes |
|---|---|---|---|
| `long_form_title` | string | required (or `project_brief`) | Title of the published or in-progress long-form video |
| `project_brief` | string | required (or `long_form_title`) | Free-text brief if the video is not yet titled |
| `source_transcript` | string | optional | Full or partial transcript; improves clip extraction fidelity |
| `video_url` | string | optional | YouTube or internal URL used to extract clips when no transcript is supplied |
| `platform_targets` | list of strings | optional | Defaults to `[youtube-shorts, instagram-reels, tiktok, pinterest]` |
| `persona` | string | optional | Overrides the default audience persona from `shared/audience-engine.md` |

## Primary Outputs

Returns a single `short_form_package` object with the following keys:

- **clips** (list, 3 to 5 items) - produced by `short-extract`. Each clip contains a hook line, a transcript excerpt or timecode range, and a recommended duration.
- **captions** (list) - produced by `caption-write` (repeated once per clip per platform). Each caption is platform-spec-compliant in length, tone, and CTA style.
- **hashtag_sets** (map: platform to list) - produced by `hashtag-set` (repeated once per platform). Each set is deduplicated and ordered by tier (niche first, broad last).
- **pins** (list, 1 to 3 items) - produced by `pin-write`. Each Pin includes a title, description, and board suggestion aligned to the seasonal aesthetic in `canonical-sources/`.
- **drop_schedule** (object) - produced by `calendar-slot`. Maps each clip and Pin to a recommended publish date and time window.
- **quality_gate_result** (object) - produced by `govern-artifact`. Passes or blocks the package; surfaces any formatting, safety, or brand violations before delivery.

## Atoms Composed

Atoms are invoked in the order listed. `caption-write` and `hashtag-set` run once per target platform per clip.

1. `short-extract` - identifies and structures 3 to 5 clip candidates from the source material
2. `caption-write` (repeat: per_platform) - writes a caption for each clip tailored to the target platform
3. `hashtag-set` (repeat: per_platform) - builds a ranked hashtag set for each platform
4. `pin-write` - drafts 1 to 3 Pinterest Pins from the strongest visual moments
5. `calendar-slot` - assigns publish windows for each clip and Pin
6. `govern-artifact` - runs the full quality gate and returns a pass or block result

## Engines Required

- `shared/platform-engine.md` - character limits, aspect ratios, caption styles, hashtag ceilings, and scheduling windows for each platform
- `shared/brand-engine.md` - voice, tone, visual style, and niche identity constraints

## References

- `shared/platform-engine.md`
- `protocols/formatting-metadata.md`
- `protocols/safety.md` (FTC disclosure rules apply when content is sponsored)
- `protocols/quality-gates.md`

## Do NOT use for

- **Generating the original long-form video** - use the `video-development` spoke. This spoke assumes the long-form project already exists.
- **SEO keyword strategy** - use the `seo-keywords` spoke. This spoke consumes keywords; it does not generate them.
- **Caption file transcription** (SRT/VTT/ASS output) - use `document-studio`. This spoke writes social captions, not caption files.

---

---
file: skills/competitor-analysis/SKILL.md
name: competitor-analysis
description: "researches competitors in the moody/vintage home decor and DIY niche, surfaces content gaps and differentiation angles, and produces a gap report; does NOT fabricate competitor data."
load: always
---

# competitor-analysis

## Purpose

Delivers competitive intelligence to support content positioning for the creator's home decor
home decor and DIY channel. The skill scans publicly visible content across specified platforms,
clusters observed content angles, identifies overserved and underserved topics, and returns a
structured gap report.

This skill never fabricates competitor metrics. When subscriber counts, view figures, or engagement
rates cannot be confirmed through live retrieval, each affected field is marked `[unverified]` and
a manual-check recommendation is appended. Confidence is reported honestly at the report level as
`high`, `medium`, or `low` based on retrieval coverage.

## Inputs

| Field | Type | Required | Default | Notes |
|---|---|---|---|---|
| `topic` | string | yes | none | Seed keyword or content topic to anchor the scan |
| `platforms` | list of strings | no | `[youtube, pinterest, tiktok]` | Platforms to scan; any combination of `youtube`, `pinterest`, `tiktok`, `instagram` |
| `competitor_count` | integer | no | `5` | Target number of distinct competitor channels or accounts to surface |
| `include_keyword_gaps` | boolean | no | `true` | When true, runs keyword-cluster and gap-record atoms to produce `keyword_gaps` |

## Primary outputs

Returns a single `competitive_report` object with the following fields:

```
competitive_report:
  competitors_found:          # list; each entry below
    - name: string
      url_if_found: string    # omit if not retrieved; do not guess
      scale_tier: string      # "micro", "mid", or "large"; mark [unverified] if not confirmed
      content_angle: string   # observed dominant angle (e.g. "dark academia styling on a budget")
      note: string            # append "[unverified]" where any field is not confirmed by retrieval
  overserved_topics: list     # topics with dense, high-volume competitor coverage
  underserved_topics: list    # topics with thin or low-quality competitor coverage
  keyword_gaps: list          # present only when include_keyword_gaps is true
  differentiation_summary: string  # 3 to 5 sentence positioning recommendation grounded in gaps
  confidence: enum            # "high" | "medium" | "low"
  retrieval_gaps: list        # platforms or competitors where retrieval returned no usable data
  quality_gate_result: object # pass/fail + any flags from protocols/quality-gates.md
```

Confidence levels:
- `high`: retrieval succeeded on all requested platforms and at least `competitor_count` accounts
  were found with enough observable content to characterize angles.
- `medium`: one platform returned sparse results or fewer than `competitor_count` accounts were
  confirmed.
- `low`: two or more platforms returned no usable data or fewer than half the target competitor
  count was confirmed.

## Atoms composed

The following atoms are orchestrated in sequence. `trend-check` is conditional.

1. **competitor-scan** (per_platform) -- runs once per platform in `platforms`; collects publicly
   visible channel or account data and recent content titles.
2. **keyword-cluster** -- groups observed content titles into topic clusters; required before
   gap-record.
3. **search-intent** -- classifies cluster intents (informational, inspirational, transactional)
   to sharpen differentiation angles.
4. **trend-check** (conditional) -- runs only when `topic` matches a seasonal or trending
   signal in shared/platform-engine.md; appends trend context to underserved topics.
5. **gap-record** -- compares clusters against the creator's existing content footprint and outputs
   `overserved_topics`, `underserved_topics`, and `keyword_gaps`.
6. **govern-artifact** -- validates the assembled report against protocols/quality-gates.md and
   sets `quality_gate_result`.

## Engines required

- `shared/web-intel-engine.md` -- governs all retrieval operations: recency windows, source
  credibility tiers, null-and-flag behavior when data is unavailable.
- `shared/platform-engine.md` -- supplies platform-specific content norms, format constraints,
  and seasonal aesthetic signals used by competitor-scan and trend-check.
- `shared/seo-intelligence-engine.md` -- entity SEO rules and entity keyword seed list;
  topical authority model used to frame gap analysis in terms of cluster architecture.

## References

- `protocols/no-fabrication.md` -- binding. Competitor subscriber counts, view figures, and
  engagement rates must never be invented. Mark `[unverified]` and recommend manual check.
- `protocols/research-citation.md` -- recency window for home decor content: 6 to 18 months.
  Competitor content older than 18 months may be included for angle mapping but must be flagged
  as potentially stale.
- `shared/web-intel-engine.md` -- retrieval and confidence rules.
- `shared/seo-intelligence-engine.md` -- entity SEO and topical authority model.
- `protocols/quality-gates.md` -- governs `quality_gate_result`; report is not releasable until
  govern-artifact returns pass.

## Do NOT use for

- Fabricating competitor subscriber counts or view figures. If retrieval does not return a
  confirmed figure, mark the field `[unverified]` and include a recommendation to check manually
  via YouTube Studio, Social Blade, or the platform's public page.
- Analyzing paid advertising strategies or sponsored content performance. This skill covers only
  organic, publicly visible content.
- Accessing competitor private analytics, backend dashboards, or any data that is not publicly
  viewable without authentication.
- General web research outside the home decor and DIY niche. Use
  `shared/web-intel-engine.md` directly for broad research tasks.
- Producing final editorial decisions. The gap report informs content strategy; it does not
  replace the creator's judgment.

---

---
file: skills/seasonal-trends/SKILL.md
name: seasonal-trends
description: "builds a seasonal content strategy for a defined window by mapping topics to pillars, checking trend momentum, and scheduling them; does NOT generate production packages or scripts."
load: always
---

# seasonal-trends

## Purpose

Builds a seasonal content strategy for a defined planning window in the moody/vintage home decor and DIY niche. The skill maps topic seeds to the four recurring seasonal peaks that drive audience engagement for this channel:

- Seasonal decor: September to October
- Holiday tablescapes: November to December
- Spring refresh: March to April
- Summer outdoor: May to June

For each peak, the skill clusters ideas around content pillars, verifies trend momentum via web intelligence, assigns personas, and produces a publish schedule. Output is a structured plan ready for downstream production skills, not a finished production package.

## Inputs

| Field | Type | Required | Default | Notes |
|---|---|---|---|---|
| season_or_window | string | yes | none | e.g. "fall 2026" or "November to December" |
| topic_seeds | list of strings | no | none | Optional starting ideas; if omitted, the skill derives seeds from the seasonal window |
| pillar_focus | list of strings | no | all 5 pillars | Restricts output to named pillars only |
| idea_count | integer | no | 5 | Target number of ideas in the output cluster |

## Primary outputs

Returns a `seasonal_plan` object with the following structure:

```
seasonal_plan
  window               string    the resolved season label (e.g. "Fall 2026")
  peak_dates           string    the canonical date range for the window (e.g. "September to October 2026")
  idea_cluster         list
    working_title      string    draft title for the idea
    pillar             string    one of the 5 content pillars
    persona_served     string    primary audience persona from audience-engine
    seasonal_urgency   string    "high" | "medium" | "low" based on proximity to peak
    trend_status       object    output from trend-check atom (momentum, direction, source citations)
    publish_schedule   object    output from calendar-slot atom (recommended publish date, slot rationale)
  retrieval_gaps       list      topics where web-intel returned no usable signal; flagged, not fabricated
  quality_gate_result  object    pass/fail result from govern-artifact with any blocking issues listed
```

All fields with no retrievable data are set to null and surfaced in `retrieval_gaps`. No metric, rate, or trend claim is fabricated (see `protocols/no-fabrication.md`).

## Atoms composed

Atoms are invoked in the order listed. `trend-check` is conditional and runs once per idea.

1. **seasonal-map** -- resolves `season_or_window` to canonical peak dates and retrieves the matching seasonal aesthetic profile from `canonical-sources/seasonal-aesthetic/seasonal.json`
2. **idea-generate** -- expands `topic_seeds` (or derives seeds from the seasonal profile) into a candidate idea list sized to `idea_count`
3. **trend-check** *(per idea, conditional)* -- queries web intelligence for each candidate idea; marks momentum direction; cites sources; sets `trend_status`; skips if web-intel returns no signal and logs to `retrieval_gaps`
4. **keyword-cluster** -- attaches keyword groups to each idea using platform-engine keyword norms and any trend-check signal
5. **calendar-slot** -- assigns a recommended publish date and rationale for each idea within the resolved peak window
6. **govern-artifact** -- runs the Quality Gates protocol against the assembled plan and populates `quality_gate_result`

## Engines required

- `shared/platform-engine.md` -- pillar definitions, keyword norms, platform publishing constraints
- `shared/web-intel-engine.md` -- trend signal retrieval, source citation rules, null-and-flag behavior

## References

- `canonical-sources/seasonal-aesthetic/seasonal.json` -- authoritative seasonal window dates and aesthetic profile data
- `protocols/research-citation.md` -- citation formatting rules for all trend and source claims
- `protocols/no-fabrication.md` -- null-and-flag requirement; no trend data, metric, or date may be invented
- `protocols/quality-gates.md` -- gate criteria that `govern-artifact` enforces before the plan is released

## Do NOT use for

- Generating scripts, hooks, B-roll lists, or production packages -- use `video-development` for that
- SEO keyword strategy or keyword research as a standalone deliverable -- use `seo-keywords`
- Competitor research or gap analysis -- use `competitor-analysis`
- Content outside the moody/vintage home decor and DIY niche -- this skill's seasonal windows, aesthetic profiles, and persona assumptions are niche-specific and will produce invalid output for other niches
- Producing a plan that bypasses the Quality Gates -- `govern-artifact` is non-optional; a plan that does not pass the gate is not released

---

---
file: skills/audience-research/SKILL.md
name: audience-research
description: research and profile the creator's target audience by mapping comments, engagement patterns, and platform signals to the five-persona model; surfaces audience insights to inform content strategy. Content lane spoke.
load: always
---

# audience-research

Content lane spoke that transforms raw audience signals (comments, analytics exports, platform data)
into a verified persona profile and actionable audience insights for the creator's
home decor and DIY channel.

## Purpose

audience-research answers the question: "Who is actually watching, engaging, and converting, and
what do they need?" It does not generate content. It does not guess at demographics or fabricate
engagement figures. It maps only what is present in the provided data or confirmed through flagged
live retrieval, records every gap explicitly, and produces a profile that downstream spokes
(content-strategy, seo-keywords, video-development) can consume to target the right persona at the
right moment.

The five canonical personas this spoke maps against:

| Persona | Core identity |
|---|---|
| Renter | Small-space, budget-constrained renter; no permanent changes allowed |
| Vintage Hunter | Thrift and antique seeker; wants sourcing strategy and authenticity |
| Organizer | System-seeker; loves checklists, labeled zones, and declutter workflows |
| Holiday Maximalist | Seasonal decor enthusiast; wants moody impact without looking cheap |
| New Homeowner | First home, overwhelmed, modest budget, builder-basic starting point |

Persona definitions are authoritative in `shared/audience-engine.md`. This spoke reads them from
there and never redefines them inline.

All retrieval follows `shared/web-intel-engine.md` acquisition levels. Any field that cannot be
confirmed by provided data or live retrieval is recorded via gap-record and flagged, never filled
with an estimate or invented figure, per `protocols/no-fabrication.md`.

## Inputs

```json
{
  "data_source": {
    "type": "comments_export | analytics_export | platform_url | paste",
    "file_path": "absolute local path (if type is comments_export or analytics_export)",
    "source": {
      "provider": "youtube | instagram | tiktok | pinterest",
      "identifier": "URL or content ID (if type is platform_url)"
    },
    "raw_text": "pasted comment block or analytics snippet (if type is paste)"
  },
  "analysis_scope": {
    "persona_targets": ["Renter", "Vintage Hunter", "Organizer", "Holiday Maximalist", "New Homeowner"],
    "time_window": "string -- e.g. last 90 days; null if not available",
    "content_sample": "string -- video title or topic the data is drawn from (optional)"
  }
}
```

- `data_source`: at least one of `file_path`, `source`, or `raw_text` must be provided. If none
  is provided, the spoke records a gap and returns a `needs_more_info` prompt.
- `persona_targets`: defaults to all five personas if omitted. Restrict to a subset to narrow the
  mapping pass.
- `time_window`: used to assess data freshness. If the export predates the freshness window in
  `protocols/research-citation.md`, results are labeled stale rather than suppressed.
- `content_sample`: helps persona-map weight the mapping. Omit when the analysis is channel-wide.

## Primary outputs

```json
{
  "skill": "audience-research",
  "data_source_summary": {
    "type": "string",
    "record_count": 0,
    "time_window": "string or null",
    "injection_scan_result": "CLEAN | REVIEW | QUARANTINE | BLOCK",
    "ingestion_status": "content_ingested | metadata_only | quarantined | send_back"
  },
  "persona_profile": {
    "Renter": {
      "signal_volume": "integer -- count of comments or data points mapped to this persona",
      "engagement_signals": ["verbatim themes or patterns drawn from the provided data; no invented text"],
      "confidence": "high | medium | low",
      "confidence_note": "string or null -- explains any factor that reduced confidence"
    },
    "Vintage Hunter": { "signal_volume": 0, "engagement_signals": [], "confidence": "low", "confidence_note": null },
    "Organizer": { "signal_volume": 0, "engagement_signals": [], "confidence": "low", "confidence_note": null },
    "Holiday Maximalist": { "signal_volume": 0, "engagement_signals": [], "confidence": "low", "confidence_note": null },
    "New Homeowner": { "signal_volume": 0, "engagement_signals": [], "confidence": "low", "confidence_note": null }
  },
  "dominant_persona": "string -- persona with highest signal volume and confidence",
  "underserved_personas": ["personas with low signal volume relative to their share in shared/audience-engine.md"],
  "top_themes": [
    {
      "theme": "string -- pattern or recurring question from the data",
      "persona_fit": ["Renter", "..."],
      "frequency": "integer -- approximate count; labeled [estimated] if not exact",
      "content_opportunity": "string -- specific video angle or format this theme suggests"
    }
  ],
  "platform_signals": {
    "provider": "youtube | instagram | tiktok | pinterest | null",
    "engagement_patterns": ["string -- observed patterns from analytics data; null if not available"],
    "freshness": "string -- data date range or 'stale' if outside research-citation window"
  },
  "retrieval_gaps": [
    {
      "tool": "gap-record",
      "gap_type": "string",
      "description": "string",
      "impact": "string",
      "recommended_next_step": "string"
    }
  ],
  "fabrication_flags": ["any field that could not be confirmed and is marked [unverified]"],
  "source_artifacts": [],
  "human_review_required": true
}
```

Key output guarantees:

- `engagement_signals` contains only themes or patterns drawn from the provided data. No comment
  text is invented, paraphrased beyond recognition, or presented as a direct quote unless it appears
  verbatim in the source. Per `protocols/no-fabrication.md`, invented audience statements are a
  hard-fail violation.
- `signal_volume` counts are exact where the data allows and labeled `[estimated]` where the
  ingested record reports approximate counts.
- `confidence` is set to `low` whenever the underlying signal volume is fewer than 10 data points
  for a persona, or the ingestion status is `metadata_only`.
- `human_review_required` is always `true`. govern-artifact must pass before any audience profile
  is used in a published planning artifact.

## Atoms composed

1. ingest-route: ingests comments exports, analytics exports, or platform URLs; runs inject-scan;
   returns a structured ingestion record. Called first for every non-paste data source.
2. web-acquire (via `shared/web-intel-engine.md`): used when a platform URL is provided or when
   the ingestion record's routing hint indicates live retrieval is needed to supplement thin data.
   Acquisition level starts at Level 2 and falls through per the web-intel escalation rules.
3. persona-map: maps ingested content and observed themes to the five-persona model; returns primary
   and secondary personas per topic cluster surfaced in the data.
4. gap-record: called for every field or retrieval path that returns no usable data. Produces an
   explicit gap object rather than a silent blank.
5. govern-artifact: gates the completed audience profile through quality-review before it is
   returned to the user or a downstream spoke.

## Engines required

- `shared/audience-engine.md`: authoritative five-persona definitions; persona signal thresholds;
  engagement pattern taxonomy.
- `shared/web-intel-engine.md`: acquisition-level escalation rules; freshness windows; retrieval
  gap handling.

## References

- `shared/audience-engine.md`
- `shared/web-intel-engine.md`
- `protocols/no-fabrication.md`
- `protocols/research-citation.md`
- `protocols/quality-gates.md`

## Do NOT use for

- Generating content ideas, hooks, titles, or scripts. Use content-strategy or video-development.
- Fabricating or estimating comment sentiment, demographic breakdowns, or engagement figures when
  no source data is provided. Null and record a gap instead.
- Competitor audience research. This spoke profiles the creator's own audience only. Use
  competitor-analysis for competitor channel profiling.
- Producing final editorial decisions. Outputs are research inputs requiring human review before
  any publishing action.
- Any audience outside the creator's home decor and DIY channel. These persona
  definitions and signal thresholds are calibrated for that specific niche and creator.

---

---
file: skills/analytics-insights/SKILL.md
name: analytics-insights
description: "analyzes the creator's channel and post metrics, compares them to industry benchmarks, and surfaces prioritized recommendations; does NOT fabricate data and returns a gap-record if no analytics data is provided."
load: always
---

# analytics-insights

## Purpose

Reads provided analytics data (exported CSV, screenshot, or structured object) for the creator's YouTube, Instagram, TikTok, or Pinterest presence. Performs benchmark comparison against canonical rate benchmarks. Returns a prioritized insights report with data-quality flags.

If no analytics data is provided or the data is insufficient for meaningful analysis, this skill invokes the `gap-record` atom and returns a structured gap record instead of fabricating or estimating values. No metrics, rates, or benchmarks are invented; all comparisons draw from `canonical-sources/rate-benchmarks/benchmarks.json`.

## Inputs

| Field | Type | Required | Notes |
|---|---|---|---|
| `analytics_source` | object, file_path (CSV or screenshot), or null | yes | Pass null to trigger gap_record mode |
| `platform` | string: youtube, instagram, tiktok, pinterest, or all | yes | Scopes benchmark lookup and metric set |
| `time_period` | string | no | Example: "last 90 days". Defaults to whatever the source covers |
| `comparison_metrics` | list of strings | no | Defaults: ctr, avd, engagement_rate, subscribers |

## Primary outputs

Returns an `insights_report` object with the following fields:

- `metrics_analyzed` (list): the metrics successfully extracted from the analytics source
- `benchmark_comparisons` (list): per-metric comparison produced by the `benchmark-compare` atom, drawn from `canonical-sources/rate-benchmarks/benchmarks.json`
- `top_performers` (list): videos or posts with the highest metric values in the analyzed window
- `underperformers` (list): videos or posts that fall below benchmark thresholds
- `recommendations` (list): prioritized action items, each with a rationale field; ordered by estimated impact
- `data_quality` (string enum): real | estimated | partial
- `retrieval_gaps` (list): fields that could not be extracted or were absent from the source
- `quality_gate_result` (object): output of the `govern-artifact` atom; includes pass/fail and any blocking findings

## Atoms composed

| Atom | When invoked |
|---|---|
| `ingest-route` | Parses an uploaded CSV or screenshot into a structured analytics object |
| `benchmark-compare` | Compares extracted metrics against benchmarks from canonical-sources |
| `roi-metric` | Invoked when the content being analyzed is linked to a deal in the pipeline |
| `gap-record` | Invoked when `analytics_source` is null or data is too sparse to analyze |
| `govern-artifact` | Always invoked last; enforces Quality Gates before the report is returned |

## Engines required

- `shared/platform-engine.md`: platform-specific metric definitions, normal ranges, and posting norms
- `shared/audience-engine.md`: audience segment context used when interpreting engagement signals

## References

- `canonical-sources/rate-benchmarks/benchmarks.json`: authoritative benchmark values for all supported platforms
- `protocols/no-fabrication.md`: prohibits inventing any metric, rate, or benchmark value
- `protocols/research-citation.md`: governs how benchmark sources are attributed in the report
- `protocols/quality-gates.md`: defines pass/fail criteria applied by `govern-artifact`

## Do NOT use for

- Fabricating analytics data when none is provided. Use the `gap-record` atom instead and return an honest gap record.
- Generating content recommendations that are not grounded in the provided analytics data.
- Accessing live platform APIs directly. If fresh data is needed from a live source, route through `shared/web-intel-engine.md` Level 1 fetch; this skill does not call platform APIs itself.
- Producing a final deliverable that has not passed the Quality Gates enforced by `govern-artifact`.
