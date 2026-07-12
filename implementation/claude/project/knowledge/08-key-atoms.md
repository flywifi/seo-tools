---
file: skills/atoms/keyword-compare/SKILL.md
name: keyword-compare
atom: true
description: compare 1 to 10 keywords side-by-side across platforms (YouTube, Pinterest, TikTok, Google) and optionally across a seasonal window, producing a structured matrix of intent, SERP feature, format fit, competition estimate, and seasonal relevance per keyword-platform pair plus three cross-platform verdicts (universal, platform-exclusive, niche long-tail). Use when the creator wants to decide which platform to prioritize for a keyword or batch of keywords without running four separate queries. Do NOT use for keyword research from scratch (use keyword-cluster or long-tail-expand first), seasonal planning without existing keywords (use seasonal-trends), or full SEO strategy output (use the seo-keywords spoke).
load:
  - shared/seo-intelligence-engine.md
  - shared/platform-engine.md
  - protocols/no-fabrication.md
  - protocols/formatting-metadata.md
---

_Data freshness: as of 2026-07-12 (Creator OS baseline 2821dd09). Live updates come from your own store; see docs/FRESHNESS.md._

# keyword-compare

Compare a list of keywords across platforms and optionally across a seasonal window.
Returns a structured matrix plus cross-platform verdicts so the creator can make one
decision about where to focus instead of running and collating four separate queries.

## Purpose

The creator's content decisions are inherently cross-platform: a keyword that drives
YouTube discovery may be a poor fit for Pinterest's visual search model, or it may
be a universal keyword that works everywhere. This atom surfaces the differences in
one structured output, using the SERP feature map and intent model from
`shared/seo-intelligence-engine.md` and platform-specific format rules from
`shared/platform-engine.md`. No volume API is used -- competition estimates are labeled
`[estimated]` and derived from SERP feature type and niche density signals.

## When to invoke

- "Which of these keywords works on TikTok vs. YouTube?"
- "Compare this keyword across platforms."
- "Where should I focus for fall -- YouTube or Pinterest?"
- "Show me which keywords overlap across platforms."
- "Do these keywords translate to Pinterest?"
- Invoke directly or from `seo-keywords` spoke via `shortcut_atoms`.

## Do NOT use for

- Keyword research from scratch -- generate keywords first with `keyword-cluster` or
  `long-tail-expand`, then feed the output here.
- Seasonal content planning without existing keywords -- use `seasonal-trends` spoke.
- Full SEO strategy output with titles, descriptions, and posting plan -- use `seo-keywords`.
- Cross-platform scheduling with a calendar -- use `calendar-slot`.
- Trending topic discovery -- use `trend-check`.

## Inputs

```json
{
  "keywords": ["string — 1 to 10 items"],
  "platforms": ["youtube", "pinterest", "tiktok", "google"],
  "season": "fall | holiday | spring | summer | evergreen",
  "check_trend_momentum": false
}
```

- `keywords`: 1 to 10 keyword strings. If more than 10 are provided, the first 10 are
  analyzed and the overflow is noted in `retrieval_gaps`.
- `platforms`: defaults to all four if omitted. Accepts any subset.
- `season`: optional. If provided, each keyword is tagged with seasonal relevance
  (peak / moderate / off_season / evergreen) using the lead times from
  `seo-intelligence-engine.md`. If omitted, `seasonal_relevance` is null for all cells.
- `check_trend_momentum`: when true, calls `trend-check` per platform per keyword to add
  a momentum signal (rising / flat / declining / unknown). Adds latency proportional to
  `len(keywords) x len(platforms)`. Emit a warning in output if the product exceeds 20.
  Defaults to false; static analysis only is fast and sufficient for most decisions.

## Procedure

1. For each keyword x platform pair: call `search-intent` with the platform parameter.
   Collect `intent` label and `format_fit` (primary and secondary).
2. Apply the SERP feature map from `seo-intelligence-engine.md` to each pair: derive
   `serp_feature` (video_carousel / image_pack / featured_snippet / shopping / local_pack)
   and `competition_estimate` (low / medium / high -- labeled `[estimated]`).
3. If `season` is provided: apply seasonal lead times from `seo-intelligence-engine.md`
   to tag each keyword with `seasonal_relevance` (peak / moderate / off_season / evergreen).
   Use static data from the engine -- do not call a separate atom.
4. If `check_trend_momentum: true`: call `trend-check` per keyword x platform.
   Attach `momentum` to each cell. If trend-check returns null or fails, set
   `momentum: "unknown"` and record a retrieval_gap.
5. Aggregate into comparison matrix. Compute per-keyword `cross_platform_verdict`:
   - `universal`: primary format_fit aligns with the dominant SERP feature on 3 or more platforms.
   - `platform_specific`: strong alignment on 1 to 2 platforms, weak on others.
   - `niche_long_tail`: low `competition_estimate` across all platforms.

## Output

```json
{
  "tool": "keyword-compare",
  "keywords_analyzed": ["string"],
  "keywords_overflow": ["strings beyond the 10-item limit, if any"],
  "platforms_analyzed": ["string"],
  "season_context": "fall | holiday | spring | summer | evergreen | null",
  "trend_momentum_checked": false,
  "comparison_matrix": [
    {
      "keyword": "string",
      "cross_platform_verdict": "universal | platform_specific | niche_long_tail",
      "strongest_platform": "youtube | pinterest | tiktok | google | null",
      "platform_profiles": [
        {
          "platform": "youtube",
          "intent": "informational | navigational | commercial | transactional",
          "format_fit": "long-form | short-form | pin | reel",
          "serp_feature": "video_carousel | image_pack | featured_snippet | shopping | local_pack | mixed",
          "competition_estimate": "low [estimated] | medium [estimated] | high [estimated]",
          "seasonal_relevance": "peak | moderate | off_season | evergreen | null",
          "momentum": "rising | flat | declining | unknown | null",
          "recommendation": "one-sentence action for this keyword on this platform"
        }
      ],
      "notes": "string or null"
    }
  ],
  "universal_keywords": ["string"],
  "platform_exclusive_opportunities": {
    "youtube": ["string"],
    "pinterest": ["string"],
    "tiktok": ["string"],
    "google": ["string"]
  },
  "seasonal_timing_summary": "string or null — only present when season_context is non-null",
  "retrieval_gaps": [],
  "fabrication_flags": []
}
```

## Fabrication rules

- `competition_estimate` is always labeled `[estimated]`. Never cite a specific volume number
  without an attributed API source. Estimates are derived from SERP feature type and niche
  density signals in `seo-intelligence-engine.md`.
- `momentum` is only present when `check_trend_momentum: true` AND trend-check returned a
  non-null result. Never invented.
- `seasonal_relevance` is only present when `season` is provided. Set to null for all cells
  if not provided -- do not infer seasonality without the input.
- `recommendation` in each platform profile is one concise, actionable sentence derived from
  intent, format_fit, serp_feature, and seasonal_relevance. No unverified statistics.

## Cross-platform verdict definitions

| Verdict | Definition |
|---|---|
| `universal` | Primary intent and format fit aligns with the dominant SERP feature on 3 or more analyzed platforms. Worth targeting everywhere. |
| `platform_specific` | Strong format fit on 1 to 2 platforms; low alignment on others. Focus on the strong platform(s). |
| `niche_long_tail` | Low competition estimate across all platforms. Specific enough to target everywhere without significant competitive pressure. |

`strongest_platform` is the platform with the best combination of format_fit alignment and
lowest competition estimate. If all are equal, return the first in `platforms_analyzed`.

## Momentum scope warning

If `check_trend_momentum: true` and `len(keywords) x len(platforms) > 20`, emit an advisory
in `retrieval_gaps`:

```
"check_trend_momentum=true with N keywords x M platforms = K calls. Consider reducing scope
or setting check_trend_momentum=false for a faster result."
```

The atom still runs -- this is advisory only, not a block.

---

---
name: keyword-cluster
description: build a keyword cluster (primary, secondary, long-tail) for a topic on a target platform, with a difficulty note for a new channel. Use when video-development or seo-keywords needs keywords. Do NOT assert search volume without web-intel verification; do NOT write the description copy (that is the spoke).
---

# keyword-cluster

Build one keyword cluster for one topic and platform.

## Input
```json
{
  "topic": "string",
  "platform": "youtube | pinterest | google"
}
```

## Output
```json
{
  "tool": "keyword-cluster",
  "primary": ["1 to 2 exact-phrase keywords for the title"],
  "secondary": ["2 to 4 for description body and tags"],
  "long_tail": ["4 to 8 for description and chapter titles"],
  "difficulty_note": "which primaries are high-competition for a new channel",
  "source_artifacts": [],
  "note": "verify volume signals via trend-check or web-intel before recommending a primary"
}
```

## Do NOT use this atom for
- Stating exact search volume as fact (verify via `shared/web-intel-engine.md`, present as a range).
- Recommending a high-competition primary for a new channel without flagging the difficulty.
- Writing the SEO description (that is video-development or document-studio).

## Pipeline note
Follows `shared/method.md`. Platform SEO differences come from `shared/platform-engine.md`. The
creator's niche keyword library (configured via `creator-profile.local.json`) seeds the
cluster. Obeys `protocols/no-fabrication.md`.

---

---
file: skills/atoms/search-intent/SKILL.md
name: search-intent
description: "classifies search intent (informational/commercial/transactional/navigational) and best-fit content format for a home decor or DIY keyword; feeds title-generate and hook-write but does NOT write those outputs itself."
load:
  - shared/platform-engine.md
  - shared/brand-engine.md
  - protocols/no-fabrication.md
---

# search-intent

Classify the underlying searcher intent and format fit for a home decor or DIY keyword so that downstream atoms can tailor their output to what the searcher actually wants. This atom resolves four intent types (informational, commercial, transactional, navigational) against five format types (tutorial/how-to, inspiration/listicle, product-review/haul, transformation/before-after, trend/explainer) and returns a structured classification that title-generate, hook-write, and other downstream atoms consume to stay on-model for the query.

## Purpose

This atom exists because the same keyword can serve radically different searcher goals, and writing a hook or title without knowing intent produces generic output that fails to satisfy the underlying query. It accepts a keyword and an optional platform signal, reasons over the word-level and contextual signals in the keyword itself, and returns a structured intent label plus the most fitting content format. It does NOT write any creative copy, generate titles, or make live search calls.

## Inputs

```json
{
  "keyword": {
    "type": "string",
    "required": true,
    "description": "The search keyword or phrase to classify, e.g. 'moody living room ideas' or 'how to style a thrift store lamp'."
  },
  "platform": {
    "type": "string",
    "required": false,
    "enum": ["youtube", "pinterest", "tiktok"],
    "description": "Target platform. Informs format-fit scoring because format conventions differ across platforms. Omit to return a platform-agnostic classification."
  }
}
```

## Output

```json
{
  "tool": "search-intent",
  "keyword": "the input keyword, echoed back",
  "intent": {
    "label": "informational | commercial | transactional | navigational",
    "definition": "informational = searcher wants to learn or get ideas; commercial = searcher is evaluating products or approaches before buying; transactional = searcher is ready to act, buy, or download; navigational = searcher wants a specific creator, brand, or page"
  },
  "content_format_fit": {
    "primary": "tutorial/how-to | inspiration/listicle | product-review/haul | transformation/before-after | trend/explainer",
    "secondary": "optional second-best format if the keyword is ambiguous",
    "rationale": "one to two sentences explaining which signals in the keyword drove the format choice"
  },
  "confidence": {
    "value": "high | medium | low",
    "note": "high = unambiguous keyword signals; medium = one competing interpretation exists; low = keyword is too short or generic to classify reliably"
  },
  "rationale": "two to four sentences explaining the intent classification, referencing the specific word-level signals (modifier words, question framing, brand mentions, action verbs) that drove the decision",
  "notes": "any caveats, alternate reads, or flags for the downstream atom to consider; null if none"
}
```

## Do NOT use for

- Writing video titles or thumbnail text (use title-generate).
- Writing hooks or opening lines (use hook-write).
- Building keyword clusters or expanding a seed keyword into a list (use keyword-cluster).
- Scoring SEO difficulty, search volume, or ranking probability.
- Publishing any output directly to a platform or CRM record.

## Pipeline note

This atom classifies from keyword signals alone. It reads `shared/platform-engine.md` for platform-specific format conventions and `shared/brand-engine.md` to confirm format fit against the creator's content model, but it does NOT make live search calls or pull live SERP data. If fresh SERP context has already been retrieved by `web-intel-engine.md` and is present in the current context window, this atom may reference it; it will not initiate a new fetch. All classifications obey `protocols/no-fabrication.md`: if confidence is low, the atom returns `"confidence": "low"` and flags the ambiguity in `notes` rather than forcing a label.

---

---
name: hook-write
description: write ONE hook for a video or short that lands the promise or problem in the first seconds. Use when video-development, shortform-repurposing, or script-writer needs a hook. Do NOT use to write the full script or outline.
load:
  - shared/brand-engine.md
  - shared/voice-engine.md
---

# hook-write

Write a single hook in the creator's published voice.

## Input
```json
{
  "concept": "string",
  "persona": "the persona this serves",
  "platform": "youtube_longform | shorts | reels | tiktok",
  "duration_seconds": 30
}
```

## Output
```json
{
  "tool": "hook-write",
  "hook": "the spoken or on-screen hook line",
  "promise_or_problem": "what it establishes",
  "first_seconds": "copy for the opening window (3 seconds short-form, up to 30 long-form)",
  "note": "establish the promise or problem before any process content"
}
```

## Do NOT use this atom for
- A full outline or script (use script-section or script-writer).
- A title (use title-generate).

## Pipeline note
Follows `shared/method.md`. Voice comes from `shared/brand-engine.md` (published mode); opening-window
lengths come from `shared/platform-engine.md`. For short-form the hook must work with no prior context.

---

---
name: title-generate
description: generate a few title options for a video, human readable first and SEO aware second, front-loading the primary keyword. Use when video-development or seo-keywords needs titles. Do NOT use to write the thumbnail text (use thumbnail-concept) or the description.
---

# title-generate

Generate title options for one concept.

## Input
```json
{
  "concept": "string",
  "primary_keyword": "string",
  "style": "the aesthetic style label, for example vintage or modern",
  "platform": "youtube"
}
```

## Output
```json
{
  "tool": "title-generate",
  "titles": [
    {
      "title": "string",
      "chars": 0,
      "keyword_front_loaded": true
    }
  ],
  "note": "human readable first, SEO aware second; balance curiosity with clarity"
}
```

## Do NOT use this atom for
- Thumbnail overlay text (use thumbnail-concept).
- Overpromising beyond what the video delivers.

## Pipeline note
Follows `shared/method.md`. Title length and front-loading guidance come from
`shared/platform-engine.md` (roughly 80 to 100 characters for search and how-to). A useful pattern:
"[Action] My [Space] with [Approach] ([Style] Inspired)."

---

---
file: skills/atoms/script-section/SKILL.md
name: script-section
description: Write ONE named section of a YouTube video script for the creator in planning-to-the creator voice (speaking notes, second person). Sections are hook, intro, body-step, broll-cue, transition, cta, and outro. Use when any scripting or video-development workflow needs a single section drafted. Do NOT use to write a full script in one call; call this atom once per section and use workflow.json repeat per_section to compose the full script.
load:
  - shared/brand-engine.md
  - shared/voice-engine.md
---

# script-section

Write one named section of a YouTube video script in planning-to-the creator voice (speaking notes, second
person, "you'll say..."). Designed to be called once per section and composed into a full script via
workflow.json `repeat: per_section`.

## Purpose

Produce a single discrete script section that a spoke can assemble, in order, into a complete video
script. Each call writes exactly one section. The output is planning language addressed to the creator, not
published audience-facing copy. Tone is collaborative and practical (see "planning to the creator" mode in
`shared/brand-engine.md`).

The seven supported section types are:

- **hook** -- the opening moment (first 15 to 30 seconds on long-form; first 3 to 5 seconds on
  Shorts). States the promise or problem fast. Cuts long intros. Matches the platform opening-window
  rules in `shared/platform-engine.md`.
- **intro** -- brief context after the hook. Who you are, what the viewer will get, and why it
  matters to them. Keep it tight; retention drops in this window.
- **body-step** -- one numbered project step in conversational spoken form. Explain the action, the
  reason it matters, and any tip or watchout. Repeat this section type once per project step.
- **broll-cue** -- a production note section naming specific b-roll shots to capture at a given point
  in the script. Not spoken content; editor-facing only.
- **transition** -- a short spoken bridge (one to three sentences) that moves between two body steps
  or sections without losing momentum.
- **cta** -- the call-to-action window. Prompts subscribe, like, comment, or click. Warm and
  conversational; never pushy. Matches platform norms.
- **outro** -- closes the video. Teases the next video or playlist, thanks the viewer, signs off
  in the creator's voice.

## Inputs

```json
{
  "section_type": "hook | intro | body-step | broll-cue | transition | cta | outro (required)",
  "topic": "string (required) -- the video topic or project title, e.g. 'stylized bookshelf makeover'",
  "step_content": "string (optional, required when section_type is body-step) -- the specific step action and detail to convert into spoken script",
  "target_duration_seconds": "integer (optional) -- desired spoken length for this section in seconds",
  "platform": "youtube | shorts (optional, default youtube) -- determines opening-window timing and CTA norms"
}
```

Field notes:

- `section_type` controls the template, tone target, and timing expectation for the section.
- `topic` anchors brand voice, aesthetic, and relevance for every section type.
- `step_content` is required for `body-step`. Pass the action and detail from the step-sequence
  atom output. Omit for all other section types.
- `target_duration_seconds` is a planning target, not a guarantee. Actual delivery time varies by
  pace. If omitted, defaults apply by section type: hook 15 to 30 s (youtube) or 3 to 5 s (shorts);
  intro 30 to 60 s; body-step 60 to 120 s; broll-cue 0 s (not spoken); transition 5 to 15 s;
  cta 20 to 30 s; outro 15 to 30 s.
- `platform` shifts timing defaults and CTA language. On Shorts, hooks must work with zero prior
  context; see `shared/platform-engine.md`.

## Output

```json
{
  "section_type": "string -- mirrors the input section_type",
  "script_text": "string -- the speaking notes for the creator, written in second person planning voice (e.g. 'You'll open by holding up the before photo and saying: ...'). broll-cue sections contain editor notes, not spoken copy.",
  "duration_estimate_seconds": "integer -- rough estimate of spoken delivery time; 0 for broll-cue",
  "notes": "string or null -- timing or delivery tips for the creator (e.g. 'Pause here to let the before image land before moving on'). Null when no tips apply.",
  "broll_suggestion": "string or null -- a specific b-roll shot or sequence to capture at this point in the script. Always populated for broll-cue sections. Populated for other sections when a strong visual opportunity exists. Null otherwise."
}
```

Output rules:

- `script_text` is always in planning-to-the creator voice. Use "you" to address the creator. Write as speaking
  notes, not a verbatim teleprompter script: guide the delivery without locking every word. Example
  register: "You'll say something like: 'This corner was a disaster for two years, and I finally
  fixed it in one weekend.'"
- For `broll-cue` sections, `script_text` contains editor-facing production notes only (no spoken
  copy). `duration_estimate_seconds` is 0.
- `duration_estimate_seconds` is a rough planning range midpoint. Actual delivery time varies by pace
  and adlib. Never present it as a guaranteed runtime.
- `broll_suggestion` for non-broll-cue sections names one opportunistic shot. Keep it short and
  actionable ("overhead pour shot as you mix the stain").
- Do not fabricate product names, brand timings, measurements, or prices. If the input step_content
  references specifics, carry them through; do not invent new ones.
- Never use em dashes. Write ranges with "to" per `protocols/formatting-metadata.md`.
- Voice anchors to the home decor aesthetic and the bungalow context from `shared/brand-engine.md`.
  Warm, conversational, imperfect-is-fine energy.

## Do NOT use for

- Writing a full script in one call. Call this atom once per section; use `workflow.json`
  `repeat: per_section` in the parent spoke to compose the complete script.
- Writing audience-facing published copy such as captions, descriptions, or pin text (use
  caption-write or document-studio).
- Generating a hook for a Short without passing `platform: shorts`; the timing and no-context rules
  differ significantly from long-form.
- Writing project step sequences (use step-sequence atom to generate steps first, then pass each
  step's content here as `step_content`).
- Generating titles, thumbnails, or SEO metadata (use title-generate, thumbnail-concept, or
  seo-keywords).

## References

- `shared/brand-engine.md` -- voice modes; use "planning to the creator" mode for all output from this atom.
- `shared/platform-engine.md` -- hook opening-window lengths, Short vs long-form timing rules, and
  CTA norms per platform.
- `protocols/formatting-metadata.md` -- no em dashes; ranges use "to."
- `protocols/no-fabrication.md` -- do not invent measurements, product names, prices, or timings not
  present in the inputs.

---

---
file: skills/atoms/caption-write/SKILL.md
name: caption-write
description: write ONE platform-appropriate social media caption (hook line, body, CTA) in the creator's warm published-to-audience voice for an Instagram Reel, TikTok, YouTube Short, or Pinterest Pin. Use when shortform-repurposing, content-calendar, or any spoke needs a ready-to-post caption. Do NOT use to write a full video script, a long-form YouTube description, or a title card.
load:
  - shared/brand-engine.md
  - shared/platform-engine.md
  - shared/voice-engine.md
  - protocols/safety.md
---

# caption-write

Write a single social caption ready for publishing: hook line, body, and CTA. Voice is published-to-audience mode (warm, specific, draws the viewer in). Character count is enforced per platform.

## Purpose

Produce one caption per call, scoped to the target platform. The caption must open with the hook line, flow naturally through a brief body, and close with a CTA. If the post is sponsored, gifted, or affiliate, the output flags that an FTC disclosure line is required before publishing and returns the correct disclosure tag.

## Inputs

```json
{
  "topic": "string (the content topic or working title)",
  "platform": "instagram-reel | tiktok | shorts | pinterest",
  "hook_angle": "optional string (angle or emotion to lead with)",
  "persona": "optional string (persona this post serves, from shared/brand-engine.md)",
  "sponsored": "optional bool (default false)",
  "gifted": "optional bool (default false)",
  "affiliate": "optional bool (default false)"
}
```

Field notes:
- `topic` is required. Pass the working title or a plain description of the content.
- `platform` is required. It controls character limits and tone calibration.
- `hook_angle`, `persona`, `sponsored`, `gifted`, and `affiliate` are optional; omit any you do not have.
- More than one of `sponsored`, `gifted`, `affiliate` may be true at once.

## Output

```json
{
  "tool": "caption-write",
  "platform": "instagram-reel | tiktok | shorts | pinterest",
  "hook_line": "string (opening line used inside caption)",
  "caption": "string (full caption: hook line + body + CTA, within platform character limit)",
  "cta": "string (the call-to-action line, also embedded in caption)",
  "ftc_disclosure_line": "#ad | #gifted | #affiliate | null",
  "character_count": 0,
  "notes": "string or null (flags, suggestions, or truncation warnings)"
}
```

### Character limits (enforced)

| Platform | Limit | Notes |
|---|---|---|
| instagram-reel | 2200 chars | Full caption; only the first 125 chars show before "more" |
| tiktok | 2200 chars | Full caption; front-load the hook |
| shorts | 100 chars | Only the first ~100 chars are visible without expanding; keep the full caption within this limit |
| pinterest | 500 chars | Description field; keyword-forward, no hashtag clutter |

If the draft exceeds the platform limit, trim body copy first, preserve the hook line and CTA, and set `notes` to explain what was shortened.

### FTC disclosure logic

- If `sponsored` is true: `ftc_disclosure_line` returns `"#ad"`.
- If `gifted` is true and `sponsored` is false: `ftc_disclosure_line` returns `"#gifted"`.
- If `affiliate` is true (and neither sponsored nor gifted): `ftc_disclosure_line` returns `"#affiliate"`.
- If more than one flag is true, use the strictest applicable tag (`#ad` outranks the others) and note the others in `notes`.
- If all three are false or omitted: `ftc_disclosure_line` returns `null`.

The disclosure line must appear in the final published caption before it goes live. This atom flags the requirement and returns the tag; the human is responsible for placement. See `protocols/safety.md`.

## Do NOT use for

- Full YouTube video descriptions (use the description-write atom or the relevant spoke).
- Video titles or thumbnail text (use title-generate or thumbnail-concept).
- Scripts or spoken voiceover copy (use hook-write or script-writer).
- Batch caption generation across multiple posts in one call; call once per post.
- Any caption where brand voice, persona, or platform specs have not been loaded; always load `shared/brand-engine.md` and `shared/platform-engine.md` before writing.

## Pipeline note

Voice and persona guidance come from `shared/brand-engine.md` (published-to-audience mode: warm, specific, draws the viewer in; no corporate tone, no em dashes). Platform character limits, hashtag conventions, and opening-window rules come from `shared/platform-engine.md`. Sponsored-content disclosure requirements come from `protocols/safety.md`. This atom does not fabricate engagement metrics, brand names, or product claims; see `protocols/no-fabrication.md`.

---

---
name: trend-check
description: verify current momentum for a topic via web-intel-engine before a spoke recommends it, and mark stale data honestly. Use when content-strategy, seo-keywords, or seasonal-trends needs a freshness check on a trend. Do NOT invent momentum; if retrieval fails, record a gap.
---

# trend-check

Check whether a topic is rising, flat, or declining using real retrieval, and flag stale or missing
data rather than guessing.

## Input
```json
{
  "topic": "string",
  "platform": "youtube | pinterest | tiktok | google",
  "freshness_days": 14
}
```

## Output
```json
{
  "tool": "trend-check",
  "topic": "string",
  "momentum": "rising | flat | declining | unknown",
  "source_artifacts": [],
  "retrieval_gaps": [],
  "freshness_note": "string or null",
  "note": "momentum unknown is a valid, honest answer"
}
```

## Do NOT use this atom for
- Asserting momentum without retrieval. If `web-intel-engine` returns nothing usable, set momentum to
  unknown and record a retrieval gap with gap-record.
- Keyword volume or difficulty (use keyword-cluster).

## Pipeline note
Calls `shared/web-intel-engine.md` (Levels 1 through 6) and passes any external content through
`shared/injection-guard-engine.md` first. Obeys `protocols/research-citation.md` recency windows; data
older than `freshness_days` is marked stale, not dropped. Never fabricate (`protocols/no-fabrication.md`).

---

---
file: skills/atoms/competitor-scan/SKILL.md
name: competitor-scan
description: research competitor creators or videos in the moody/vintage home decor and DIY niche on YouTube, Pinterest, or TikTok; surface content gaps, overserved topics, and differentiation angles for the creator. Use when content-strategy, seo-keywords, or video-development needs a competitive landscape read before recommending a topic. Do NOT use to assert subscriber counts, view counts, or engagement rates as fact; all scale estimates and metrics must be marked [unverified] if not retrieved from a live API response.
load:
  - shared/web-intel-engine.md
  - protocols/no-fabrication.md
---

# competitor-scan

Research the competitive landscape for a given topic or keyword in the moody/vintage home decor and
DIY niche, surface what competitors are doing, what is overserved, and where the creator has room to
differentiate.

## Purpose

Provide a grounded, retrieval-backed picture of who is covering a topic, how they are covering it,
and what angles or sub-topics are thin or absent in the niche. All scale estimates are coarse
(small/medium/large) and sourced from live retrieval where possible; anything not confirmed by
retrieval is labeled [unverified] and flagged for manual check. The atom never invents channel
names, video titles, subscriber counts, view counts, or specific metrics.

## Inputs

```json
{
  "topic": "string  -- the keyword or content topic to research (required)",
  "platform": "youtube | pinterest | tiktok  -- the platform to search (required)",
  "count": "integer  -- number of competitors to surface (default: 5, max: 10)"
}
```

- `topic`: a keyword phrase or content concept (for example, "home decor bedroom makeover" or
  "vintage thrift flip DIY").
- `platform`: one of the three supported platforms. Pass one platform per call; run the atom twice
  for cross-platform comparison.
- `count`: how many distinct competitor entries to return. Defaults to 5 if omitted.

## Output

```json
{
  "tool": "competitor-scan",
  "topic": "string",
  "platform": "youtube | pinterest | tiktok",
  "competitors": [
    {
      "name": "string -- channel, account, or creator name as found in retrieval; [unverified] if not confirmed",
      "url_if_found": "string or null -- direct URL to channel/profile/board if retrieved; null if not found",
      "estimated_scale": "small | medium | large -- coarse size tier based on retrieval signals; always [unverified] unless sourced from a live API",
      "content_angle": "string -- how this creator covers the topic (style, format, tone, production level)",
      "gap_or_differentiation": "string -- what this creator does NOT do, or where the creator's brand could stand apart from them"
    }
  ],
  "overserved_angles": ["list of sub-topics or formats that multiple competitors already cover heavily"],
  "underserved_angles": ["list of sub-topics, formats, or aesthetics with thin or no coverage found"],
  "overall_gap_summary": "string -- one-paragraph synthesis of the most actionable differentiation opportunity for the creator in this topic on this platform",
  "confidence": "high | medium | low -- based on retrieval quality: high means multiple live sources returned; medium means partial retrieval or mixed freshness; low means retrieval largely failed or returned thin results",
  "retrieval_gaps": [],
  "source_artifacts": [],
  "fabrication_flags": ["list any field that could not be verified and is marked [unverified]"]
}
```

Scale tier definitions (for `estimated_scale`):
- `small`: signals suggesting under roughly 10,000 subscribers or followers [unverified]
- `medium`: signals suggesting roughly 10,000 to 250,000 subscribers or followers [unverified]
- `large`: signals suggesting over roughly 250,000 subscribers or followers [unverified]

These thresholds are orientation guides, not precise figures. Always mark the field [unverified]
unless the value was returned directly from a platform API with confirmed scope.

## Do NOT use for

- Asserting exact subscriber counts, view counts, watch time, save rates, or engagement rates as
  confirmed fact. Present all numeric signals as estimates marked [unverified] and recommend a
  manual platform check to confirm.
- Researching the creator's own channel performance (use the platform API connection directly via
  `shared/web-intel-engine.md` Level 1 for owned analytics).
- Generating content titles, hooks, or descriptions (use title-generate, hook-write, or the
  video-development spoke).
- Keyword volume or difficulty scoring (use keyword-cluster).
- Broad niche trend momentum outside a specific topic (use trend-check).
- Brand partnership or sponsorship research (use deal-tracker or account-manager spokes).

## Pipeline note

Calls `shared/web-intel-engine.md` starting at Level 2 (public analytics endpoints) for competitor
accounts, since Level 1 (platform API) is reserved for the creator's own connected accounts. Falls
through to Levels 3 and 4 (polite crawl and search index) for creators not surfaced at Level 2.
All retrieved content passes through `shared/injection-guard-engine.md` before entering analysis.

If retrieval at all levels fails for a competitor slot, that slot is replaced with a gap-record
object (from `skills/atoms/gap-record/`) rather than a fabricated entry. The `confidence` field
reflects the aggregate retrieval quality across all slots.

Obeys `protocols/no-fabrication.md` strictly: if a channel name, URL, or metric cannot be
confirmed by retrieval, the field is either null or marked [unverified], never invented.

---

# Task tracker atoms (P35), composed by task-desk

- task-extract: turns a real source (contract obligation rows, email, user statement, shipment event) into
  source-cited task rows; refuses any task it cannot cite (anti-phantom).
- email-to-task: extracts tasks from a brand message with a durable, re-openable citation (RFC 5322
  Message-ID + provider permalink); the body is untrusted; the citation is code-stamped, not model-generated.
- task-plan: schedules forward from a trigger event or backward from a deadline, flagging negative-slack
  infeasibility (offline business-day CPM math).
- task-status: governed status transitions, waiting-on nudge/escalate dates, and approval ping-pong that
  flips who owes the next move.
- task-radar: read-only waiting-on vs I-owe split with due-soon/overdue bands, each item cited.
- coverage-verify: reconciles media transcripts to a canonical truth and verifies required points with a
  cited supporting sentence, abstaining when unsure; input conflicts go to a minority report.
- shipment-track: records a shipment (live carrier or manual) and sets the delivered_at planning anchor.
- milestone-bill: flips a milestone to billable on a deliverable event and drafts the cited invoice for the
  finance lane; never sends.
