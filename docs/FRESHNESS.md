# Always-Fresh Data Inputs (P36)

How Creator OS keeps its reference data accurate for every user, on every surface, without ever
touching GitHub on a user's behalf. This is the runbook for the P36 freshness system. The token-free
maintenance mechanics (registry, dependency drift) are in `docs/CURRENCY.md`; this doc adds the
personal-freshness model, the overlay, the per-modality stores, and the source poll list.

## The three hard rules
1. **The freshness system never touches GitHub and never generates "homework" for anyone.** No commit,
   push, pull, PR, review request, or "an update is available" nag — not from a tool, an agent, the
   wizard, or CI. No user, entity, or AI ever proposes a GitHub change to the owner.
2. **Every deployment's freshness is self-contained in a store that user controls.** Refresh runs on
   the user's machine/platform/tokens; refreshed data lives only in that user's own store, consumed
   only by that user.
3. **The repo is a download-only, decoupled baseline.** The owner updates it if and when *they* choose,
   through their own work. Any user may download those updates at their discretion. The system never
   prompts a pull.

## The overlay model
`canonical-sources/**` (the registry + data) is a **read-only baseline** you downloaded. Your
freshness state — last-checked dates, content hashes, change flags, and any refreshed values — is
written to an **overlay in your own store**. The tools **union-merge baseline + overlay at read time**
(`tools/freshness_overlay.py`), so:
- the repo files are never modified by the runtime,
- your fresh data is yours alone, and
- if you later download a newer baseline, your overlay re-merges cleanly (append-only event log,
  deterministic fold, no last-writer-wins clobber).

Every refreshed **value** carries an `{as_of, source_citation, publish_date}` envelope, so a stale
value is aged and flagged, never silently trusted (no-fabrication).

## Two ways to stay fresh (you pick; they never cross)
1. **Refresh into your own store** — the token-free detector (always) and an optional in-platform
   agent (on your tokens) update your overlay. Fully local.
2. **Download a newer baseline** — when you want the shared improvements the owner has published, you
   `git pull` / download. Your own choice, never prompted.

## Per-modality store (set by the wizard: `/freshness-setup`)
| Modality | Store | How it writes |
|---|---|---|
| Claude Desktop (any model) | `local_fs` via filesystem MCP | writes JSON in place (best fidelity) |
| Cross-platform / multi-model | Google Drive + Docs/Sheets | append-new-dated-file; union-merge on read |
| Gemini-first | Google Drive/Docs/Sheets (native) | Gemini appends rows/sections, auto-saves |
| ChatGPT (Enterprise/Dev-mode only; conditional, verify your plan) | connected Google Drive via MCP | server-stamped `as_of`, write-confirm gate |
| ChatGPT plain web / Projects / Custom GPT / claude.ai web / Gem | export-and-you-save into Drive | agent emits a dated file; you file it (read-back steps: `docs/TRANSITIONS.md`) |

Knowledge-only surfaces (Projects, GPT, Gemini) that can't run the tools stay fresh two ways: the
**live path** (the surface reads your Drive overlay via its native connector) and the **static path**
(the downloadable baseline carries a visible `_Data freshness: as of …_` stamp from
`tools/build_freshness_bundle.py`).

## Running it
```bash
# read-only: your merged freshness view
python3 tools/source_currency.py report   --overlay "$HOME/CreatorOS/freshness.overlay.json"
# token-free change detection; stamps go to YOUR overlay only (never the registry, never GitHub)
python3 tools/source_currency.py check --detect-changes --apply --overlay "$HOME/CreatorOS/freshness.overlay.json"
# your personal dashboard (a local view; nothing is sent)
python3 tools/source_currency.py dashboard --overlay "$HOME/CreatorOS/freshness.overlay.json" --out "$HOME/CreatorOS/dashboard.md"
# dependency drift (token-free PyPI + GitHub Releases)
python3 tools/dependency_currency.py report
# owner dev-time: date the downloadable baseline
python3 tools/build_freshness_bundle.py --apply   # --check verifies it still matches canonical
```
Schedule it locally with `tools/freshness-scheduler.example` (cron/launchd). There is no scheduled
GitHub job. In Claude Desktop, the MCP tools `currency_scan`, `currency_detect_changes`, and
`freshness_refresh` do the same, writing only to your overlay.

## Detection primitives (token-free, stdlib)
- **Conditional GET + sha256** (ETag / If-Modified-Since; 304 = fresh, zero bytes).
- **CSS-selector-scoped hashing** (`content_selector` per source) so nav/ads/timestamps outside the
  watched region don't create false "changed" events.
- **Feed-first**: prefer a source's RSS/Atom/sitemap `lastmod` over its HTML page.
- **RFC 9111 `max-age`**: the origin's own policy can lengthen (never shorten) your re-check cadence.
- **Two-tier SLA**: `warn_after` (stale) and `error_after` (badly overdue) in your report.
- **Link-rot**: on 404/moved, the Wayback Availability API proposes the archived/again-live URL into
  your overlay for you to accept — in your own store.

## What is watched
- The `canonical-sources/**` data files (`data-currency-map.json` `files`).
- The **prose/config that embeds the same facts** (`data-currency-map.json` `embedded_fact_files`):
  the connector registry, integrations/contract/construction/compute/tasks/platform engines,
  `creator-os-config.json`, the wizard, and the video-tooling evidence JSONs. Drift invariant 25 ties
  every embedded fact to its upstream source.
- **New P36 monitors** (seeded into the registry): connector API changelogs (`api-changelog`),
  AI-surface/packaging formats (`ai-surface-spec`), creator content data, and compliance sources.

## Source poll list (best token-free signal per source)
- **Cleanest machine-readable feeds:** eCFR Versioner API (`.../full/current/title-16.xml?part=255`
  and `?part=465`, sha256), Google Search Central `feed.xml`, Google Search Status Dashboard RSS/JSON,
  FTC press-release RSS, Federal Register API, US Copyright Office RSS.
- **Git spec repos (watch `releases.atom` / commit feeds):** MCP protocol, `.mcpb` manifest, Anthropic
  Skills, Pinterest `api-description`, Microsoft `msgraph-metadata`, EasyPost client libs.
- **ETag + sha256 HTML/text holdouts:** Meta Graph & TikTok changelogs, SKILL.md spec, GPT Actions
  limits, Gemini plain-text changelog, Sprout/Hootsuite spec pages, rate reports, Ship24 OpenAPI YAML.

## Governance / licensing
- **Public domain (cache freely with provenance):** eCFR, Federal Register, FTC, US Copyright Office,
  DOE, state statutes.
- **Copyrighted — cache the fact/date only, never the text:** ICC/NFPA model codes, and gated reports
  (HypeAuditor/Aspire). Store the adopted-edition date or the benchmark number with its source URL and
  publish date; never mirror the page/PDF/tables.
- **No-fabrication:** every cached value keeps `publish_date` + `source_citation`; stale or
  unverifiable values are null-and-flagged, not trusted.
- **Known moving dates to watch:** FL 9th-Edition Building Code (2026-12-31), CA AI Transparency Act
  (2026-08-02), NY synthetic-performer disclosure (2026-06-09), NC 2024 code (~2027). Note: FTC
  Part 255 is unchanged since 2023-07-26 — the 2024 rule is the separate Part 465.

## Secrets / privacy
API keys (carrier aggregators, etc.) are read from the environment only, never persisted or logged.
Your overlay holds the same gitignored-class data as the rest of your local context; it is never
uploaded anywhere.
