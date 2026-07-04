# Realistic Scenario Suite

Five realistic, messy creator requests, pinned as a re-runnable test contract. The suite exercises
what Creator OS can do TODAY for each request and pins what it cannot (the gap ledger below). It is
the follow-up to the obligations handoff simulation: same self-testing discipline, applied to the
kind of vague, cross-lane questions a creator actually asks.

```bash
python3 tools/scenario_check.py              # run the whole suite (exit 0 = contract holds)
python3 tools/scenario_check.py --list       # list scenarios and gaps
python3 tools/scenario_check.py --json       # machine-readable report
python3 tools/scenario_check.py --selftest   # the runner's own micro-tests
```

The full offline battery is this suite plus `python3 tools/handoff_sim.py` (the 38-check
online-to-offline handoff simulation, sandboxed), `python3 tools/obligations.py --selftest`, and
`python3 tools/sync_check.py`.

The contract lives in `skills/creator-core/evals/scenarios.json` with fictional fixtures in
`skills/creator-core/evals/fixtures/`. The clock is pinned (`pinned_today: 2026-09-15`) so urgency
bands and dates are exact; `--today` or `--year` overrides demote date-exact assertions to
structural ones.

## Findings as a contract

The run fails loudly in BOTH directions:

- A deterministic leg breaking (date math, transcript parsing, chapter fan-out, quality-gate
  arithmetic) fails the suite the normal way.
- A declared-ABSENT routing classification appearing in the hub table, or a gap probe no longer
  observing its gap, ALSO fails the suite. Closing a gap is good news, but it must be closed
  deliberately: update `scenarios.json` and this ledger in the same change.

## The five scenarios

| ID | Utterance | Routing verdict | What runs deterministically today |
|---|---|---|---|
| S1 | "what's the email for that guy from my Hearthline account?" | gap: no `account_read` / `crm_query` / `contact_lookup` classification | The account record shape: the email is reachable at `primary_contact.email`, and the committed schema has no `secondary_contacts` or `alias` field ("that guy" has nowhere to resolve) |
| S2 | "where are we with that lightbulb company contract?" | partial: `contract_obligations` covers the timeline half; no `account_read` / `deal_status`, no category resolver for "lightbulb" | The full obligations lane on a fictional lighting brand: register build, weekend roll-back, net-30 anchor derivation, urgency bands, action-queue ordering |
| S3 | "what's the market going to look like for the holiday season and what should I start doing to prepare?" | present: `seasonal_planning` routes to `seasonal-trends` | All 16 seasonal publish-by deadlines through the obligations date math (band counts, roll-backs, prep queue ordered by urgency), plus the canonical machine-readable source itself: `canonical-sources/seasonal-aesthetic/seasonal.json` seasonal-windows entry with 8 windows of resolved ISO dates (P32) |
| S4 | "here's my media kit, do market research and give me critiques" | ambiguous: `media_kit` (generation only) vs `quality_check`; no `content_critique` | The deterministic Quality Gates verdict arithmetic (releasable and integrity hard-fail cases) plus the structured benchmark rows: 2 rate rows with low/high/unit and 6 sourced-or-null metric rows (P30) |
| S5 | "here's raw footage, break it down: chapters and what to cut" | present: `footage_breakdown` routes to `video-development` (P28; footage-analysis atom) | Transcript parsing (20 segments, exact duration), product silence detection via `shared/docintel/transcripts.gap_metrics` (three 8-to-20 second gaps), chapter fan-out and YouTube-rule validation on an authored chapter list |

## Gap ledger (the later-phase backlog)

Each gap has a repo-state probe in `scenarios.json`; the suite asserts all of them are still
observable. When one of these is built or fixed, the probe fires and the suite fails until this
ledger and the contract are updated together.

| ID | Gap | Blocks |
|---|---|---|
| G1 | No contact-retrieval capability: account-manager actions are health_check, renewal_scan, overview only; no MCP tool reads contacts | S1 |
| G2 | No fuzzy/nickname/category account resolver: account-health needs an exact `brand_name`; no alias field in any schema | S1, S2 |
| G3 | No routing classification for CRM read/status queries (`account_read` / `deal_status`) | S1, S2 |
| G4 | Schema drift: `pipeline/accounts/account-schema.json` (free-string `product_category`, single contact) vs `shared/pipeline-engine.md` (`brand_category` enum including lighting, `secondary_contacts`, `relationship_health`) | S2 |
| G7 | No media-kit critique path: `media_kit` routes to a generation-only spoke; `quality_check` scores internal gates, not market position; no `content_critique` classification | S4 |

### Closed gaps

| ID | Gap | Closed by |
|---|---|---|
| G5 | Broken load ref: `skills/atoms/seasonal-map/SKILL.md` listed `canonical-sources/seasonal-aesthetic.md`, which did not exist | P32: the canonical file now exists (aesthetic profiles plus the reconciled eight-window timing table); drift invariant 22 validates frontmatter load refs and `canonical-sources` joined KNOWN_ROOTS, closing the scan hole |
| G6 | Seasonal publish-by deadlines were prose-only with 3 non-reconciled copies; no machine-readable ISO source | P32: `seasonal.json` gained the seasonal-windows entry (8 windows, resolved ISO dates for reference_year 2026, annual recurrence stated); engine table, seasonal-map table, and JSON reconciled |
| G8 | Benchmark coverage: `benchmarks.json` had 2 prose-only rate rows and zero of benchmark-compare's 6 metric rows | P30: rate rows gained structured low/high/unit/currency parsed from their own prose; the 6 metric rows (ctr, avd, engagement_rate, views, subscribers, rpm) now exist with the low/high/unit schema, values sourced-or-null (null until verified against a registered rate-benchmark source, never estimated) |
| G9 | No transcript-to-chapters/cuts capability: nothing proposed chapters or cut points from transcript timecodes; no pause/WPM/filler analysis anywhere | P28: `shared/docintel/transcripts.py` gained `gap_metrics()` (inter-segment silences) and `suggest_chapters()` (silence plus words_per_minute boundary proposal); the runner's S5 leg now asserts the product function, not runner-owned evidence |
| G10 | No dedicated routing for raw-footage breakdown | P28: `footage_breakdown` classification routes to `video-development`; the `footage-analysis` atom is the realizer |

## What the suite deliberately does not do

It does not simulate the LLM judgment legs (writing the critique, choosing the chapters, answering
"where are we" in prose). Those are the model's job and are governed by the Quality Gates. The suite
pins the deterministic substrate those judgments stand on, and the exact list of capabilities that
are still missing underneath the five requests.

All fixture brands, people, and addresses are fictional. Nothing in the suite reads or writes real
CRM data, and the runner writes nothing at all.
