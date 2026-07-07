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

## Cross-modality
Inherits its calling spoke's class (varies by caller (A/B)); see `shared/cross-modality-engine.md`. An atom carries no independent surface wiring and runs wherever the spoke that composes it runs.
