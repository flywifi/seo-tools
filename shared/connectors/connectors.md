---
file: shared/connectors/connectors.md
role: Connector model for Creator OS. Defines which platform APIs and local tools provide which
  evidence types, how atoms degrade when a connector is off, and which deployment modes support
  which connectors. Load alongside shared/integrations-engine.md when an atom or spoke needs to
  know what data sources are active.
load: when resolving what data is available for the current deployment (analytics atoms,
  integrations-engine calls, MCP capability checks)
---

# Connectors

Creator OS atoms consume **evidence types**, not connectors. This model lets a skill use whatever
the deployment has connected, degrade to what it has permission for, and converge on an answer via
alternate sources — with unused connectors flagged off so nothing is probed unnecessarily.

This is a contract, not a set of live API clients. We build no provider auth/API code here. Live
retrieval is realized by the host AI's native integration (Claude / OpenAI / Gemini) when the
deployment has connected it, or via `manual_paste` / `uploaded_file` through `shared/docintel/`.

Files: `connectors.json` (registry), `connectors.py` (offline resolver), `feature-flags.example.json`
(sample per-deployment flags). API credential patterns: `shared/integrations-engine.md`.

---

## Connectors shipped

**Always available (offline fallbacks):**
- `manual_paste` — creator pastes any data directly into the conversation
- `uploaded_file` — creator uploads .pdf/.docx/.csv; read via docintel-engine
- `local_json_files` — reads `pipeline/user-context/*.local.json` (gitignored, Option A only)
- `web_intel_crawl` — polite web crawl via acquire.py when requirements-crawl.txt is installed

**Platform APIs (default: `not_installed`):**
- `youtube_data_api` — YouTube Data API v3; analytics, keywords, channel stats, competitor search
- `instagram_graph_api` — Meta Graph API v25.0; Reels insights, Business Discovery competitor data
- `tiktok_api` — TikTok APIs (Content Posting, Research, Display); analytics, trend data
- `pinterest_api` — Pinterest API v5; pin analytics, trend data
- `google_drive` — Google Drive files; document source (PDFs, docs, images)

**Local tools (availability depends on installation):**
- `sqlite_cache` — offline FTS5 keyword cache + competitor snapshot SQLite (keyword_data, competitor_data)
- `mcp_server` — stdio MCP server for Claude Desktop; exposes all MCP-gated capabilities
- `playwright_render` — Playwright Chromium for JS-rendered competitor snapshots (ytInitialData)

---

## Evidence types

Each connector declares which evidence types it provides. Atoms request evidence types; the
resolver returns the provider chain (primary connector → fallback → gap).

| Evidence type | What it covers |
|---|---|
| `analytics` | Platform performance (views, CTR, retention, engagement rates, impressions) |
| `keyword_data` | SEO keywords, search volumes, autocomplete results, FTS5 cache snippets |
| `competitor_data` | Competitor video tags (ytInitialData), hashtags, chapter markers, OG metadata |
| `trend_data` | Trending sounds, hashtags, seasonal search patterns, Google Trends signals |
| `document_source` | Uploaded PDFs, docs, spreadsheets for document-studio workflow |
| `voice_profile` | Creator's real phrases and patterns (voice-profile.local.json or uploaded) |
| `channel_stats` | Subscriber count, avg views, platform-specific channel metrics |
| `rate_benchmarks` | Brand deal rates, CPM data (from uploaded benchmarks or local.json) |
| `content_calendar` | Upcoming content schedule (content-calendar.local.json or pasted) |

---

## Canonical states

`available · disabled · not_installed · permission_blocked · metadata_only · unsupported · unknown`

- A **non-`available`** connector is never presented as an active retrieval path.
- `metadata_only` is never treated as content-ingested truth (a connector may be connected but
  restricted to metadata headers only — still not the same as having the content).
- `not_installed` means the dependency is not present on this machine (pip package, API key, etc.).
- `permission_blocked` means the dependency is installed but credentials are absent or revoked.
- Any degraded/partial path **lowers confidence** and is recorded — never hidden in prose.

---

## Restricted-but-active connectors

A connector can be `available` yet restricted for specific evidence types:

```json
{
  "youtube_data_api": {
    "state": "available",
    "restricted_evidence": ["competitor_data"],
    "reason": "YouTube Data API v3 does not return video tags for non-owner videos; use competitor_snapshot for tag extraction"
  }
}
```

Treat restricted evidence as blocked for that connector: drop to the next available provider,
record the reason, and lower confidence — "take what you can get, then look elsewhere."

---

## Degradation and convergence policy

Evidence priority, strong to weak:
`explicit user input > youtube_data_api > instagram_graph_api > tiktok_api > sqlite_cache >
web_intel_crawl > manual_paste > uploaded_file`

- If the top source for a signal is off or blocked, drop to the next available source for the
  same signal, record it in the execution trace, and lower confidence.
- **Converge**: corroborate several weak available sources before asserting. A single weak
  source means low confidence.
- **Skip** connectors that are flagged off — do not probe them.
- `youtube_data_api` is **authoritative for `channel_stats`** when available; always used first
  for that evidence type.

---

## Deployment mode matrix

| Connector | Option A (Desktop+MCP) | Option B (Projects) | Option C (GPT API) | Option D (ChatGPT Web) | Option E (Gemini) |
|---|---|---|---|---|---|
| manual_paste | available | available | available | available | available |
| uploaded_file | available | available | available | available | available |
| local_json_files | available | unsupported | unsupported | unsupported | unsupported |
| web_intel_crawl | available | unsupported | unsupported | unsupported | unsupported |
| youtube_data_api | setup required | unsupported | setup required | unsupported | unsupported |
| instagram_graph_api | setup required | unsupported | setup required | unsupported | unsupported |
| tiktok_api | setup required | unsupported | setup required | unsupported | unsupported |
| pinterest_api | setup required | unsupported | setup required | unsupported | unsupported |
| google_drive | setup required | available (native) | setup required | unsupported | available (native) |
| sqlite_cache | setup required | unsupported | unsupported | unsupported | unsupported |
| mcp_server | setup required | unsupported | unsupported | unsupported | unsupported |
| playwright_render | setup required | unsupported | unsupported | unsupported | unsupported |

---

## Override policy

- Set `allowed_sources` to narrow the active connectors to a specific list.
- Set `blocked_sources` to exclude specific connectors regardless of their state.
- An override is a control-plane reset: do not keep a blocked connector open because it was
  already open. Preserve recorded provenance and blocked-path notes.

---

## Use the resolver

```bash
# List registry and default states
python3 shared/connectors/connectors.py --list

# Show provider chain for current deployment (using local config)
python3 shared/connectors/connectors.py --flags creator-os-config.local.json --plan

# Use example flags
python3 shared/connectors/connectors.py --flags shared/connectors/feature-flags.example.json --plan
```

`--plan` prints each connector's effective state, the active connectors, the per-evidence-type
provider chain (primary to fallbacks), any evidence-type gaps (no active provider), and any
restrictions (active connector limited for an evidence type with the fallback it dropped to).

The `get_connectors` MCP tool calls this resolver and returns the JSON plan to Claude Desktop.

---

## Capability flag mapping

The simple boolean flags in `creator-os-config.json` (and `.local.json`) map to connector states:

| Capability flag | Maps to connector | State when true |
|---|---|---|
| `youtube_api` | `youtube_data_api` | available |
| `instagram_api` | `instagram_graph_api` | available |
| `tiktok_api` | `tiktok_api` | available |
| `keyword_cache` | `sqlite_cache` | available |
| `playwright` | `playwright_render` | available |
| `mcp_server` | `mcp_server` | available |
| `voice_profile` | `local_json_files` (voice evidence) | available |
| `channel_context` | `local_json_files` (channel_stats evidence) | available |

The resolver reads `creator-os-config.local.json` and maps these flags into connector states
when no explicit connector-level config is present.

---

## Privacy boundary

Connecting platform APIs can expose real analytics and account data. Extract only what the
atom needs (minimum necessary), never persist real credentials or PII to git, and follow
`protocols/safety.md` for FTC disclosure rules when using platform-connected data in content.
