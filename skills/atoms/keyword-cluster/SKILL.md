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
