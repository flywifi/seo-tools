---
file: docs/ARCHITECTURE.md
role: Authoritative design reference for Creator OS. Describes the hub-and-spoke architecture,
  lane model, engine load rules, scoop cache, document intelligence, transcription, integrations,
  and the quality gate.
---

# Creator OS Architecture

## Overview

Creator OS is a hub-and-spoke ecosystem of Claude Agent Skills built for Alexandra Slason, a
YouTube creator in the moody-vintage home decor and DIY niche.

**Hub-and-spoke.** A single routing hub (`creator-core`) sits at the center. It classifies every
request, loads only the engines that request needs, enforces the governance protocols, and dispatches
to one or more capability spokes. Spokes do not talk to each other directly; all cross-spoke work
flows back through the hub or is sequenced by the user.

**Three lanes.** Every request is classified into one of three lanes: Content, Document, or
Pipeline/CRM. The lane determines which engines load, which spokes are eligible, and which protocols
fire.

**Offline-first.** Parsing, file classification, injection scanning, transcript normalization, WER
and CER validation, and cache lookups all run as local zero-token scripts. The model receives only
compact, structured extractions. Tokens are spent on reasoning, not on re-reading raw bytes.

**Atom-level actions.** Spokes are thin orchestrators. Each spoke composes single-operation atoms
via a `workflow.json`. Atoms can also be called directly for one-off tasks, making the system
modular and testable at the smallest unit of work.

---

## Repository layout

```
seo-tools/
  shared/           Flat canonical engines. Source of truth for all cross-cutting logic.
  protocols/        Five governance protocols. quality-gates.md is authoritative.
  pipeline/         CRM records store (accounts/, deals/). Real data is gitignored.
  skills/           Hub, governance skill, 14 spokes, and atoms/ sub-skills.
  canonical-sources/ Reference data the scoop cache indexes.
  tools/            Drift guard, scaffolder, versioner, packager, cache sync, template.
  implementation/   Platform packaging for Claude, GPT, and Gemini.
  docs/             Architecture, routing model, quality model, and deployment docs.
  ledger/           Audit log of artifact verdicts and pipeline events.
  examples/         Cross-skill example library.
```

### shared/

| File | Role |
|---|---|
| brand-engine.md | Identity, aesthetic, pillars, voice, config. Source of truth. |
| audience-engine.md | Personas, behavior signals, adaptation baselines. |
| platform-engine.md | Per-platform specs, algorithm signals, metric definitions. |
| adaptation-engine.md | Skill-level, tenure, budget, persona, surface adaptation. |
| pipeline-engine.md | Account and deal schemas, lifecycle stages, transition rules, radar. |
| web-intel-engine.md | Live research acquisition, freshness rules, citation protocols. |
| injection-guard-engine.md | Injection scan for all untrusted external content. |
| docintel-engine.md | Document intelligence pipeline (classify, parse, scan, route). |
| transcription-engine.md | Offline STT, caption formats, WER and CER validation. |
| integrations-engine.md | YouTube, Meta, TikTok, OneDrive, Google Drive integrations. |
| method.md | The unified pipeline every generating skill follows. |
| cache/ | Scoop tier (L1 keyword index, L2 semantic recall, L3 sync). |

### protocols/

| File | Role |
|---|---|
| quality-gates.md | Nine-dimension rubric, thresholds, and release gate. Authoritative. |
| no-fabrication.md | Never invent data, metrics, brands, deals, or sources. |
| safety.md | Trade, legal, and FTC disclosure boundaries. |
| research-citation.md | Research-first rule, freshness windows, citation format. |
| formatting-metadata.md | No em dashes, ranges with "to," document author metadata. |

---

## Hub

`skills/creator-core/` is the routing hub. It does not generate content; it classifies and
dispatches.

**Step sequence:**
1. Classify the request into one of 21 `request_classification` values.
2. Assign the primary lane (Content, Document, or Pipeline/CRM) and note any secondary lane.
3. Identify which engines are required for the target spoke.
4. Identify which protocols apply.
5. Determine adaptation axes (skill level, tenure, budget, persona, platform targets).
6. Identify the recommended spoke and any secondary spoke.
7. Flag open questions and any minority routing possibility.
8. Return a plain-language human summary and a fully populated JSON routing object.
9. Stop. Do not generate the final deliverable in the same turn unless the user explicitly
   requests it.

**Stop conditions.** The hub stops after emitting the routing object unless the user explicitly
asks for the spoke work in the same message, or the routing is unambiguous and proceeding saves
meaningful effort.

**External content.** Any file or attachment arriving with the request is processed by the
document intelligence pipeline (ingest-route atom) before the hub classifies the lane. Quarantined
or unreadable sources never reach routing.

**Source authority hierarchy.** When conflicting signals exist, the hub resolves by this ladder:
`pipeline/accounts/` and `pipeline/deals/` beat everything for CRM facts. `shared/brand-engine.md`
is canonical for identity and voice. `shared/platform-engine.md` is canonical for format specs.
User-provided analytics are operational truth for the current period. Research results are current
truth for trends and SEO. Ingest connectors are input signals only; they never overwrite pipeline
store records.

---

## Lanes and spokes

### Content lane

Requests to plan, script, research, repurpose, or analyze content.

| Spoke | Primary function |
|---|---|
| content-strategy | Idea clusters, pillar-aligned video concepts, competitive positioning |
| project-builder | Full production packages from a single concept |
| video-development | Script, hook, title, thumbnail, and chapter development |
| shortform-repurposing | Short-form clips and captions extracted from long-form content |
| seo-keywords | Keyword research, cluster strategy, and title SEO |
| analytics-insights | Analytics interpretation, trend reading, and performance review |
| audience-research | Persona mapping, audience question research, and signal gathering |
| competitor-analysis | Competitive positioning and gap identification |
| seasonal-trends | Seasonal topic and aesthetic planning |

### Document lane

Requests to create or edit a file: media kit, deliverable brief, invoice, PDF guide, content
calendar, or brand one-pager.

| Spoke | Primary function |
|---|---|
| document-studio | All file creation and document editing tasks |

### Pipeline/CRM lane

Requests touching a brand account or deal: create and read and update records, move a deal stage,
generate a production plan from a signed deal, compute the radar, check deadlines or payment status.

| Spoke | Primary function |
|---|---|
| account-manager | Brand account CRUD and radar views |
| deal-pipeline | Deal lifecycle: create, update, move stage, close |
| deal-resourcing | Production plan and materials from a signed deal |
| partnership-mediakit | Media kit and outreach generation for partnership requests |

### Cross-lane requests

A request can span two lanes (for example, a signed deal that immediately needs a production plan
and a deliverable brief). The hub routes the primary lane first and records the secondary lane in
the routing object.

### Governance skill

`quality-review` sits outside the three lanes. It evaluates any artifact produced by any spoke.
Spokes call it via the `govern-artifact` atom as the final step of every workflow.

---

## Atoms

Atoms are single-operation sub-skills that live in `skills/atoms/`. Each atom does exactly one
thing. Spokes compose atoms in sequence via `workflow.json` rather than embedding logic directly.

Atoms can be called directly for one-off tasks without going through a full spoke workflow.

**Installed atoms:**

| Atom | Operation |
|---|---|
| idea-generate | Generate a batch of content ideas |
| pillar-classify | Classify a request into a content pillar |
| trend-check | Verify trend or seasonal claim against live sources |
| keyword-cluster | Build a keyword cluster from a seed term |
| hook-write | Write hook variants for a video |
| title-generate | Generate SEO-optimized title candidates |
| thumbnail-concept | Produce thumbnail concept descriptions |
| short-extract | Extract a short-form clip from long-form content |
| script-section | Write a section of a video script |
| caption-write | Write social captions for a platform |
| hashtag-set | Generate a platform-specific hashtag set |
| pin-write | Write a Pinterest pin description |
| seasonal-map | Map a concept to a seasonal aesthetic |
| calendar-slot | Place content into a calendar window |
| persona-map | Map a request to a named audience persona |
| competitor-scan | Scan a competitor profile for gaps and signals |
| renter-alt | Generate a renter-friendly alternative for a project step |
| step-sequence | Write a numbered step sequence for a DIY project |
| materials-list | Produce a materials and tools list for a project |
| production-task | Generate a production task list from a deal |
| account-health | Compute account health signals from a pipeline record |
| mediakit-section | Write a section of a media kit |
| rate-card-fill | Fill rate card fields from a deal or benchmark data |
| pitch-paragraph | Write an outreach pitch paragraph |
| gap-record | Record a retrieval or parsing gap with structured metadata |
| govern-artifact | Run the Quality Gates and return a verdict |
| ingest-route | Classify, parse, and injection-scan a file or asset |

---

## Engines

Engines are markdown files in `shared/`. They are the source of truth for all cross-cutting
knowledge. Spokes reference them by repo-root path. There are no per-skill copies.

The hub loads only the engines a spoke actually needs. Engine load rules:

| Engine | Load condition |
|---|---|
| brand-engine.md | Every Content and Document request |
| audience-engine.md | Requests involving audience targeting, persona mapping, or analytics |
| platform-engine.md | Video, short-form, SEO, or analytics requests |
| adaptation-engine.md | Any content or project output |
| pipeline-engine.md | Every Pipeline/CRM request |
| web-intel-engine.md | Trend, SEO, competitor, seasonal, or platform-spec research |
| docintel-engine.md | Any request that carries a file or attachment |
| transcription-engine.md | Any request involving audio, video, or caption work |
| integrations-engine.md | Any request that fetches from a cloud or social API |
| injection-guard-engine.md | Always active as pre-routing middleware on external content |

---

## Scoop cache

The scoop tier is `shared/cache/`. It provides deterministic, offline, low-token retrieval over
the enumerated reference data in `canonical-sources/`. Instead of loading full reference files
into context, a spoke gets a handful of ranked snippets with provenance (source file and record
ID).

**canonical-sources/** holds the authoritative reference data the cache indexes:
keyword library, platform specs, personas, rate benchmarks, and seasonal aesthetic.

### Three layers

**L1 (shared/cache/cache.py):** Local-first keyword index. Pure stdlib `sqlite3` with FTS5 full-text
search. Zero token cost at query time. If the host SQLite lacks FTS5, a LIKE fallback is used and
reported honestly. Every result carries its source file for traceability.

```bash
python3 shared/cache/cache.py --build
python3 shared/cache/cache.py --query "moody fall" --limit 5
python3 shared/cache/cache.py --stats
python3 shared/cache/cache.py --verify
```

**L2 (shared/cache/semantic.py):** Optional offline semantic recall. Off by default. Activates
only when a local vector backend is installed and the user has granted consent. Falls back to L1
and says so. No data leaves the machine.

**L3 (tools/sync_cache.py):** Manifest-driven sync and portable distribution. Produces a
Scoop-style bucket manifest that is sha256 verified. Human-approved by default: `--sync` is a
dry-run; rebuilding the index requires `--apply`.

The scoop tier complements `shared/web-intel-engine.md` (live acquisition). Live retrieval
handles fresh external data. The scoop tier handles stable canonical reference data offline.

---

## Document intelligence

The document intelligence pipeline is defined in `shared/docintel-engine.md`. It runs as
pre-routing middleware: whenever a request carries a file or attachment, the pipeline processes it
before the hub classifies the lane.

**Design principles:** local-first zero-token compute; detect before parse; never overstate
extraction; scan all untrusted content; return honest gaps rather than guessing.

**Four-step ingestion chain:**

1. Classify: `shared/docintel/classify.py` reads magic bytes and file extension, returns file
   type, family, parseable-offline flag, and a trust hint.
2. Parse (offline, zero token): `shared/docintel/parse_text.py` handles text, data, and Office
   formats. `shared/docintel/transcripts.py` handles SRT, VTT, JSON, and plain transcripts.
   Unreadable or encrypted files return `metadata_only` and a `needs_more_info` flag.
3. Scan: all untrusted text passes through `shared/injection-guard-engine.md`. A QUARANTINE or
   BLOCK result stops ingestion; no content reaches routing.
4. Route: the ingest-route atom assembles the ingestion record and returns it to creator-core,
   which classifies the lane as usual.

**Four-state evidence ladder:** `referenced`, `metadata_only`, `content_ingested`,
`local_artifact_saved`. A scanned PDF that yielded no text is `metadata_only`, not
`content_ingested`.

**Files arrive from:** user upload (trusted), cloud storage via integrations-engine (untrusted
external), and pasted text or fetched URLs via web-intel-engine Level 5 (untrusted).

---

## Transcription engine

The transcription engine is defined in `shared/transcription-engine.md`. It handles batch
offline speech-to-text and caption creation. Live STT and real-time streaming are out of scope.

**Offline-first.** All STT work runs on local hardware. Model weights are downloaded once and
cached. No audio bytes or transcript text leave the machine. No API calls, no cloud endpoints,
no token consumption.

**Library priority for batch production:**
1. faster-whisper (recommended): CTranslate2 backend, int8 quantized, fastest on CPU and CUDA.
2. whisper.cpp: C/C++ backend, no Python dependency, suitable for shell-only environments.
3. openai-whisper: PyTorch reference implementation, used for debugging and validation.

**Model tiers:**
- Tier 1 (tiny): fast quality checks, rough drafts.
- Tier 2 (base): draft transcripts, speed-sensitive batch jobs.
- Tier 3 (small to medium): production captions, YouTube uploads.
- Tier 4 (large-v3): accuracy-critical work; default for dense niche vocabulary content.

**Caption formats:** SRT (YouTube uploads, broadest compatibility), WebVTT (HTML5 web embeds),
ASS/SSA (styled exports, optional).

**WER and CER validation:** Accuracy is measured by Word Error Rate and Character Error Rate
against a reference transcript using `shared/docintel/wer.py` (stdlib only, no dependencies).

- WER below 0.05: broadcast quality, proceed without additional review.
- WER 0.05 to 0.10: production-acceptable, light human review recommended.
- WER at or above 0.10: flag for human review; re-run with a larger model tier.

**Local scripts:** `shared/docintel/transcripts.py` normalizes any transcript format to a segment
array. `shared/docintel/wer.py` computes WER and CER. `shared/docintel/parse_text.py` produces
clean paragraph-style text for downstream content skills.

---

## Integrations

Integration logic is defined in `shared/integrations-engine.md`. All ingestion from any external
API or cloud storage ends at `shared/docintel/` via the classify, parse, injection-scan, and route
sequence. No spoke processes raw external content directly.

**Principles:** fetch once and parse locally; access only creator-owned data with minimum OAuth
scopes; fail transparently with structured failure records; treat all external content as untrusted.

### YouTube Data API v3

Used for video metadata, analytics, caption download, comment retrieval, and channel statistics.
Key endpoints: `videos.list` (1 unit), `channels.list` (1 unit), `commentThreads.list` (1 unit),
`playlistItems.list` (1 unit), `captions.list` (50 units), `search.list` (100 units),
`captions.download` (200 units). Default quota is 10,000 units per day; resets at midnight Pacific.

### Meta Graph API (Instagram)

Used for media listing, post-level insights, and comment retrieval. Base URL:
`https://graph.instagram.com/` (v22.0 and later). Note: the `impressions` field was deprecated in
v22.0 (April 2025); use `views` instead. Video captions are not accessible via the Graph API.

### TikTok APIs

Two surfaces: the Display API for public profile and video metadata (competitive research), and
the Content Posting API for programmatic publishing (OAuth required, scopes `video.upload` and
`video.publish`). Caption text is not available via either API; obtain from the creator directly
or via local STT.

### Microsoft OneDrive (Microsoft Graph API)

Used for file retrieval and ingestion. Auth via MSAL OAuth 2.0 with `Files.Read` scope. Large
files (above 5 MB) use range requests. All downloaded content is passed to
`shared/docintel/classify.py` then `shared/docintel/parse_text.py`.

### Google Drive

Two access paths: the `mcp__Google_Drive__*` MCP connector for interactive session use, and
the Google Drive API v3 for programmatic or batch access. Google Workspace documents (Docs, Sheets,
Slides) must be exported via the export endpoint before parsing; they are not downloadable as
binary files. After export, pass to `shared/docintel/classify.py` then
`shared/docintel/parse_text.py`.

### Failure handling

All API failures return a structured failure record with platform name, failure reason, and any
available retry-after or scope information. The system never guesses at content that was not
returned, never retries silently, and never fabricates API fields.

---

## Quality Gates

The quality gate is defined in `protocols/quality-gates.md`. No artifact (content, document, or
CRM record write) is released until it passes.

**Nine dimensions** scored 0 to 5: Integrity (critical), Accuracy, Brand and Aesthetic Alignment,
Audience Fit, Governance, User Intent, Accessibility, Professional Quality, and Safety (critical).

**Release thresholds:** no dimension below 3; Integrity and Safety each 4 or higher; composite
average 4.0 or higher.

**Hard fail:** Integrity or Safety scoring 0 to 1 triggers immediate failure regardless of the
composite. The artifact is not released, not softened, and not partially shipped.

**Gate process:**
1. The generating spoke produces a draft using the shared engines.
2. It self-checks against the nine dimensions.
3. It hands off to quality-review via the govern-artifact atom.
4. quality-review scores each dimension with a one-line evidence note and runs `scripts/score.py`.
5. The spoke fixes and re-scores until it passes.
6. Only a passing artifact is released. For CRM artifacts, the verdict is recorded alongside the
   record in `pipeline/`.

**Deterministic scoring.** The arithmetic is always done by `scripts/score.py`, not by hand.
The score.py script takes nine integer scores as JSON and returns a verdict object with the
composite, the pass/fail decision, and the hard-fail flag.
