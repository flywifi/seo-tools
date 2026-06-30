---
name: geo-optimize
atom: true
description: Given a video title, description draft, and optional chapter outline, produces
  GEO/AEO optimization artifacts: chapter timestamp list with keyword-rich titles, VideoObject
  schema annotation notes, and a companion blog post outline that enables dual-ranking across
  YouTube Search and Google Search while building AI citation authority. Do NOT use for
  keyword research or SEO strategy — use long-tail-expand and topical-authority-map for those.
engines_required:
  - shared/seo-intelligence-engine.md
  - shared/brand-engine.md
  - shared/platform-engine.md
protocols:
  - protocols/no-fabrication.md
  - protocols/formatting-metadata.md
---

# geo-optimize

## When to use this atom

Use this atom when a video title, description, and rough chapter structure are finalized
(or drafted by script-section) and the goal is to maximize the video's discoverability in
both traditional search and AI-citation systems. Triggers: "optimize this for AI search,"
"create chapter markers," "write a blog post outline for this video," "help this show up in
AI answers," "dual-ranking strategy."

Do NOT use for keyword strategy — use `keyword-cluster`, `long-tail-expand`, or
`topical-authority-map` first, then pass results here.

## Inputs

Required:
- `video_title`: the finalized or working title of the video
- `video_description_draft`: the current description draft (at minimum the first 300 characters)

Optional (improves output significantly):
- `chapter_outline`: list of {timestamp_seconds, chapter_topic} entries from script-section
- `primary_keyword`: the target keyword this video is optimized for
- `entity_list`: named brands, products, and techniques mentioned in the video (from entity-extract)
- `platform_targets`: defaults to ["youtube", "google"] if not provided

## Core procedure

Follow `shared/method.md`.

### Step 1: Chapter timestamp optimization

If `chapter_outline` is provided, rewrite each chapter title to be keyword-rich and descriptive.
Rules:
- Each chapter title should be 3 to 8 words that could stand alone as a search query
- Use entity names where applicable ("Rust-Oleum Chalked Paint step" not "painting step")
- Format: `{MM:SS} {Keyword-rich chapter title}`
- First chapter at `00:00` is required; title it with the primary keyword or transformation hook
- Minimum 3 chapters for Key Moments eligibility in Google SERP

If no `chapter_outline` provided, generate a suggested chapter structure based on the description
draft. Label all generated chapter suggestions `[suggested — requires timestamp adjustment]`.

### Step 2: Description SEO annotation

Annotate the first 300 characters of the description for keyword density:
- Primary keyword should appear in the first 125 characters
- 1 to 3 named entities in the first 300 characters
- Chapter timestamps block (from step 1) placed after the opening paragraph
- Links to related cluster videos (placeholder text: `[link to {topic} video]`)

Output the annotated description as a diff from the input draft.

### Step 3: Companion blog post outline

Produce a companion blog post outline that:
- Uses the same primary keyword in the H1 title
- Embeds the YouTube video (placeholder: `[embed: {video_title}]`)
- Includes a written chapter-by-chapter summary (1 to 2 sentences per chapter)
- Names the same entities that are spoken in the video
- Ends with 3 to 5 internal link suggestions to other cluster videos
- Targets the "how-to" or "best of" SERP feature for the keyword type (from SERP feature map)

Format as a structured markdown outline, not prose. Label it `companion_blog_post_outline`.

### Step 4: VideoObject schema notes

Summarize what the creator needs to know about the VideoObject schema for this specific video:
- YouTube auto-populates: name, description, thumbnailUrl, uploadDate — no additional action needed
- What the creator controls: title accuracy, description (first 300 chars indexed), chapter timestamps
- If companion blog post is published: note the `hasPart` and `SeekToAction` markup that can be
  added to the blog post's VideoObject to surface chapter links in Google SERP
- Flag: "Key Moments in Google Search require at least 3 chapter timestamps in the description"

Do not generate raw JSON-LD schema — that is a web developer artifact. Provide actionable notes
on what the creator needs to do (or not do) to maximize VideoObject indexability.

### Step 5: AI citation assessment

Based on the inputs, rate the video's AI citation readiness on 3 dimensions:
- `entity_density`: are named entities (brands, products, techniques) present in the title and
  description? (high / medium / low)
- `chapter_structure`: are chapters present and keyword-rich? (high / medium / low / absent)
- `companion_post_exists`: does the creator plan a blog post? (yes / planned / no)

Emit a `geo_readiness_score` as a simple sum: high=2, medium=1, low/absent/no=0. Max = 6.
Score 5 to 6: strong AI citation candidate. 3 to 4: moderate. Below 3: recommend improvements.

## Output contract

Emit a JSON object with:
```json
{
  "video_title": "...",
  "primary_keyword": "...",
  "chapter_timestamps": [
    { "timestamp": "00:00", "title": "...", "suggested": false }
  ],
  "description_annotation": {
    "first_300_chars_optimized": "...",
    "changes_from_input": "..."
  },
  "companion_blog_post_outline": { ... },
  "videoobject_notes": [ "..." ],
  "geo_readiness": {
    "entity_density": "high | medium | low",
    "chapter_structure": "high | medium | low | absent",
    "companion_post_exists": "yes | planned | no",
    "geo_readiness_score": 0
  },
  "retrieval_gaps": []
}
```

`retrieval_gaps`: list any information that was not provided and would materially improve the
output (e.g., "chapter_outline not provided — timestamps are suggested, not confirmed").

Always honor `protocols/formatting-metadata.md`: no em dashes in user-facing text fields;
ranges use "to"; no fabricated entity names or schema property values.

## Engines and protocols loaded

- `shared/seo-intelligence-engine.md` (GEO/AEO section, chapter markers, SERP feature map)
- `shared/brand-engine.md` (voice and identity alignment for companion post outline)
- `shared/platform-engine.md` (YouTube chapter timestamp requirements)
- `protocols/no-fabrication.md` (no invented entity names, no fake schema values)
- `protocols/formatting-metadata.md` (no em dashes, ranges with "to")

## Standalone usability

Produces chapter timestamp list, description annotation, and companion blog post outline from
a video title and description draft alone, with no downstream skill required.

## Failure modes

- If chapter_outline is absent and the description is too sparse to infer structure: set
  `chapter_timestamps` to `[]` and note in `retrieval_gaps`.
- If primary_keyword is absent: use the most prominent noun phrase from the title; flag as
  `[inferred from title — verify against keyword research]`.
- If entity_list is absent: do not fabricate entity names; extract only those explicitly
  present in the title and description inputs.
