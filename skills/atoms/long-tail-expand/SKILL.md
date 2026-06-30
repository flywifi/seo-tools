---
name: long-tail-expand
description: Given a seed keyword, generate 20 to 40 long-tail keyword variations using 5 expansion
  methods (YouTube autocomplete traversal, Google PAA tree, related searches, community question
  mining, and product search adjacency), each traversed 2 levels from the seed. Returns keywords
  ranked by niche relevance. Do NOT use for broad competitive keyword research (use keyword-cluster)
  or intent classification (use search-intent).
version: 1.0.0
lane: content
atom: true
load:
  - shared/seo-intelligence-engine.md
  - shared/web-intel-engine.md
  - shared/platform-engine.md
  - protocols/no-fabrication.md
---

# long-tail-expand

## What it does

Expands one seed keyword into 20 to 40 long-tail variations by systematically applying the five
expansion methods documented in `shared/seo-intelligence-engine.md`. Traversal is 2 levels deep
from the seed — the seed surfaces first-level candidates, which themselves yield second-level
candidates. Results are scored and ranked by niche relevance to the moody-vintage home decor niche.

## Input

```json
{
  "seed_keyword": "string — the starting keyword (typically the primary keyword from keyword-cluster)",
  "platform": "youtube | pinterest | google",
  "count": 30,
  "methods": ["autocomplete", "paa", "related", "community", "product"]
}
```

`methods` defaults to all five if omitted. Individual methods can be excluded (e.g. omit "product"
when the topic has no adjacent product search behavior).

## Output

```json
{
  "seed_keyword": "string",
  "platform": "string",
  "long_tail_keywords": [
    {
      "keyword": "string",
      "expansion_method": "autocomplete | paa | related | community | product",
      "expansion_depth": 1,
      "intent": "informational | inspirational | transactional | navigational",
      "niche_relevance_score": "1 to 5",
      "estimated_competition": "low | medium | high",
      "volume_estimate": "[estimated, unverified]"
    }
  ],
  "expansion_depth_reached": 2,
  "total_candidates_found": "integer",
  "retrieval_gaps": []
}
```

## Rules

- All `volume_estimate` values must be labeled `[estimated, unverified]`. No tool in this system
  has direct API access to search volume data. Google Trends signals may be used as a proxy
  with this label; if no signal is available, omit the field rather than guessing.
- `niche_relevance_score` 1 to 5: 5 = clearly within moody-vintage home decor niche; 1 = generic
  or off-niche. Never include keywords below 2.
- `expansion_depth` 1 = direct expansion from seed; 2 = expansion of a depth-1 candidate.
- Do not exceed depth 2 without explicit caller instruction.
- `estimated_competition` is based on keyword length and specificity (3 to 6 words = low/medium;
  1 to 2 words = high); not from any live API. Label is a heuristic, not a verified figure.

## Engines and protocols loaded

- shared/seo-intelligence-engine.md (5-method expansion methodology, PAA tree process)
- shared/web-intel-engine.md (live autocomplete and PAA retrieval via Levels 2 and 3)
- shared/platform-engine.md (platform-specific keyword format conventions)
- protocols/no-fabrication.md (volume labeling rule)
