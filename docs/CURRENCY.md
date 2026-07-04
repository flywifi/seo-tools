# Source and Dependency Currency

How Creator OS keeps its reference data, canonical sources, and dependencies current, and how to
run the mundane parts token-free (as deterministic Python, without spending model tokens).

## Two lanes

| Lane | What it watches | Tool | Token-free? |
|---|---|---|---|
| **Web content** | Registered source pages (SEO/platform/API-changelog/legal/rate/niche/cost) | `tools/source_currency.py` | change detection yes; interpretation no |
| **Dependencies** | pip packages, system binaries, MCP servers | `tools/dependency_currency.py` | fully |

Both read the one registry, `canonical-sources/source-registry.json`, written only through
`tools/registry_io.py` (imported by `source_currency.py`, `traversal_engine.py`, and
`dependency_currency.py`). `canonical-sources/data-currency-map.json` says, for every canonical
data file, whether it is **watched** by a source, **static** (no upstream by design), **dated**
(a calendar cadence, e.g. the seasonal windows), or **tool-managed**.

## The token-free flow

The mundane 90% question — "did anything actually change?" — is answered by plain Python:

```bash
# Dependencies: query PyPI + GitHub Releases, compare to the pinned/validated versions.
python3 tools/dependency_currency.py report            # read-only drift report
python3 tools/dependency_currency.py check --apply      # stamp last_checked/latest_seen (no model)

# Web content: conditional GET + sha256 per source; unchanged pages stamped, changed queued.
python3 tools/source_currency.py check --detect-changes           # read-only
python3 tools/source_currency.py check --detect-changes --apply    # stamp unchanged/first_seen (no model)

# What is stale / never checked (read-only):
python3 tools/source_currency.py report [--category <cat>]
```

Only entries that genuinely **changed** or **drifted** are escalated. For web content, the changed
queue names the `used_by` atoms/engines and the canonical data file to update; a person or the
model reads the diff and updates it (e.g. `youtube-algorithm-signals.json`). For dependencies, a
drift line names the tool/atom that breaks and why; a major-version bump is flagged breaking. No
model tokens are spent on the unchanged majority.

Offline or behind a restrictive proxy, both tools degrade to **advisory** (they print the pinned
baseline and the exact check URL) and exit 0 — they never fabricate a version or a change.

## How dependencies are checked accurately

- **pip package** -> PyPI JSON API (`pypi.org/pypi/<pkg>/json`): exact latest version + upload date.
- **GitHub-hosted tool / MCP server** -> GitHub Releases API (`api.github.com/repos/<o>/<r>/releases/latest`): tag + publish date. Uses `GITHUB_TOKEN` when present.
- **system binary / no feed** (ffmpeg, Resolve, Compressor, CommandPost, Apple FCPXML) -> advisory: the entry records the validated version, the pinned constraint, and the release URL to check by hand.

Baselines come from `requirements-*.txt` (the pin), `docs/video-tooling-integration-evidence.json`
(the validated version), and `shared/connectors/connectors.json` (the MCP servers).

## Adding a new source or dependency

Never hand-edit `source-registry.json`.

- **A web source**: add an entry (id, name, url, category, tier, extraction_hint, used_by) to a
  seed file shaped like `canonical-sources/legal-sources-seed.json`, then
  `python3 tools/source_currency.py seed-sources <file.json>`.
- **A dependency / MCP server**: add it to `canonical-sources/dependency-sources-seed.json` with
  `package` (pip) or `upstream_api`+`check_url`, `used_by` (the tool/atom it protects plus, for an
  MCP server, the `connectors.json` connector id it backs), and `_why` (the failure mode), then
  `seed-sources`. **Invariant 23** fails the drift guard if a `requirements-*.txt` package or an
  MCP-backed connector has no matching entry, so a new dependency cannot ship untracked.
- **A correction** (URL fix, recategorization): `python3 tools/source_currency.py update-source
  <id> --url ... --category ...`.
- **A graph-discovered source**: `python3 tools/traversal_engine.py traverse[-all]` then
  `accept <url>`.

## What updates what, and why

Every entry's `used_by` names the atoms/engines/connectors it protects; `_why` (dependencies) or
`extraction_hint` (content) states what a change means. When `mark-checked --changed` or a detected
content change fires, the `used_by` list is the review queue: those are the artifacts to refresh.

## Cadence

Per-category intervals live in `canonical-sources/traversal-config.json`
(`per_category_overrides`). Current defaults: SEO authority 7d, platform spec / API changelog /
tool-mcp 14d, niche authority 30d, mcp-server 30d, software-dependency 60d, rate-benchmark /
cost-vendor 90d, legal-authority 180d, competitor-page 3d. A per-entry `check_interval_days`
governs dependency freshness precisely (dependency_currency reads it directly).

## Weekly automation

The `currency-report` CI job (`.github/workflows/ci.yml`, weekly + `workflow_dispatch`) runs both
reports **read-only** and never writes the registry. Closing the loop (`mark-checked` / `--apply`)
is an explicit local or cron step so a human always sees drift before a pin is bumped.
