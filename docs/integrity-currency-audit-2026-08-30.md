# Integrity and currency audit — 2026-08-30 (P78)

Audited at data-commit HEAD `b1bc5dd` (census pass B and the battery ran there; this report lands
in the records commit that follows it). Scope set by the maintainer in four explicit decisions: verification gaps are
REPORTED not closed; the source sweep is FULL; guard behavior is RECORDED not changed; dependency
drift is RECORDED not acted on. This audit therefore wrote exactly three kinds of thing: registry
stamps through the sanctioned writers, the freshness re-stamp rituals those stamps mandate, and
this report with its records.

Method note: every mechanism below was verified by RECOMPUTING the stored hash from current
bytes, never by checking that a stored value exists or agrees with a sibling record. The GIS
finding (F2) is why that distinction is the whole audit: fourteen stored hashes agreed with each
other perfectly and had never matched a byte on disk.

## 1. Summary index

| id | sev | one line | status |
|---|---|---|---|
| F1 | MED | Freshness-bundle per-file hashes are stored but never recompared; one was stale in the live tree | closed P79-2: `check()` now recompares every stored per-file sha inside blocking invariant 26 |
| F2 | HIGH | All 14 GIS boundary hashes (manifest + provenance) never matched the committed bytes — the writer hashes one serialization and writes another | closed P79-1: the writer hashes the bytes it writes; all 14 hashes re-stamped from disk; `tools/hash_audit.py` recomputes them clean |
| F3 | MED | 110 of 222 web sources are bot-blocked at this environment's egress and cannot be verified from here | still the Mac re-run queue (110 entries; each carries a durable block record); see the P79 record, section 7 |
| F4 | MED | 18 sources changed content since their last reading, including the FTC endorsement cluster and 10 jurisdiction/GIS authorities | closed P79-3 as churn: all 18 pages read to the operative text, zero downstream corrections; selector-scoped hashing on the three FTC pages ends the class |
| F5 | MED | Four moving dates have passed; two never re-verified after their effective date (`eu-ai-act-article-50`, `assistants-api-sunset`), one verified before it (`ca-ai-transparency-sb942`), one blocked (`ny-synthetic-performer-disclosure`) | closed P79-3: all four verified against primary law and stamped; the Art. 50 source seeded; the staged corrections applied |
| F6 | MED | Integrity controls that observe but never refuse: registry digest, projection staleness, and doc-freshness checks are advisory; the doc-freshness CI step exits 0 even when stale; the projection check is not in CI | closed P79-2 and P79-5: doc-freshness exit-coded, projection step added to CI, invariants 47, 51, and 56 blocking; 45 stays advisory by recorded decision |
| F7 | MED | Dependency drift: 1 breaking (mcp 2.0.0, install-safe behind the `<2` pin), 3 minor (numpy, av, scenedetect), 8 previously had no baseline | P79-9: seven no-baseline entries validated by battery and stamped; numpy pinned to its validated ceiling; av and scenedetect stay Mac-side; mcp 2.0 deferred with a port checklist |
| F8 | LOW | Written-never-read hash stores: video library rows, construction-library manifest, GIS manifest (F2's enabler), bucket manifests with no scheduled verifier | closed P79-8: `tools/hash_audit.py` gives every stored hash a reader; tracked stores gate the exit code, local stores report |
| F9 | LOW | Registry hygiene: one entry carries tier `primary` instead of a `T*` value; 42 tracked canonical files are absent from the currency map; the map's own as-of is 2026-07-07; excerpt-confidence is a free-text convention, not a field | closed P79-4: tier datum fixed and the vocabulary enforced; 26 files mapped with a coverage check; excerpt-confidence structured; map as-of 2026-09-04 |
| F10 | LOW | The whisper model pins verify byte-exact upstream today, but verification happens only at download; a swapped file after download is not detected, and the pins file is itself unpinned | closed P79-6: doctor verifies a discovered model against its pin on the CLI path |
| F11 | LOW | The packaged plugin artifacts carry no content hashes; packaging integrity rests on version equality alone | closed P79-7: per-skill source-tree manifest with a CI check |
| F12 | LOW | The self-release entry cannot be stamped from this environment (releases API unreachable through the proxy); it stays honestly unstamped | still unstampable from this egress; Mac runbook in the P79 record |

Status column updated 2026-09-04 by P79 (`docs/remediation-2026-09-04.md`); the rest of this report is the
2026-08-30 record and is unchanged.

## 2. The hash census — recomputed, both passes

Pass A ran at the pre-sweep HEAD `61dd921`; pass B re-ran the mechanisms the sweep and rituals
touch. Outputs pasted verbatim from the runs.

```
CENSUS PASS A @ HEAD 61dd921
  1 mac-surface: 85 files, 0 mismatch
  2 registry _content_digest: MATCH
  3 projection: 94 hashes, 0 mismatch
  4 doc-freshness: 15 docs, 40 hashes, 0 stale
  5 bundle: 12 files, stale=['implementation/gpt/web/custom-instructions.md']   <- F1
     canonical_digest MATCH
  7 GIS: MANIFEST 7/7 disk-mismatch, provenance 7/7 disk-mismatch,
     7/7 match the never-written sort_keys serialization                        <- F2
  9 git fsck: clean

CENSUS PASS B (post-sweep, post-ritual)
  2 registry _content_digest: MATCH        (re-stamped by the sanctioned writer)
  5 bundle: 12 files, stale=NONE           (F1 instance cured by the ritual)
     canonical_digest: MATCH
  8 registry content_sha256 coverage: 106/257; last_checked null=122; block-recorded=110
```

Whisper pins, checked upstream by HEAD request without following the redirect, reading the
linked-content headers off the response (the header name is case-sensitive when converted to a
plain dict; read it from the HTTP message object):

```
base.en / small.en / small / medium / large-v3 / large-v3-turbo
   all 302; linked etag == pinned sha256, linked size == pinned bytes  (6/6)
```

### F2 in full — wrong since birth, and why nothing noticed

`tools/geo_source_fetch.py::_write_geojson` computes the hash over
`json.dumps(feature_collection, sort_keys=True)` (compact separators, sorted keys) and then
writes the file with `json.dump(feature_collection, f, indent=2)` (indented, insertion order).
Different bytes. Every one of the 7 manifest hashes and 7 provenance-sidecar hashes describes a
serialization that was never written to disk. Recomputing with the hashed recipe matches 7/7, so
the boundary data itself is INTACT — the hashes were simply never hashes *of the files*. Nothing
noticed since 2026-07-07 because no code anywhere reads these hashes (F8). The one-line fix is to
hash the same bytes that are written (serialize once, hash it, write it); per the scope decision
it is NAMED here and not applied.

### F1 in full — stored but never recompared

`build_freshness_bundle.check()` verifies marker presence, file listing, the canonical digest,
and the combined pack body — but reads `managed_files` only for the file NAMES; the per-file
sha256 it writes is never recompared by anything. The P74-5 version re-stamp changed
`custom-instructions.md` after the last bundle apply, and the stored hash sat stale until this
census recomputed it. The mandated post-stamp ritual re-applied the bundle and cured the
instance; the class (a verifier that ignores its own strongest field) stays open by scope
decision.

## 3. The currency sweep — first complete pass

All writes went through the sanctioned writers; the registry diff was machine-audited before
staging as field-additions only (auditor output: empty), and the content digest re-verified in
pass B.

**Dependencies (35 entries):** 18 stamped, drift flagged on `dep-mcp` (major, breaking — the
installed pin `>=1.28,<2` makes it install-safe), `dep-numpy` 2.4.6 to 2.5.2, `dep-av` 18.0.0 to
18.1.0, `dep-scenedetect` 0.7 to 0.7.1. Entries with no machine-readable feed remain advisory by
design and unstamped. Nothing was upgraded or re-pinned (scope decision).

**Web sources (222 fetched):**

| bucket | count | meaning |
|---|---|---|
| unchanged | 9 | prior hash matched, or origin returned not-modified |
| first_seen | 76 | first content hash ever recorded |
| changed | 18 | content hash moved vs the stored reading (F4) |
| unreachable | 9 | clean 404/410 or transient failure — NOT blocked |
| blocked | 110 | bot wall (F3): never stamped checked, block state recorded |

213 entries received stamps. `last_checked` null went from 182 to 122; every remaining null is a
blocked, unreachable, advisory-dependency, or the self-release entry — i.e. accounted for, not
forgotten.

**F4 — the changed queue.** A changed verdict means the page BYTES moved (whole-body hash);
boilerplate churn is indistinguishable from substance without reading the page, so per the
no-fabrication protocol no downstream data was touched. The 18, with their consumers: the FTC
endorsement cluster (`ftc-endorsements-faq`, `ftc-endorsements-hub`,
`ftc-soliciting-reviews-marketers`, `ftc-press-release-feed`, `federal-register-ftc-api` — feeding
legal-requirement-check and contract-review), the Cornell contract/license pages,
`ca-ai-transparency-sb942` (publishing_compliance), and ten jurisdiction/GIS authorities (SFWMD,
Miami historic districts, two FL statutes, Buncombe, NC watersheds, and four Orlando
code/zoning/historic sources — feeding jurisdiction-desk and the committed overlay files). Review
each page before trusting the derived overlay or legal data it feeds.

**F3 — the blocked set.** 110 sources sit behind Cloudflare/Akamai/reCAPTCHA/AWS-WAF walls as
seen from this environment's egress address. Each now carries `last_block_detected`,
`block_kind`, and `block_vendor` — the first time the durable block fields have ever held real
data — and none was stamped checked or counted stale. This is an environmental ceiling, not
source rot: most of these hosts serve a normal browser. The five OpenAI help-center pages remain
excerpt-confidence, which is their documented pass state. **The whole blocked list is the re-run
queue for a machine with residential egress**: `python3 tools/source_currency.py check
--detect-changes --apply` re-attempts everything and a success clears the block state
automatically.

**Self-release (F12):** the releases API returns 403 through this proxy, so `creator-os-release`
stays unstamped, correctly classified blocked rather than absent.

## 4. Seeds, datasets, and the currency map

- **Seeds reconcile clean:** 138 real entries across the 13 seed arrays all resolve to registry
  ids (the staged EU-AI-Act object and a comment header are excluded by shape, verified
  individually). Seeded means applied; nothing was seeded and lost.
- **Currency map (F9):** its 35 entries all resolve, but 42 tracked canonical files are in no
  class — the 13 seed arrays + staged object, construction SVG diagrams, the whisper pins file,
  and the platform-specs/personas/rate-benchmarks/seasonal-aesthetic/cost-library datasets, which
  also carry no internal freshness field at all. Five of those six dataset dirs have no tool
  reader anywhere in the tree; reference data no code consumes deserves an explicit decision
  (map it, wire it, or retire it) rather than silence. Map as-of: 2026-07-07.
- **Moving dates (F5):** passed and unverified — `eu-ai-act-article-50` (2026-08-02; its
  advisory fires in every guard run) and `assistants-api-sunset` (2026-08-26, newly passed);
  `ca-ai-transparency-sb942` was last verified 2026-07-07, before its own effective date, and its
  source page is in the changed queue; `ny-synthetic-performer-disclosure` (2026-06-09) is
  bot-blocked. The staged corrections in `volatile-corrections.2026-07-14.json` (three now
  `overdue`, one `proposed`) remain the maintainer's to apply.
- **Keyword library:** dated files last updated 2026-06-30; competitor summary still the blank
  template (nothing has run `--export-summary`).

## 5. Not exercisable from this environment

Local-only stores are absent in this clone by design. On the machine that has data:

| store | verify with |
|---|---|
| competitor snapshot index | `python3 tools/competitor_snapshot.py --check-og` (then `--parse` to repair) |
| inbox ledger | approvals re-hash at approve time (blocking); `python3 tools/handoff/inbox.py scan` |
| obligations / tasks / finance / editing buckets | each tool's `verify()` against its manifest — no scheduled caller exists (F8) |
| scoop cache baseline | `python3 shared/cache/cache.py --verify` |
| video library | no verifier exists — `content_hash` is written and read by nothing (F8) |
| construction library manifest | no runtime verifier exists (F8) |
| GitHub releases API | unreachable through this proxy (F12); `update_check` works with normal egress |
| the 110 blocked sources | the F3 re-run queue, from residential egress |

## 6. What was deliberately not done (the four scope decisions, plus standing ones)

No new verification tool or mechanism (the dead-hash classes in F1/F2/F8 are findings); no guard
promotions and no fix to the doc-freshness exit code or the projection check's CI absence (F6);
no dependency upgrades, re-pins, or baseline edits (F7); no re-band of check intervals and no
selftest-enrolment gate (P76 decisions stand); no edits to any data file downstream of a changed
source (F4 queue is for a human); no GIS code fix (F2 is named only); no tag, no PR.

## 7. Verification

Battery green at both commits: drift guard clean, scenario check full pass, selftest sweep full
pass, doc freshness current, projections clean, version consistent at 0.2.0, preflight clean,
staged secret scan clean. The registry diff audited as adds-only; the content digest recomputed
MATCH in both passes.
