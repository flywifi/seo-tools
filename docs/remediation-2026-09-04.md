# Remediation record — 2026-09-04 (P79)

Closes the open findings of `docs/integrity-currency-audit-2026-08-30.md` (P78) except those that need
the maintainer's Mac. Code landed in ten commits, P79-1 at `9ed1693` through P79-10 at `82f7414`; this
record lands in the commit that follows P79-10, so every claim below describes the tree at `82f7414`
plus the registry seeds this record itself declares. The plan's standing bar applied throughout: every
work package carried who/what/when/where/why/how, every guard change was red-teamed to fail before it
was allowed to pass, and no code was proposed that had not already been executed against the live
tree. Five read-only researchers crawled to primary sources; their evidence is condensed in section 4
with URLs, verbatim quotes, and fetch dates so it survives the session that produced it.

Authorization trace: "covering each of those items except items that require a mac" (all packages);
the three reversals of P76 decisions were each chosen explicitly after a written explanation
(advisory checks to blocking, the selftest enrolment gate, packaging content hashes); "Apply cited
diffs" for the data corrections. Nothing outside that trace was executed.

## 1. What landed, by commit

| commit | package | outcome, in one line |
|---|---|---|
| P79-1 `9ed1693` | A1 | `tools/geo_source_fetch.py` now serializes once, hashes that string, and writes it; a `--rehash-from-disk` verb re-stamped all 14 boundary hashes from the bytes on disk; the vertex counter counts every ring (the zoning polygon has a 5-point hole ring, so 128 became 133); offline `--selftest` added |
| P79-2 `b2b4d70` | A2, A3 | `tools/build_freshness_bundle.py` recompares the per-file sha256 it always stored (inside blocking invariant 26); `tools/doc_freshness.py` exits 1 on stale and 2 on unrecognized arguments; `.github/workflows/ci.yml` gained the projection-staleness step it never had |
| P79-3 `a36b6d0` | E1 to E7 | five moving dates verified against primary law and stamped; the EU Article 50 source finally seeded; three staged corrections executed and marked applied; two FL statute URLs bumped to the 2026 codification; the Buncombe hint corrected; `content_selector` gained a sanctioned writer and was set on the three FTC pages; `implementation/gpt/api/README.md` moved the Assistants sunset to past tense |
| P79-4 `82586c3` | F1 to F3 | the one `tier: "primary"` datum fixed and the T1/T2/T3 vocabulary enforced inside invariant 25; 26 unmapped canonical files classified into `canonical-sources/data-currency-map.json` with a six-way schema and coverage check; the traversal tool's next-step text no longer instructs a hand edit of the registry; excerpt-confidence became two structured fields |
| P79-5 `2214b36` | B1 to B4 | invariants 47, 51, and 56 flipped from advisory to problem, including their import-failure branches; invariant 45 stays advisory by recorded decision, its unreadable-file branch now blocks |
| P79-6 `6f3cb93` | G | `tools/transcribe.py` doctor verifies a discovered whisper model against its pin on the CLI path; the one-byte fixture that used to pass green now reports amber |
| P79-7 `4452eb5` | D1 to D4 | `tools/package_skill.py` writes and checks `implementation/skill-package-manifest.json` (a mtime-free sha256 per skill source tree, 130 skills), refuses duplicate leaf names instead of overwriting, gained `--selftest`; CI gained the `--check-manifest` step |
| P79-8 `bb77aa9` | H | `tools/hash_audit.py`: one verb that recomputes every stored hash; seven tracked stores gate the exit code, gitignored stores report only and are never created |
| P79-9 `1f74ed5` | I1, I2 | seven dependency baselines stamped after the battery ran green with those versions installed; numpy pinned below 2.5 because 2.5 drops the Python the video tooling was validated on |
| P79-10 `82f7414` | C | the selftest enrolment gate re-landed in `tools/selftest_sweep.py` with a pure core whose four branches are permanent selftest cases; `tools/selftest-exemption.json` names the 22 remaining files with reasons |

## 2. Proof ledger (executed, not recalled)

| # | claim | how it was proven | result |
|---|---|---|---|
| P1 | the GIS fix recipe is byte-compatible with the committed cache | `json.dumps(fc, indent=2)` compared to each committed GeoJSON's bytes | 7 of 7 identical |
| P2 | the bundle recompare catches a desync and stays quiet on a clean tree | ran the block against the live bundle, then against a flipped byte | clean; exactly one problem naming the file |
| P3 | the P74 enrolment gate is recoverable verbatim | `git cat-file -t 29bc694` | `commit`; code, exemption file, and doc section extracted |
| P4 | the recovered gate maps onto the finished tree with no drift | its discovery logic run against today's tree before landing | 111 tracked, 87 discovered, 22 uncovered, all 22 already listed, 0 stale |
| P5 | selector-scoped hashing ends the FTC churn | live fetch of the marketers guide with `main#main-content` | scoped hash differs from whole-body, 5,138 characters captured, operative guidance inside, request tokens excluded |
| P6 | the invariant-25 extension fires on each blind spot exactly once | five-way in-memory desync of the currency map | each sub-check fired once; coverage went from 28 unmapped to 0 within the commit |
| P7 | hash_audit reads the real video-library schema | read the SQLite schema instead of guessing | the key is `video_key`, not `video_id`; 24 columns |
| P8 | the package manifest is deterministic and cheap | two generator passes over all skill trees | identical output, 0.05 seconds, no leaf collisions today |
| P9 | doctor verification rejects the historical gap | one-byte `ggml-base.en.bin` fixture and an unlisted name | sha256 mismatch; not in allowlist |
| P14 | the vertex miscount is the outer-ring-only bug | corrected counter against the seven live-layer counts | 204, 50, 46, 82, 66, 104, 133 reproduced exactly |
| X1 | fail-then-pass for every promoted or new guard | inv 47 (byte appended to a projection), inv 51 (comment added to a bound source), inv 56 (one character flipped in the registry), tier vocabulary, map coverage, bundle recompare, enrolment gate three ways, package manifest drift and duplicate leaf | every red-team failed as required and passed after restore; `git status` clean after each |
| X2 | dependency validation is real, not nominal | scratch venv with the seven packages; full selftest sweep and drift guard under that interpreter; sqlite-vec extension loaded and `vec_version()` answered; Playwright launched a real Chromium via `executable_path` and rendered a page | sweep 88 of 88, guard clean, backends active rather than fallen back |
| X3 | hash_audit's own fail-then-pass on real data | run before and after P79-1 | GIS 14 of 14 mismatch before; ok after |

## 3. Guard changes, stated as decisions

- **Blocking now:** projection staleness (inv 47), doc freshness (inv 51), registry content digest
  (inv 56), the freshness-bundle per-file recompare (inside inv 26), tier vocabulary and currency-map
  coverage (inside inv 25), the doc-freshness CI step (exit-coded), the projection CI step (new), the
  package-manifest CI step (new), and the selftest enrolment gate (inside the sweep, which CI runs).
- **Still advisory, by decision:** invariant 45 (registry stamps newer than the freshness bundle). It
  is a pure date comparison that fires the moment any source is stamped, so promoting it would turn
  every routine `mark-checked` into a build break until the bundle is re-applied. Its docstring records
  this. Its unreadable-file branch now blocks, because an unreadable input is infrastructure failure,
  not a heuristic.
- **No new invariant numbers.** Every extension lives inside invariants 25 and 26 or inside a tool,
  so no count-truth doc moved. The drift guard is clean with its full invariant set unchanged.
- **Doctrine for `tools/hash_audit.py`:** it is a tool plus a sweep selftest, not an invariant,
  because eight of its stores are gitignored and an invariant must never depend on out-of-repo state.

## 4. Research evidence (five read-only researchers, all accepted at the exhaustiveness bar)

### 4.1 Legal moving dates (fetched 2026-09-04)

| item | primary source | verbatim | verdict and action taken |
|---|---|---|---|
| EU AI Act Art. 50 | Art. 113 as reproduced by the AI Act explorer (EUR-Lex itself returned HTTP 202 with an empty body from this egress) | "It shall apply from 2 August 2026." | confirmed; two official Commission instruments the staged seed predated are now cited: the Article 50 transparency guidelines ("Article 50 of the AI Act applies from 2 August 2026.") and the 2026-06-10 Code of Practice on marking and labelling ("The Code is voluntary and sets out practical steps to help providers and deployers of generative artificial intelligence (AI) systems"). Both are registered by this record. A law-firm-reported transitional easing for pre-2026-08-02 systems was NOT confirmed on a Commission page and is not recorded as fact. |
| CA SB 942 (AI Transparency Act) | leginfo: SB 942 (Ch. 291), AB 853 (Ch. 674, approved 2025-10-13), codified BPC div. 8 ch. 25 | "This chapter shall become operative on August 2, 2026." | confirmed; the repo did not track the 2028-01-01 capture-device phase AB 853 created, and phase 2 (2027-01-01) covers two obligation sets (large online platforms and GenAI hosting platforms). The description in `canonical-sources/moving-dates.json` now says so; the schema gained no field. Covered provider unchanged: over 1,000,000 monthly visitors or users, publicly accessible in California. |
| NY synthetic-performer disclosure | nysenate.gov S8420-A, Chapter 617, signed 2025-12-11 | "This act shall take effect on the one hundred eightieth day after it shall have become a law." (= 2026-06-09); "SHALL CONSPICUOUSLY DISCLOSE IN SUCH ADVERTISEMENT THAT A SYNTHETIC PERFORMER IS IN SUCH ADVERTISEMENT, WHERE SUCH PERSON HAS ACTUAL KNOWLEDGE." | confirmed; the source was fetchable on 2026-09-04 although the registry recorded a challenge block on 2026-08-30, so the staged `mark-checked --changed` correction was executed with a real verification |
| OpenAI Assistants API | developers.openai.com deprecations and migrate-to-responses pages | "The Assistants API was officially sunset on August 26, 2026, and is no longer available."; replacement "Responses API and Conversations API" | confirmed and now past tense; `implementation/gpt/api/README.md` corrected, and the description names both replacement APIs |
| Homebrew 5 casks | the Homebrew 5.0.0 announcement (content hash stored by the sweep) | casks failing Gatekeeper are disabled from September 2026; the post gives month precision only | verified at month precision; `verified_after` stamped; the tier datum on the registry entry corrected from `primary` to T1 |

### 4.2 Dependency drift, release by release (fetched 2026-09-04)

Release ranges verified on PyPI: numpy 2.4.6 (2026-05-18) to 2.5.0 (2026-06-21), 2.5.1 (2026-07-04),
2.5.2 (2026-08-09); PyAV 18.0.0 to 18.1.0 (2026-08-12); PySceneDetect 0.7 to 0.7.1 (2026-07-22);
mcp 1.28 to 2.0.0 stable (2026-07-28). Every changelog item was mapped against every usage site.

| package | what changed upstream | our usage | verdict |
|---|---|---|---|
| numpy 2.5.0 | "drops Python 3.11" (supports 3.12 to 3.14); 12 new deprecations (setting `dtype` or `shape` attributes, `fix`, `char.*`, `take` out-cast, in-place `resize`, and others); 12 expirations (`distutils`, `row_stack`, 2-D `cross`, `finfo(None)`, and others); `linalg.eig` always complex; `where` no longer truncates Python ints | `tools/videoedit/mediaprobe.py`: `frombuffer(..., int16).astype(float64)`, `sqrt(mean(arr*arr))`, nothing else | AFFECTED only by the Python floor: the validated environment is Python 3.11.15 (`docs/video-tooling-integration-evidence.json`), so the drift is uninstallable there. No deprecation or expiration touches a call we make. Pinned `>=2.4,<2.5` in `requirements-videoedit.txt`; raise with the Python 3.12 migration. |
| numpy 2.5.1, 2.5.2 | patch releases; 20 and 28 PRs read in full; gcc 10.3 floor for source builds; `PyArray_StringDTypeObject` opaque under abi3t | wheels only; no C API | not affected |
| PyAV 18.1.0 | additive features (`AVRational`, `Frame.metadata`, `rescale_ts`, CUDA); fixes to `VideoFrame.save`, `add_stream` frame rate, mid-stream codec changes, missing `CodecContext`; "Support for building from source against FFmpeg 9.0 (binary wheels ship FFmpeg 8.1.2)" | audio-only decode via `av.open`, `decode`, `AudioResampler` | not affected on every item; baseline NOT re-stamped because validated means tested with media (Mac runbook, section 7) |
| PySceneDetect 0.7.1 | `detect()` gains a `backend` keyword defaulting to `"opencv"`; PyAV-backend fixes; `FrameTimecode` comparison precision; additive helpers | `detect(path, ContentDetector(threshold))` on the default backend; reads `.seconds` | not affected on every item; same Mac-side disposition |
| mcp 2.0.0 | `FastMCP` renamed `MCPServer`; `mcp.types` moved to the `mcp-types` package with snake_case fields; `streamablehttp_client` and WebSocket transport removed; transport parameters moved to `run()`; `MCP_*` env vars and `.env` no longer read; `McpError` renamed `MCPError`; sync handlers on a worker thread; results schema-validated; "v1.x is in maintenance mode and will only receive security fixes" | `tools/mcp_server.py` imports `FastMCP`, `mcp.types.ToolAnnotations`, probes `_tool_manager._tools`, wraps the streamable-http app builder | a real port, deferred as a future phase with this checklist; the `>=1.28,<2` pin in `requirements-mcp.txt` stands |

Side observation recorded, not acted on: `tools/videoedit/mediaprobe.py` falls back to `audioop`, which
leaves the standard library after Python 3.12, so the Python upgrade the numpy drift forces will also
need that fallback revisited.

### 4.3 The seven changed legal pages: token churn, zero corrections

Mechanism proven: two consecutive fetches of the FTC endorsement FAQ differed only in seven per-request
Drupal `js-view-dom-id` tokens, so a whole-body hash moves on every fetch by construction. All three FTC
HTML pages carry `<main id="main-content">`, and the repo already supported selector-scoped hashing
(`tools/freshness_overlay.py`, `content_hash`), which nothing had used. P79-3 gave the field a sanctioned
writer and set it on the three pages; the next sweep reports one final `changed` per entry as the stored
whole-body hash is replaced, then stability.

| page | revision stamp on the page | fact the repo consumes, verbatim on the page today | verdict |
|---|---|---|---|
| FTC Endorsement Guides FAQ | "June 2023" | "the ultimate responsibility for clearly and conspicuously disclosing a material connection rests with the influencer and the brand" (the sentence continues to exclude the platform) | churn |
| FTC endorsements hub | (landing page) | guidance link set unchanged; cases list now led by Publishing.com, TruHeight, NextMed, Click Profit (the page doing its job) | churn |
| FTC soliciting and paying for reviews | "January 2022" | "If you offer an incentive for a review, don't condition it, explicitly or implicitly, on the review being positive." | churn |
| FTC press-release feed | (feed) | rotation is its function; two on-topic items since 2026-07-07 (section 5) | churn |
| Federal Register FTC API | (API) | newest document is 2026-17428 (Part 310, telemarketing fees); zero Part 255 or Part 465 activity since 2026-07-07; the last Part 465 rule remains 2024-18519 | churn |
| Cornell Wex: contract | "Last reviewed in October of 2025" | raw-body sha256 equals the registry's stored value; mutual assent, consideration, capacity, legality all present | churn |
| Cornell Wex: license | "Last reviewed in June of 2020" | raw-body sha256 equals the registry's stored value; "Licenses may have territorial and/or time limits and can be revoked or forfeited." | churn |

Honesty boundary: the exact 2026-07-07 bytes could not be diffed because web.archive.org and the
Memento aggregator are unreachable from this egress; the verdicts rest on the demonstrated token churn
plus intact in-page revision stamps, and for the two Wex pages on a stored-hash match.

### 4.4 The ten changed jurisdiction and GIS sources: metadata churn, zero overlay corrections

| source | what actually moved | what the repo depends on, verified | action |
|---|---|---|---|
| SFWMD open data hub | daily permit feeds (approved ERPs modified 2026-09-03) | every basin and boundary dataset last modified 2018 to 2024 | none |
| Miami historic districts layer | Hub page re-render | layer `lastEditDate` 2021-02-08; 12 features; extent consistent with the illustrative bbox | none |
| FL statute 553.899 (milestone inspections) | site chrome added the 2026 codification | operative text byte-identical between the 2025 and 2026 codifications: "by December 31 of the year in which the building reaches 30 years of age" | URL bumped to the 2026 codification |
| FL statute 553.842 (product approval) | same chrome | byte-identical: "a product evaluation and approval system that applies statewide" | URL bumped |
| Buncombe GIS overlays | service roster update | layers 7 Protected Ridges, 20 County Zoning Overlay, 35 Stability Index Map unchanged; a raster layer 43 "PERCENT SLOPE" now exists | extraction hint corrected (the old "(no slope-percent layer)" was no longer literally true) |
| NC OneMap watersheds | portal rebuild | "NC Surface Water Supply Watersheds" modified 2024-07-10 | none |
| Orlando historic districts layer | bulk republish stamped `lastEditDate` 2026-08-30 | all six districts compared coordinate by coordinate against the committed GeoJSON: identical; vertex counts 204, 50, 46, 82, 66, 104 | none; the cache needs no refetch |
| Orlando zoning layer | same republish, 100 seconds later | point query returns "R-2B/T/HP", "Traditional City 62.600 to 62.629", "Lake Eola Heights Historic District"; polygon identical, 133 vertices both sides | none; the 128-vs-133 discrepancy was our counter, fixed in P79-1 |
| Orlando historic-preservation page | CMS churn | six districts named; "a Certificate of Appropriateness must first be issued by the Historic Preservation Board" | none |
| Orlando residential standards guide | CMS churn | overlay legend intact ("/T is the Traditional City Overlay"); setback values still absent, so the null flag stays correct | none |

### 4.5 Internal census (R-CODE) that shaped the code

The exact seams: `tools/doc_freshness.py` returned 0 on stale and on any mistyped flag; the projection
checker already exited 1 but was absent from CI; whisper doctor's discovery was name-only, with the
proof in its own selftest (a one-byte model file reported green); tier was validated nowhere (help text
only); 42 canonical files sat outside the currency map and classified into its four classes with zero
new registry entries; the traversal tool's next-step text told operators, verbatim, to hand-edit the
registry (an instruction whose obedience would fail the promoted digest check, so it was reworked
before the promotion); the packaging step wrote two same-leaf skill directories to one archive; and
`tools/hash_audit.py`'s draft guessed a column name that reading the schema corrected.

## 5. Watch-notes (enforcement context, not guidance changes)

Two FTC press-release items since the P78 baseline are on-topic for legal-requirement-check and are
recorded here rather than edited into consumer docs, because neither changes the disclosure guidance
the repo cites:

- 2026-07-15, final order against TruHeight (Vanilla Chip LLC): bars "using fake or incentivized
  consumer reviews"; the complaint alleged reviews "written by their own employees and vendors, or by
  consumers who were offered a free product or discount in return for writing a 5-star review".
- 2026-08-27, finalized orders with Cox Media Group and two other firms over deceptive marketing of an
  "Active Listening" AI-powered service: an AI-capability deception case, not an endorsement action.

Both surfaced through the registered `ftc-press-release-feed` source.

## 5a. The six new registry sources, first check from this egress

Seeded through `source_sync.py reconcile` and `seed-sources`, then checked once with `check --detect-changes --apply --only`. Checked and content-hashed: `eu-ai-act-article-50-guidelines`, `eu-ai-act-aigc-code-of-practice`, `mcp-python-sdk-migration`. Bot-blocked at this egress and recorded as such rather than stamped: `numpy-release-notes` (ip_block/Cloudflare), `pyav-releases` (ip_block/None), `pyscenedetect-releases` (ip_block/None). The researchers read these pages in full through a different fetch path on 2026-09-04, so the facts stand; the entries join the Mac re-run queue with the other blocked sources.

## 6. Dependency disposition after P79-9

`dependency_currency report`: 13 current, 3 minor drift (numpy, av, scenedetect), 1 major drift (mcp,
install-safe behind its pin), 1 no-baseline (`mcp-stats-compass`, an MCP server not importable-testable
here), 17 advisory by design (no machine-readable feed). The seven stamped baselines are exactly the
versions the battery ran green against: requests 2.34.2, charset-normalizer 3.5.1, beautifulsoup4
4.15.0, python-dateutil 2.9.0.post0, sqlite-vec 0.1.9, PyYAML 6.0.3, playwright 1.62.0. Each entry's
hint records the validation scope in words.

## 7. Not exercisable here: the Mac runbook

| item | command on the machine that has the data or the egress |
|---|---|
| the 110 bot-blocked sources | `python3 tools/source_currency.py check --detect-changes --apply` from residential egress; a success clears each block record automatically |
| av and scenedetect baselines | re-run the golden-cut check from `docs/video-tooling-integration-evidence.json` with real media (expects cuts at 60.0, 150.0, 240.0, 330.0), then `update-source dep-av --validated-version 18.1.0` and `update-source dep-scenedetect --validated-version 0.7.1` |
| scoop cache baseline | `python3 tools/hash_audit.py` reports the local baseline as report-only MISMATCH (entries legitimately changed since the last build); `python3 shared/cache/cache.py --build` re-baselines |
| competitor index repair (P75) | `python3 tools/competitor_snapshot.py --check-og`, then `--parse`, then `--check-og` again |
| self-release stamp | `python3 tools/update_check.py check --apply` (the releases API is blocked through this proxy) |
| freshness scheduler | install per `docs/CURRENCY.md` "Weekly automation" |

## 8. Recorded, not done

- No new numbered invariants; no interval re-band; no tag; no PR; no edits to any data file downstream
  of a changed source (every changed page was read and verdicted instead).
- Invariant 45 stays advisory (section 3).
- The mcp 2.0 port is deferred with its checklist (section 4.2).
- `mcp-stats-compass` stays without a baseline, with the reason recorded on the entry.
- **New finding, recorded for the maintainer:** `CLAUDE.md` (and its projection `AGENTS.md`) state that
  `tools/dependency_currency.py` reconciles against the requirements files, the evidence file, and the
  connector registry. The tool reads only the registry's own `validated_version` and `pinned_constraint`
  fields; it opens none of those three files. The registry fields are therefore the single source of
  truth for drift math, which is why P79-9 mirrored the numpy pin into `pinned_constraint` (as the
  scenedetect and mcp entries already did). Correcting the CLAUDE.md sentence is a projection-source
  edit outside this plan's authorization and is left to the maintainer.
- The excerpt-confidence prose prefixes on five OpenAI help-center entries stay as the human
  explanation; the structured `excerpt_confidence` and `excerpt_verified_at` fields are authoritative
  for tooling (`docs/CURRENCY.md`, "Blocked is not gone").

## 9. Verification at the code HEAD

Battery at `82f7414`, gated on exit codes rather than on tail output: drift guard clean (full invariant
set, count unchanged from P78); `scenario_check.py` reported 10/10; selftest sweep 88 of 88 with the
enrolment gate clean; doc freshness current; projections clean; version consistent at 0.2.0; preflight
clean; staged secret scan clean; `hash_audit.py` PASS with all seven tracked stores recomputed clean.
The registry diff for every stamping step was written only by the sanctioned writers, and the content
digest re-verified after each.

```sources
[
  {"id": "eu-ai-act-article-50", "url": "https://artificialintelligenceact.eu/article/50/"},
  {"id": "eu-ai-act-article-50-guidelines", "name": "European Commission - Guidelines on transparency obligations for AI-generated content (AI Act Article 50)", "url": "https://digital-strategy.ec.europa.eu/en/policies/guidelines-transparency-ai-generated-content", "category": "legal-authority", "tier": "T1", "check_interval_days": 90, "staleness_threshold_days": 120, "extraction_hint": "Commission guidelines for Article 50 transparency obligations; states 'Article 50 of the AI Act applies from 2 August 2026'; watch for adoption-date and scope changes; reachable from cloud egress while EUR-Lex is not", "used_by": ["tools/publishing_compliance.py", "shared/contract-engine.md", "legal-requirement-check"]},
  {"id": "eu-ai-act-aigc-code-of-practice", "name": "European Commission - Code of Practice on marking and labelling AI-generated content (published 2026-06-10)", "url": "https://digital-strategy.ec.europa.eu/en/news/commission-publishes-code-practice-marking-and-labelling-ai-generated-content", "category": "legal-authority", "tier": "T1", "check_interval_days": 180, "staleness_threshold_days": 200, "extraction_hint": "voluntary Code of Practice giving practical steps for providers and deployers of generative AI to meet Article 50 marking and labelling duties; watch for a successor edition", "used_by": ["tools/publishing_compliance.py", "shared/contract-engine.md", "legal-requirement-check"]},
  {"id": "ny-synthetic-performer-law", "url": "https://www.nysenate.gov/legislation/bills/2025/S8420"},
  {"id": "ca-ai-transparency-sb942", "url": "https://leginfo.legislature.ca.gov/faces/billNavClient.xhtml?bill_id=202320240SB942"},
  {"id": "openai-migrate-to-responses", "url": "https://developers.openai.com/api/docs/guides/migrate-to-responses"},
  {"id": "homebrew-5-cask-gatekeeper", "url": "https://brew.sh/2025/11/12/homebrew-5.0.0/"},
  {"id": "numpy-release-notes", "name": "NumPy release notes (stable)", "url": "https://numpy.org/doc/stable/release.html", "category": "api-changelog", "tier": "T1", "check_interval_days": 30, "staleness_threshold_days": 60, "extraction_hint": "per-release deprecations, expirations, and the supported Python range; 2.5.0 dropped Python 3.11, which is why requirements-videoedit.txt pins numpy below 2.5", "used_by": ["tools/videoedit/mediaprobe.py", "requirements-videoedit.txt"]},
  {"id": "pyav-releases", "name": "PyAV GitHub releases", "url": "https://github.com/PyAV-Org/PyAV/releases", "category": "api-changelog", "tier": "T1", "check_interval_days": 30, "staleness_threshold_days": 60, "extraction_hint": "per-release feature and fix list; the repo's audio-only decode path (av.open, decode, AudioResampler) is what matters; wheel FFmpeg series", "used_by": ["tools/videoedit/mediaprobe.py"]},
  {"id": "pyscenedetect-releases", "name": "PySceneDetect GitHub releases", "url": "https://github.com/Breakthrough/PySceneDetect/releases", "category": "api-changelog", "tier": "T1", "check_interval_days": 30, "staleness_threshold_days": 60, "extraction_hint": "detect() and ContentDetector API changes and the default backend; cross-check against the scenedetect.com changelog", "used_by": ["tools/videoedit/mediaprobe.py"]},
  {"id": "mcp-python-sdk-migration", "name": "MCP Python SDK v2 migration guide", "url": "https://py.sdk.modelcontextprotocol.io/migration/", "category": "api-changelog", "tier": "T1", "check_interval_days": 60, "staleness_threshold_days": 90, "extraction_hint": "the FastMCP to MCPServer rename, the mcp-types package split, transport and env-var changes; the checklist for the deferred mcp 2.x port of tools/mcp_server.py", "used_by": ["tools/mcp_server.py", "requirements-mcp.txt"]},
  {"id": "ftc-endorsements-faq"},
  {"id": "ftc-endorsements-hub"},
  {"id": "ftc-soliciting-reviews-marketers"},
  {"id": "ftc-press-release-feed"},
  {"id": "federal-register-ftc-api"},
  {"id": "cornell-wex-contract"},
  {"id": "cornell-wex-license"},
  {"id": "fl-statute-553-899-milestone"},
  {"id": "fl-statute-553-842-product-approval"},
  {"id": "buncombe-gis-overlays"},
  {"id": "orlando-historic-districts-gis"},
  {"id": "orlando-zoning-gis"},
  {"id": "sfwmd-open-data-gis"},
  {"id": "miami-historic-districts-gis"},
  {"id": "nc-onemap-watersheds"},
  {"id": "orlando-city-code-ch62"},
  {"id": "orlando-ldc-traditional-city"},
  {"id": "dep-numpy"},
  {"id": "dep-av"},
  {"id": "dep-scenedetect"},
  {"id": "dep-mcp"},
  {"id": "mcp-stats-compass"}
]
```
