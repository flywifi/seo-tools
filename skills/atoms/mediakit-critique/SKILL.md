---
name: mediakit-critique
atom: true
standalone: true
description: "critiques a creator's own media kit against the market: compares each metric the kit claims (CTR, AVD, engagement rate, views, subscribers, RPM) to the industry benchmark ranges via benchmark-compare, checks rate figures against the structured rate rows, and reviews the kit's structure (required sections, personal-vs-industry rate labeling, FTC disclosure, sourced claims). When the benchmark rows are unsourced (currently null) it degrades to structural_only: it names each unsourced benchmark in data_gaps and withholds market-position claims rather than inventing one. Do NOT use to GENERATE a media kit (that is partnership-mediakit's mediakit-section), to score the internal Quality Gates (that is quality-review), or to fabricate the creator's metrics (numbers come from the kit; benchmarks come from the file, sourced-or-null)."
engines_required:
  - shared/platform-engine.md
  - shared/brand-engine.md
protocols:
  - protocols/no-fabrication.md
  - protocols/research-citation.md
---

# mediakit-critique

The outside-in read on a media kit: does it stand up to the market, and is it put together well?
It compares the kit's own numbers to benchmark ranges and reviews its structure. It never invents
a benchmark and never scores the internal quality gates (that is quality-review's job).

## When to use this skill
- "here's my media kit, do market research and give me critiques", "how do my stats compare to
  the industry?", "critique my rate card" reached through the partnership-mediakit
  `content_critique` action.

Do NOT use for:
- Generating or drafting the media kit itself (use `mediakit-section`, `rate-card-fill`,
  `pitch-paragraph`).
- Scoring the nine internal Quality Gates dimensions (that is `quality-review` /
  `quality_check`); those are integrity and safety gates, not market position.
- Fabricating the creator's metrics. Every claimed number comes from the kit; every benchmark
  comes from `canonical-sources/rate-benchmarks/benchmarks.json`, sourced-or-null.

## Input
```json
{
  "media_kit": "object -- the kit's claimed metrics {ctr, avd, engagement_rate, views, subscribers, rpm} and rate figures, plus its sections",
  "platform": "youtube | instagram | tiktok | pinterest (required for benchmark rows)",
  "niche": "string (optional; defaults to home-decor-diy)"
}
```

## Core procedure
1. For each metric the kit claims, call `benchmark-compare` with the kit's real number as
   `alex_value`. Collect each `gap_assessment` (above / below / within / unknown) and the range.
2. Determine `critique_mode`. If every benchmark row for the requested metrics has a null range
   (the current sourced-or-null state of the file), set `critique_mode: "structural_only"`, add
   each unsourced metric to `data_gaps[]`, and WITHHOLD market-position claims. If at least one
   range is sourced, set `critique_mode: "benchmarked"` and report the standings for the metrics
   that have a range; still list any null ones in `data_gaps[]`.
3. Compare rate figures to the structured rate rows in the benchmarks file (the two rate rows with
   low/high/unit). Flag a rate presented as the creator's personal rate without that labeling.
4. Structural review, always available regardless of benchmark coverage: required sections
   present (audience, formats, rates, contact), personal-vs-industry rate labeling, an FTC
   disclosure note where sponsored work is described, and whether each market claim is sourced.
5. Assemble strengths, issues (each with a fix), and, only in benchmarked mode, the market
   position. Never assert "above average" or "competitive" from a null range.

## Output contract
```json
{
  "critique_mode": "benchmarked | structural_only",
  "metric_standings": [{ "metric": "", "alex_value": 0, "benchmark_range": "or null", "gap_assessment": "above | below | within | unknown" }],
  "rate_review": [{ "figure": "", "against_benchmark": "", "labeling_ok": true }],
  "structural_findings": [{ "area": "", "status": "ok | issue", "detail": "", "fix": "" }],
  "strengths": [],
  "issues": [{ "issue": "", "fix": "" }],
  "market_position": "one paragraph, benchmarked mode only; null in structural_only",
  "data_gaps": ["each unsourced benchmark that a market claim would have needed"],
  "human_review_required": true
}
```

## Standalone usability
The critique reads as a standalone review the creator can act on: what is strong, what to fix, and
where the market comparison is limited by missing benchmark sourcing.

## Failure modes
- All benchmark rows null (today's state): `critique_mode` is `structural_only`, market claims are
  withheld, `data_gaps` names each unsourced metric; the structural review still ships.
- A metric the kit claims that the file does not cover: `gap_assessment` unknown, listed in
  `data_gaps`; never borrowed from an adjacent niche.
- A rate presented as personal without labeling: flagged in `rate_review` with the fix, never
  silently accepted.
