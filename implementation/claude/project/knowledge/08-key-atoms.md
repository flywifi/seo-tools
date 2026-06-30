---
files_combined:
  - skills/atoms/keyword-compare/SKILL.md
  - skills/atoms/keyword-cluster/SKILL.md
  - skills/atoms/search-intent/SKILL.md
  - skills/atoms/hook-write/SKILL.md
  - skills/atoms/title-generate/SKILL.md
  - skills/atoms/script-section/SKILL.md
  - skills/atoms/caption-write/SKILL.md
  - skills/atoms/trend-check/SKILL.md
  - skills/atoms/competitor-scan/SKILL.md
note: These nine atoms are the most frequently called. Spokes compose them; users can also invoke them directly as shortcuts.
---

---
name: keyword-compare
atom: true
description: compare 1 to 10 keywords side-by-side across platforms (YouTube, Pinterest, TikTok, Google) and optionally across a seasonal window, producing a structured matrix of intent, SERP feature, format fit, competition estimate, and seasonal relevance per keyword-platform pair plus three cross-platform verdicts (universal, platform-exclusive, niche long-tail). Use when the creator wants to decide which platform to prioritize for a keyword or batch of keywords without running four separate queries. Do NOT use for keyword research from scratch (use keyword-cluster or long-tail-expand first), seasonal planning without existing keywords (use seasonal-trends), or full SEO strategy output (use the seo-keywords spoke).
load:
  - shared/seo-intelligence-engine.md
  - shared/platform-engine.md
  - protocols/no-fabrication.md
  - protocols/formatting-metadata.md
---

# keyword-compare

Compare keywords across platforms. Returns a matrix plus cross-platform verdicts.

## Inputs
```json
{
  "keywords": ["1 to 10 strings"],
  "platforms": ["youtube", "pinterest", "tiktok", "google"],
  "season": "fall | holiday | spring | summer | evergreen",
  "check_trend_momentum": false
}
```

## Output
```json
{
  "comparison_matrix": [{
    "keyword": "string",
    "cross_platform_verdict": "universal | platform_specific | niche_long_tail",
    "strongest_platform": "string",
    "platform_profiles": [{
      "platform": "string",
      "intent": "informational | commercial | transactional | navigational",
      "format_fit": "long-form | short-form | pin | reel",
      "serp_feature": "video_carousel | image_pack | featured_snippet | shopping | local_pack",
      "competition_estimate": "low [estimated] | medium [estimated] | high [estimated]",
      "seasonal_relevance": "peak | moderate | off_season | evergreen | null",
      "momentum": "rising | flat | declining | unknown | null",
      "recommendation": "one-sentence action"
    }]
  }],
  "universal_keywords": [],
  "platform_exclusive_opportunities": { "youtube": [], "pinterest": [], "tiktok": [], "google": [] },
  "seasonal_timing_summary": "string or null",
  "retrieval_gaps": []
}
```

## Fabrication rules
- `competition_estimate` always labeled `[estimated]`. Never cite volume numbers without an API source.
- `momentum` only present when `check_trend_momentum: true` AND trend-check returned non-null.
- `seasonal_relevance` only present when `season` input is provided.

---

---
name: keyword-cluster
description: build a keyword cluster (primary, secondary, long-tail) for a topic on a target platform, with a difficulty note for a new channel. Do NOT assert search volume without web-intel verification.
---

# keyword-cluster

Build one keyword cluster for one topic and platform.

## Input
```json
{ "topic": "string", "platform": "youtube | pinterest | google" }
```

## Output
```json
{
  "tool": "keyword-cluster",
  "primary": ["1 to 2 exact-phrase keywords for the title"],
  "secondary": ["2 to 4 for description body and tags"],
  "long_tail": ["4 to 8 for description and chapter titles"],
  "difficulty_note": "which primaries are high-competition for a new channel",
  "note": "verify volume signals via trend-check or web-intel before recommending a primary"
}
```

## Do NOT use for
- Stating exact search volume as fact.
- Recommending a high-competition primary for a new channel without flagging difficulty.
- Writing the SEO description (use video-development or document-studio).

---

---
name: search-intent
atom: true
description: "classifies search intent (informational/commercial/transactional/navigational) and best-fit content format for a home decor or DIY keyword; feeds title-generate and hook-write but does NOT write those outputs itself."
load:
  - shared/platform-engine.md
  - shared/brand-engine.md
  - protocols/no-fabrication.md
---

# search-intent

Classify the underlying searcher intent and format fit for a home decor or DIY keyword.

## Inputs
```json
{
  "keyword": "string (required)",
  "platform": "youtube | pinterest | tiktok (optional)"
}
```

## Output
```json
{
  "keyword": "echoed",
  "intent": { "label": "informational | commercial | transactional | navigational", "definition": "string" },
  "content_format_fit": { "primary": "tutorial/how-to | inspiration/listicle | product-review/haul | transformation/before-after | trend/explainer", "secondary": "optional", "rationale": "string" },
  "confidence": { "value": "high | medium | low", "note": "string" },
  "rationale": "2 to 4 sentences explaining the classification",
  "notes": "caveats or alternate reads; null if none"
}
```

## Do NOT use for
- Writing video titles or hooks (use title-generate, hook-write).
- Building keyword clusters (use keyword-cluster).
- Scoring SEO difficulty or search volume.

---

---
name: hook-write
description: write ONE hook for a video or short that lands the promise or problem in the first seconds. Do NOT use to write the full script or outline.
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

Voice from `shared/voice-engine.md` (published mode). No em dashes. Opening-window lengths from
`shared/platform-engine.md`. For short-form the hook must work with no prior context.

---

---
name: title-generate
description: generate a few title options for a video, human readable first and SEO aware second, front-loading the primary keyword. Do NOT use to write thumbnail text (use thumbnail-concept) or the description.
---

# title-generate

Generate title options for one concept.

## Input
```json
{
  "concept": "string",
  "primary_keyword": "string",
  "style": "moody vintage",
  "platform": "youtube"
}
```

## Output
```json
{
  "tool": "title-generate",
  "titles": [{ "title": "string", "chars": 0, "keyword_front_loaded": true }],
  "note": "human readable first, SEO aware second; balance curiosity with clarity"
}
```

Pattern: "[Action] My [Space] with [Approach] ([Style] Inspired)." Target 80 to 100 characters.

---

---
name: script-section
atom: true
description: Write ONE named section of a YouTube video script for the creator in planning-to-creator voice. Sections are hook, intro, body-step, broll-cue, transition, cta, and outro. Call once per section; use workflow.json repeat per_section to compose the full script.
load:
  - shared/brand-engine.md
  - shared/voice-engine.md
---

# script-section

Write one named section of a YouTube video script in planning-to-creator voice (speaking notes,
second person, "you'll say...").

## Section types
- **hook**: opening moment (15 to 30 s long-form; 3 to 5 s Shorts)
- **intro**: brief context after the hook
- **body-step**: one numbered project step in conversational spoken form
- **broll-cue**: production note naming specific b-roll shots (not spoken)
- **transition**: short bridge between sections
- **cta**: call-to-action window
- **outro**: closes the video

## Inputs
```json
{
  "section_type": "hook | intro | body-step | broll-cue | transition | cta | outro",
  "topic": "string (required)",
  "step_content": "string (required when section_type is body-step)",
  "target_duration_seconds": "integer (optional)",
  "platform": "youtube | shorts (default youtube)"
}
```

## Output
```json
{
  "section_type": "string",
  "script_text": "planning voice speaking notes addressed to the creator",
  "duration_estimate_seconds": 0,
  "notes": "timing or delivery tips; null if none",
  "broll_suggestion": "specific shot; null if none"
}
```

Output rules: always planning-to-creator voice ("you'll say..."). Never teleprompter. Never em dashes.
Ranges use "to". Do not fabricate product names, measurements, or prices.

---

---
name: caption-write
atom: true
description: write ONE platform-appropriate social media caption (hook line, body, CTA) in the creator's warm published-to-audience voice for an Instagram Reel, TikTok, YouTube Short, or Pinterest Pin. Do NOT use to write a full video script or a long-form YouTube description.
load:
  - shared/brand-engine.md
  - shared/platform-engine.md
  - shared/voice-engine.md
  - protocols/safety.md
---

# caption-write

Write a single social caption ready for publishing: hook line, body, and CTA.

## Inputs
```json
{
  "topic": "string (required)",
  "platform": "instagram-reel | tiktok | shorts | pinterest (required)",
  "hook_angle": "optional",
  "persona": "optional",
  "sponsored": false,
  "gifted": false,
  "affiliate": false
}
```

## Output
```json
{
  "platform": "string",
  "hook_line": "string",
  "caption": "full caption within platform limit",
  "cta": "string",
  "ftc_disclosure_line": "#ad | #gifted | #affiliate | null",
  "character_count": 0,
  "notes": "flags or truncation warnings; null if none"
}
```

## Character limits (enforced)
| Platform | Limit | Notes |
|---|---|---|
| instagram-reel | 2200 | First 125 chars show before "more" |
| tiktok | 2200 | Front-load the hook |
| shorts | 100 | Keep entire caption within this limit |
| pinterest | 500 | Keyword-forward, no hashtag clutter |

## FTC logic
- sponsored true: `#ad`
- gifted true (not sponsored): `#gifted`
- affiliate true (not sponsored/gifted): `#affiliate`
- Multiple flags: use strictest (`#ad` outranks others)

---

---
name: trend-check
description: verify current momentum for a topic via web-intel-engine before a spoke recommends it, and mark stale data honestly. Do NOT invent momentum; if retrieval fails, record a gap.
---

# trend-check

Check whether a topic is rising, flat, or declining using real retrieval.

## Input
```json
{ "topic": "string", "platform": "youtube | pinterest | tiktok | google", "freshness_days": 14 }
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

Calls `shared/web-intel-engine.md` (Levels 1 through 6). Data older than `freshness_days` is marked
stale, not dropped. Never fabricate (`protocols/no-fabrication.md`).

---

---
name: competitor-scan
atom: true
description: research competitor creators or videos in the moody/vintage home decor and DIY niche on YouTube, Pinterest, or TikTok; surface content gaps, overserved topics, and differentiation angles. Do NOT assert subscriber counts, view counts, or engagement rates as fact; all scale estimates must be marked [unverified] if not retrieved from a live API response.
load:
  - shared/web-intel-engine.md
  - protocols/no-fabrication.md
---

# competitor-scan

Research the competitive landscape for a topic in the moody/vintage home decor and DIY niche.

## Inputs
```json
{
  "topic": "string (required)",
  "platform": "youtube | pinterest | tiktok (required)",
  "count": "integer (default 5, max 10)"
}
```

## Output
```json
{
  "tool": "competitor-scan",
  "topic": "string",
  "platform": "string",
  "competitors": [{
    "name": "string [unverified if not confirmed]",
    "url_if_found": "string or null",
    "estimated_scale": "small | medium | large [unverified]",
    "content_angle": "string",
    "gap_or_differentiation": "string"
  }],
  "overserved_angles": [],
  "underserved_angles": [],
  "overall_gap_summary": "string",
  "confidence": "high | medium | low",
  "retrieval_gaps": [],
  "fabrication_flags": []
}
```

Scale tiers are orientation guides, not precise figures. Always `[unverified]` unless from a
platform API. Starts at Level 2 web-intel (not Level 1, which is reserved for owned accounts).

## Do NOT use for
- Asserting exact subscriber counts or engagement rates as confirmed fact.
- Researching the creator's own channel performance (use web-intel Level 1).
- Keyword volume or difficulty scoring (use keyword-cluster).
- Brand partnership research (use account-manager).
