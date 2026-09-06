---
file: skills/atoms/mediakit-critique/MAINTAINER_README.md
purpose: preserve the non-negotiable operating rules for mediakit-critique so it stays stable under iteration.
---

# mediakit-critique: Maintainer README

## Purpose
Critique a media kit against the market: benchmark-compare per claimed metric, rate comparison
against the structured rate rows, and a structural review. It reads benchmarks sourced-or-null and
degrades honestly when they are null. It is the market lens; quality-review is the internal-gates
lens, and they do not overlap.

## Non-negotiable invariants
- Shared: references `shared/platform-engine.md` and `shared/brand-engine.md`; obeys
  `protocols/no-fabrication.md` (metrics from the kit, benchmarks from the file, never invented)
  and `protocols/research-citation.md` (market claims are sourced or withheld).
- Composes `benchmark-compare`; never re-implements the benchmark lookup.
- Honest degradation is mandatory: when every relevant benchmark range is null,
  `critique_mode` is `structural_only`, `market_position` is null, and each unsourced metric is in
  `data_gaps[]`. A market-position claim is NEVER made from a null range.
- Does not score the nine internal Quality Gates dimensions; that is `quality-review`.
- Does not generate media-kit copy; that is `mediakit-section` / `rate-card-fill` /
  `pitch-paragraph`.
- Flags any rate presented as the creator's personal rate without that labeling.

## Known failure modes
- All benchmark rows null (today): structural_only, market claims withheld, data_gaps populated.
- A claimed metric the file does not cover: gap_assessment unknown, listed in data_gaps.

## Fragile fallbacks that must not become defaults
- Emitting "above average" / "competitive" from a null benchmark range.
- Borrowing a benchmark from an adjacent niche to avoid a null.
- Drifting into internal-gate scoring (integrity, safety) that quality-review owns.

## Regression cases to preserve
1. All-null benchmarks produce structural_only with a populated data_gaps and null market_position.
2. A sourced benchmark produces a benchmarked-mode standing for that metric.
3. An unlabeled personal rate is flagged with a fix.
4. Structural review runs and ships regardless of benchmark coverage.
Mapped to evals/evals.json.

## Approval-gated changes
The degraded-mode rule (structural_only), the no-market-claim-from-null rule, the boundary against
quality-review's internal gates, and the output schema.

## Update checklist
1. Edit SKILL.md / this file.
2. `python3 tools/sync_check.py` exits 0; `python3 tools/scenario_check.py` stays green.
Verify all backticked path references in this file and SKILL.md resolve to real files on disk.
