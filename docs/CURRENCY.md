# Source and Dependency Currency

How Creator OS keeps its reference data, canonical sources, and dependencies current, and how to
run the mundane parts token-free (as deterministic Python, without spending model tokens).

> **P36:** for the per-user, self-contained freshness model (the overlay, per-modality stores, the
> "never touches GitHub / no homework" rules, and the full source poll list) see **`docs/FRESHNESS.md`**.
> This page covers the token-free maintenance mechanics those rules build on.

## Two lanes

| Lane | What it watches | Tool | Token-free? |
|---|---|---|---|
| **Web content** | Registered source pages (SEO/platform/API-changelog/legal/rate/niche/cost) | `tools/source_currency.py` | change detection yes; interpretation no |
| **Dependencies** | pip packages, system binaries, MCP servers | `tools/dependency_currency.py` | fully |

Both read the one registry, `canonical-sources/source-registry.json`, written only through
`tools/registry_io.py`. Five tools funnel through it: `source_currency.py`, `traversal_engine.py`,
`dependency_currency.py`, and `update_check.py` import it directly, and `competitor_snapshot.py`
writes through `source_currency`'s re-exported `save_registry`. `canonical-sources/data-currency-map.json` says, for every canonical <!-- verify: tools/registry_io.py::save_registry -->
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

Baselines live in the registry: `pinned_constraint` is transcribed from `requirements-*.txt` and
`validated_version` from the last validated run (`docs/video-tooling-integration-evidence.json`),
both via `source_currency update-source`. The checker reads only those two registry fields. Drift invariant 25
keeps `pinned_constraint` equal to the requirements specifier for every pip package the registry
names (mcp-server entries carry an install command, not a specifier, and packages absent from the
requirements files are outside the rule). `shared/connectors/connectors.json` is not an input to the
checker; it only names the connector ids an MCP entry protects.

### Re-validating the video environment (P80 checklist)

1. Regenerate the synthetic media from the recipe in `docs/video-tooling-spike-evidence.json` and run
   the four probes recorded in `docs/video-tooling-integration-evidence.json` against the goldens
   (first on the previously validated versions as a control, then on the candidates).
2. Append a `revalidations` entry to that evidence file (date, python, pip_versions, ffmpeg, control,
   live_checks with the exact `command` per check plus expected, observed, max_delta_seconds,
   tolerance_seconds, pass; the 2026-07-03 originals predate this schema and are not re-shaped).
   Never edit the original run.
3. `python3 tools/mac_surface_manifest.py reconcile` (the file is hash-pinned).
4. Stamp each validated library: `python3 tools/source_currency.py update-source dep-<x>
   --validated-version <resolved>`; the requirements pin and the registry pin must agree (drift
   invariant 25 fails the build otherwise).

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

## Doc-declared sources: the citation trigger (P55)

A maintainer/SKILL/doc file whose claims rest on external authorities declares them in a fenced
`sources` block (a JSON array; a registered id needs only `id` + `url`, a NEW source declares the full
seed shape `id`/`name`/`url`/`category`/`tier`), or ties one claim to one id with an inline
`<!-- source: an-example-id -->` marker. The declaration is both the generator input and the
enforcement target, mirroring how invariant 23 makes a `requirements-*.txt` line force a registry
entry:

1. **Declare** the source in the doc that cites it (see `docs/MACOS-MAINTENANCE.md` and
   `docs/SETUP_MAC.md` "Declared sources" for live examples).
2. **Generate**: `python3 tools/source_sync.py reconcile` scans the doc corpus, diffs the declarations
   against the registry, and writes a ready seed file (a `.local.` path, never committable) for any
   declared-but-unregistered id. It never writes the registry and never invents fields: an incomplete
   declaration is reported back to the doc author.
3. **Enforce**: drift-guard **invariant 52** (fail-closed, like invariant 23) fails the build when a
   declared id is missing from the registry, a declared URL disagrees with the registry's, or a
   `sources` block does not parse. The human closes the loop with
   `python3 tools/source_currency.py seed-sources <generated-file>` (the sanctioned writer set is
   unchanged). Illustrative ids used in documentation examples are exempted in
   `tools/doc-source-allowlist.json`, each with a written reason.

The outcome: citing a source in a maintainer note is no longer inert prose. The citation forces a
registry entry, and the registry entry puts the source on the freshness cadence below, so the fact the
doc rests on gets re-checked on schedule from then on. `python3 tools/source_sync.py check` is the
read-only report (also useful pre-commit).

## What updates what, and why

Every entry's `used_by` names the atoms/engines/connectors it protects; `_why` (dependencies) or
`extraction_hint` (content) states what a change means. When `mark-checked --changed` or a detected
content change fires, the `used_by` list is the review queue: those are the artifacts to refresh.

## Cadence

Per-category intervals live in `canonical-sources/traversal-config.json`
(`per_category_overrides`). Current defaults: SEO authority 7d, platform spec / API changelog /
tool-mcp 14d, niche authority 30d, mcp-server 30d, ai-surface-spec 30d, software-dependency 60d,
rate-benchmark / cost-vendor 90d, legal-authority 180d, competitor-page 3d. A category override wins
over a per-entry value at seed time; `os-platform` (P55, the macOS/OS facts) deliberately has no
override, so its per-entry `check_interval_days` values (60d to 90d for Homebrew formulae up to 365d for
PEP 668) apply as declared. Dependency entries are checked on every `dependency_currency` run
regardless of `check_interval_days`; the interval governs only the generic `source_currency` report
grouping.

## Weekly automation

The `currency-report` CI job was **retired in P36**: source/dependency freshness is now a fully
local, per-user runtime (see `docs/FRESHNESS.md`) with **zero GitHub coupling**, so no scheduled job
reads or reports on the registry. The only weekly CI job is `competitor-intel`. What CI does keep is
read-only and offline: the `guard` job runs `dependency_currency.py --selftest` and
`update_check.py --selftest` (P47-2), which exercise the detection logic without any network call or
registry write. Closing the loop (`mark-checked` / `--apply`) stays an explicit local or cron step so
a human always sees drift before a pin is bumped.

## Push integrity, versioning, and release (P47)

Detection and correction of currency/versioning/push drift, all diagnose-only (no auto-fixers):

- **`tools/preflight_push.py`** predicts every push blocker before you push, read-only: drift,
  version desync, an un-restamped freshness projection, and the commit-hygiene classes (a claude.ai
  session trailer or personal email in the pending commit range, staged secrets, tracked-content
  secrets). Advisory by default (always exit 0); `--strict` exits 1; `--json` for machines.
- **`tools/release.py`** readies (does not fire) the baseline GitHub release so the self-update poll
  (`tools/update_check.py`) stops reporting `no_release`. `--check` reports the release state,
  `--plan` prints the exact `git tag` + `gh release create` commands, and `--execute --yes` cuts it
  only where `gh` is authenticated. The `.github/workflows/release.yml` job does the same on manual
  `workflow_dispatch` (never on push), gated on a green drift guard and a consistent version.
- **New drift invariants (36 to 45).** 36 (catalog integrity, the keystone) keeps the invariant
  catalog a single source of truth. 37 to 38 are errors (legal-source category correctness;
  marketplace/plugin version equality). 39 to 45 are **advisory** (non-blocking notes that print but
  never change the exit code): versions.json tree coverage, registry used_by path resolution,
  capability to connector existence, registry writer-count integrity, the moving-date calendar,
  degraded_behavior parity, and content-vs-digest silent staleness.
- **Staged volatile backlog.** `canonical-sources/moving-dates.json` (moving legal dates as
  machine-checkable JSON, read by invariant 43), `canonical-sources/volatile-corrections.2026-07-14.json`
  (a prioritized, cited correction backlog with exact unexecuted apply commands, highest =
  `requirements-mcp.txt` capping `mcp` below the breaking 2.x on PyPI), and
  `canonical-sources/eu-ai-act-seed.json` (the one genuinely new source, staged not applied). Nothing
  here is applied by committing it; each entry names the human command that would apply it.

## Blocked is not gone (P49 WS9)

A fetch that an automated check receives as a 403/401/406/451, a 429/503 throttle, or a
Cloudflare/CAPTCHA/DataDome challenge (even one served at HTTP 200) is bot-detection or a rate-limit,
**not** evidence the source disappeared. `source_currency.py --detect-changes` runs
`tools/fetch_diag.py::classify_block` over every response and classifies such a result as **`blocked`**,
distinct from `unreachable`:

- A `blocked` source is **never** stamped stale, **never** flagged `changed` (a 200 challenge page is
  not hashed as content), and **never** made orphan-eligible. It keeps its last-known-good `content_sha256`
  and records a durable `last_block_detected` / `block_kind` / `block_vendor` on the entry.
- `compute_staleness` and the freshness SLA **skip** currently-blocked sources (they appear under a <!-- verify: tools/source_currency.py::compute_staleness -->
  `blocked` count, not `stale`/`error`); `traversal_engine prune-orphans` excludes them. A later
  successful check clears the block automatically.
- Only a genuine `404`/`410` (no anti-bot signature) is treated as `unreachable` (gone).
- A GitHub/PyPI **403 rate-limit** in `dependency_currency.py` / `update_check.py` is reported as
  `blocked` with a "set `GITHUB_TOKEN` and retry" hint, never conflated with "no upstream" / "no release".

**Resolving a block (all surfaces).** Each blocked source is surfaced in `needs_human_verification` with
a handoff that works everywhere: open the URL in a browser and paste the text (or upload a screenshot) —
the always-available `manual_paste` / `uploaded_file` connectors carry this on claude.ai web, ChatGPT
web, and Gemini as well as desktop — gated by `docs/PASTE-SAFETY.md`. Local-runtime users can instead run
`python3 tools/fetch_resilient.py <url>` (browser render + archive.org), or pass `--resilient` to
`--detect-changes` to attempt that retry automatically before recording a block (opt-in; may use network;
degrades silently if the optional deps are absent). See `shared/web-intel-engine.md` Levels 3 to 6.

**Structured fields (P79).** Two conventions that used to live only in prose are now registry fields
with sanctioned writers. `excerpt_confidence: true` plus `excerpt_verified_at` (set with
`update-source <id> --excerpt-confidence --excerpt-verified-at YYYY-MM-DD`) is the machine form of the
EXCERPT-CONFIDENCE hint prefix: the prose prefix stays as the human explanation, the fields are what
tooling reads. `content_selector` (set with `update-source <id> --content-selector 'main#main-content'`)
scopes change detection to one region of the page so per-request chrome cannot produce a false
`changed`; it falls back to the whole body when the selector matches nothing, so a redesign degrades to
noisier, never to blind. The three FTC HTML sources use it.

## If the registry is damaged (recovery)

`canonical-sources/source-registry.json` is written atomically by
`tools/registry_io.py::save_registry` (serialize in full, write a sibling temp file, then
`os.replace`), so an interrupted write leaves either the whole old file or the whole new one.
A reader never sees a half-written registry.

If the file is damaged anyway (a hand edit, a bad merge, a disk fault):

```bash
git checkout canonical-sources/source-registry.json
```

That restores the committed structure. What you lose is any local stamping done since the last
commit: `last_checked` / `latest_seen` dates written by `source_currency.py mark-checked` or
`dependency_currency.py check --apply`. Re-run those and they re-stamp. Nothing else in the
registry is local-only, so there is no unrecoverable state here.

If `git checkout` reports no changes but the drift guard still complains about
`_content_digest`, the file was edited in place and committed: run any sanctioned write verb (for
example `python3 tools/dependency_currency.py check --apply`) to re-stamp the digest through the
single write path. Do not edit the digest by hand.

## Interval banding (what a cadence promises, P74)

A `check_interval_days` value is a promise that the clock actually runs. Today it does not.
**66 sources declare a sub-monthly cadence and 64 of them have never been checked once**, because
P36 retired the weekly CI job and made stamping an explicit local or cron step that no committed
doc installs. Only two sub-30-day entries have ever been polled: `google-drive-desktop-sync-modes`
and `google-drive-desktop-macos`. A 7-day interval that has never fired is not diligence, it is a
number that makes the registry look better maintained than it is.

This is recorded as an open finding, not a fixed one. **The bands have not been re-banded**, because
what a source's cadence should be is a maintenance-policy decision for the maintainer, not a number
a tool should quietly rewrite to silence its own advisory. The two honest resolutions are:

- **Install the cadence.** `tools/freshness-scheduler.example` exists and nothing installs it. A
  real cron job that runs `dependency_currency.py check --apply` and `source_currency.py check`
  makes the declared intervals true, and no re-banding is needed.
- **Or re-band to what will actually run.** If the answer to "what polls this?" is "someone
  remembering", the honest value is 30 — the monthly currency pass is a real ritual. Note that
  `creator-os-release` legitimately keeps 7 days either way: `tools/update_check.py` polls it
  token-free and stamps it automatically through `apply_stamp`.

Whichever is chosen, do it through the sanctioned writer, never by hand:

```bash
python3 tools/source_currency.py update-source <id> --check-interval-days 30
```

Longer bands (60, 90, 120, 180, 365, for progressively more stable authorities) are unaffected by
this finding; they are met by the monthly pass.
