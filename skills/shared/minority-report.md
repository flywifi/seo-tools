# Minority Report Policy — seo-tools

When two data sources disagree on a factual claim in an SEO context (e.g., two crawlers
return different canonical URLs, or two SERP snapshots show different ranking positions),
the skill must emit a minority report rather than silently resolving the conflict.

## Required minority report buckets

```json
{
  "minority_report": {
    "decision_log": {
      "chosen_interpretation": "string — the primary source and what it says",
      "why_it_won": "string — reason the primary source was chosen"
    },
    "conflicts": [
      {
        "source": "string — source name/URL",
        "value": "any — what this source reported"
      }
    ],
    "failed_to_merge": [],
    "residual_uncertainty": {
      "what_would_resolve_it": "string — e.g. 'Fresh crawl within 24h'"
    }
  }
}
```

## When to emit

- Two crawlers return different canonical URLs for the same page
- Two SERP snapshots show ranking positions differing by >3 positions
- Structured data extraction finds conflicting schema.org values in the same page
- Link analysis tools disagree on domain authority / link count by >20%

## When NOT to emit

- One source is clearly stale (timestamp >7 days older than the other)
- The difference is within normal measurement variance (<5% for metrics, <1 position for rankings)
- Only one source has data (no conflict to report)

## Source precedence for SEO data

1. Direct crawl of the canonical URL (most authoritative)
2. Google Search Console API data (Google's own view)
3. Third-party SEO tools (Ahrefs, Semrush, Moz)
4. Cached/historical snapshots (Wayback Machine, CommonCrawl)
