# Realistic Scenario Suite

Ten realistic, messy creator requests, pinned as a re-runnable test contract. The suite exercises
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

## The ten scenarios

| ID | Utterance | Routing verdict | What runs deterministically today |
|---|---|---|---|
| S1 | "what's the email for that guy from my Hearthline account?" | present: `account_read` routes to `account-manager` (`crm_query` / `contact_lookup` deliberately subsumed) | The resolver plus the contact read: "hearthline" resolves to one account, "hearth" surfaces both prefix-sharing brands without auto-picking, `contact-lookup` returns Marcus Webb's verbatim email, and an unmatched person hint returns a gap naming the known contacts rather than the wrong person (P32) |
| S2 | "where are we with that lightbulb company contract?" | present: `contract_obligations` (timeline), `account_read`, and `deal_status` all route | The obligations lane on a fictional lighting brand (register build, weekend roll-back, net-30 anchor derivation, urgency bands, action-queue ordering), the category resolver ("that lightbulb company" surfaces the lighting brand as a candidate, never auto-resolved), and `deal-status` reporting the deal stage verbatim (P32) |
| S3 | "what's the market going to look like for the holiday season and what should I start doing to prepare?" | present: `seasonal_planning` routes to `seasonal-trends` | All 16 seasonal publish-by deadlines through the obligations date math (band counts, roll-backs, prep queue ordered by urgency), plus the canonical machine-readable source itself: `canonical-sources/seasonal-aesthetic/seasonal.json` seasonal-windows entry with 8 windows of resolved ISO dates (P32) |
| S4 | "here's my media kit, do market research and give me critiques" | present: `content_critique` routes to `partnership-mediakit` (alongside `media_kit` generation and `quality_check` internal gates) | The Quality Gates verdict arithmetic (releasable and integrity hard-fail cases), the structured benchmark rows (2 rate rows with low/high/unit, 6 sourced-or-null metric rows), and the documented honest degradation: with the metric rows null, `mediakit-critique` runs in `structural_only` mode and withholds market-position claims (P32) |
| S5 | "here's raw footage, break it down: chapters and what to cut" | present: `footage_breakdown` routes to `video-development` (P28; footage-analysis atom) | Transcript parsing (20 segments, exact duration), product silence detection via `shared/docintel/transcripts.gap_metrics` (three 8-to-20 second gaps), chapter fan-out and YouTube-rule validation on an authored chapter list |
| S6 | "what am I waiting on from Northwind, and did my final cut cover the approved talking points?" | present: `task_status` and `coverage_check` both route to `task-desk` (P35) | The task tracker end to end on a fictional brand: `tools/tasks.scan` splits waiting-on (aging brand review) from I-owe (overdue brief plus a due-soon script); a full two-party approval loop through `advance_ping_pong` (creator submit, brand request-changes, creator resubmit, brand approve) lands `done` with the responsible-party flip and iteration count, and the approval fires an acceptance-required milestone into a citation-carrying (`event_derived`) billable finance proposal; a manual delivered shipment yields the immutable `delivered_at` planning anchor; and `coverage_verify` reconciles two divergent transcripts (one credible conflict, surfaced as a minority report) then verifies the required points with an extractive citation per satisfied point, abstaining on the absent return-policy point rather than inferring |
| S7 | "CoolBreeze emailed asking for a long-form video plus a TikTok about their portable AC" | present: `pitch_triage` routes to `partnership-mediakit` (P40) | The inbound-pitch lane: `pitch-extract` structures the ask, `product-fit` scores brand-audience alignment, and pricing floors come from the rate card with the tier gap and package math surfaced, never invented |
| S8 | "draft the CoolBreeze agreement from my vetted template, paid usage this time, no exclusivity" | present: `contract_draft` routes to `contract-desk` (P42) | Document-template assembly: `doctemplates.validate_template` accepts only a vetted starter, `assemble` resolves selections (swap the usage block, exclude exclusivity) structurally, and both fabricated variants are rejected; real wording lives only in gitignored `.local` files |
| S9 | "import my past YouTube and Instagram videos and show me which parts were most watched" | present: `import_past_videos` and `most_watched_parts` route to `content-library` (P45) | The content-import lane end to end on fictional fixtures (in-memory store): `import_parse.parse_youtube_studio_csv` carries revenue (the only revenue source), a synthetic YouTube retention curve derives most-watched peaks, `parse_instagram_dyi` builds an IG record with retention null-flagged and no revenue, and `video_library.analyze` surfaces the shared tag and lists the IG record under `retention_unavailable`, never estimating what a platform does not expose |
| S10 | "I dropped a bunch of files in my Drive inbox, divvy them up" | absent (pinned): `inbox_scan` / `inbox_routing` have no hub row on purpose; `inbox-routing` is a standalone atom that triggers on its own description (the `profile-import` precedent), so a future routing row must update the contract deliberately | The drop-folder lane (P60): the committed rules table (`shared/docintel/inbox_rules.json`) maps transcript and video categories to their handlers by format while contracts stay content-gated; the REAL offline scan (`tools/handoff/inbox.py`) on a temp hub routes an `.srt` to `transcript-import`, holds a `.pdf` for a Claude session with `classified_as` null (never guessed), and flags an unclassifiable file in place; and the atom's proposal contract keeps a QUARANTINE verdict listed verbatim and never routed, with `human_review_required` always true |

## Gap ledger (the later-phase backlog)

Each gap has a repo-state probe in `scenarios.json`; the suite asserts all of them are still
observable. When one of these is built or fixed, the probe fires and the suite fails until this
ledger and the contract are updated together.

The ledger is currently EMPTY: every gap the P24 suite raised (G1 to G10) has been closed
deliberately, each with the probe flip, a `_closed_gaps` entry, and a strengthened product leg.
New gaps are added here when a future scenario surfaces one.

### Closed gaps

| ID | Gap | Closed by |
|---|---|---|
| G7 | No media-kit critique path: `media_kit` routes to a generation-only spoke; `quality_check` scores internal gates, not market position; no `content_critique` classification | P32: the `mediakit-critique` atom and the partnership-mediakit `content_critique` action critique a kit against the market (benchmark-compare per metric plus a structural review), degrading to `structural_only` when the benchmark rows are unsourced; quality-review stays the internal-gates lens |
| G3 | No routing classification for CRM read/status queries (`account_read` / `deal_status`) | P32: the hub table gained `account_read` (account-manager) and `deal_status` (deal-pipeline), both read-only; S1 keeps `crm_query` / `contact_lookup` pinned absent on purpose (account_read subsumes them; contact_lookup is a spoke action, not a route) |
| G1 | No contact-retrieval capability: no atom, action, or MCP tool read contacts | P32: the `contact-lookup` atom and account-manager `contact_lookup` action resolve the brand then read the contact rows via `tools/accounts.contacts()`; the `contact_lookup` MCP tool exposes the same read; an unmatched person hint gaps rather than guessing, and contact PII is masked when it leaves the machine |
| G2 | No fuzzy/nickname/category account resolver: account-health needed an exact `brand_name`; no alias field | P32: `tools/accounts.py` resolve() does tiered matching (exact, alias, substring, difflib fuzzy, brand-category term map) over the new `aliases[]` field; the `account-resolve` atom wraps it and account-health delegates fuzzy resolution to it; never auto-picks past a confident exact or alias match <!-- verify: tools/accounts.py::resolve --> |
| G4 | Schema drift: `pipeline/accounts/account-schema.json` (free-string `product_category`, single contact) vs `shared/pipeline-engine.md` | P32: schema v0.2.0 reconciled to the engine (`brand_category` enum including lighting, `secondary_contacts`, `relationship_health`, `channel_preferences`, `deal_history_summary`, `renewal_candidate`); `product_category` kept deprecated |
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
