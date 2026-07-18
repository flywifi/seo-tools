---
file: tools/handoff/MAINTAINER_README.md
purpose: preserve the non-negotiable safety invariants of the async compute hand-off so a future
  edit cannot silently break them. This is a tools-layer maintainer doc (invariant 50 requires it
  for this directory).
---

# tools/handoff: Maintainer README

## Purpose
The async compute hand-off (P60): a cloud surface creates a job ticket in the Drive hub's
`Jobs/queue/`, the local machine validates and executes it through the existing tool CLIs, and a
result file appears in `Jobs/results/`. Three transports (Drive for desktop sync, Drive API
polling, remote MCP submit) all feed this ONE queue and ONE runner, so this package is the single
execution path to audit. The contract of record is `shared/schemas/compute-job.json`; the layout
and write rules are `docs/DRIVE-HUB.md`.

## Non-negotiable invariants (do NOT weaken without an approval-gated change)
1. **Allowlist-only execution.** A job runs only if its `job_type` is in the schema enum AND has a
   builder in `JOB_BUILDERS`. Publishing, posting, sending, credential access, and shell
   passthrough are not job types; adding one is an approval-gated change to BOTH the schema and
   this doc. `<!-- verify: tools/handoff/runner.py::run_job -->`
2. **Tickets are data, never instructions.** Strict key set, strict enums, params validated per
   job type; values become fixed argv items, never shell strings and never text the model follows.
   `<!-- verify: tools/handoff/queue.py::validate_ticket -->`
3. **Idempotent by job id.** An id with an existing result never re-runs, which makes duplicate
   deliveries, Drive conflict copies, and double watchers harmless.
4. **Hub-confined inputs.** `input_refs` resolve inside the hub root by realpath containment (the
   wizard's folder-confinement rule); an escaping ref is refused before anything runs.
   `<!-- verify: tools/handoff/queue.py::resolve_input_refs -->`
5. **Gated off by default.** `run_pass` refuses to read or run anything while the
   `compute_handoff_enabled` capability is off. The `allow` override exists for the selftest only.
   `<!-- verify: tools/handoff/runner.py::run_pass -->`
6. **Create-only, atomic writes.** Tickets and results are tmp+rename creations; state transitions
   are new files; only the local machine moves tickets to the archive.
7. **Honest failure.** Every bad path (invalid ticket, unwired type, timeout, tool error) lands as
   a `refused`/`failed` result with a short log tail, never a raw traceback, never a silent skip.
8. **Read-only reports only where money or accounts are involved.** The finance builder accepts
   only the read-only reports (`ar-scan`, `cashflow`); the competitor builder runs the offline
   `--parse`, never the network fetch.

## Transport A (watcher.py, the default)
The watcher only decides WHERE the queue is and WHEN to look; every execution property above lives
in `run_pass`. Hub resolution: `--hub` argument, else `drive_hub.local_mirror` (local config over
committed), else an honest "not configured" note pointing at the wizard `/drive-hub` screen.
`detect_mirror_candidates` probes the macOS File Provider mount
(`~/Library/CloudStorage/GoogleDrive-*/My Drive/<folder>`) as a wizard convenience only; the user
confirms the path, and the wizard confines it to the home tree before saving.
`<!-- verify: tools/handoff/watcher.py::resolve_hub -->`
The schedule follows `tools/freshness-scheduler.example` (cron/launchd calling `--once`);
`--watch` is a foreground convenience with a 30-second floor on the interval.

## Transport B (drive_api.py, opt-in)
Same queue, same runner: `poll_once` pulls tickets into a LOCAL staging hub, calls `run_pass` (the
gate is re-checked there), uploads results, and archives handled tickets remotely. Rules: every
HTTP call goes through an injectable transport (canned in the selftest, zero network); uploads are
CREATE-only (the append-only rule holds on this transport too); the bearer token travels only in
the Authorization header, never a URL; only `googleapis.com` hosts are ever called; a gated pass
uploads and archives nothing. The OAuth entry is `google_drive` in `tools/oauth_flow.py`
(`drive.file` scope only) and the credential lives beside the publishing ones in the gitignored
store but is never read by the publishing path.
`<!-- verify: tools/handoff/drive_api.py::poll_once -->`

## The drop folder (inbox.py, P60-6)
The offline half of the `inbox-routing` atom. `scan` is READ-ONLY: it sha256-diffs `Inbox/`
against the local ledger, classifies each new file by FORMAT (`shared/docintel/classify.py`), and
proposes a route only for categories the rules table
(`shared/docintel/inbox_rules.json`) marks `category_source: "format"` (transcripts, media,
export archives). Content-gated categories (contracts, pitches, invoices) are listed as
`needs_review` with `classified_as: null` — this tool never pretends to have read a document; the
FULL injection guard runs in a Claude session (the atom), while the offline PATTERN tier
(`tools/injection_scan.py`) runs during scan as a buffer (P61, SEC-ALL). There are TWO sanctioned
writers, and both move by REALPATH containment (never a raw `hub / rel`, so `..`, symlinks, and a
case-insensitive filesystem cannot escape or dodge the sealed area) and never overwrite a same-name
file (a collision is kept as `name (2)`, so a sanctioned move never deletes):
- `approve` moves handled files to `Inbox/Processed/<date>/`, re-verifying each sha256 (a file
  changed since its scan is refused) and refusing any path that resolves into `Inbox/Quarantine/`
  or outside `Inbox/`; it appends to the gitignored ledger atomically.
- `sweep_quarantine` seals QUARANTINE/BLOCK files into `Inbox/Quarantine/<date>/` with their
  findings (the second writer; details under "The sealed Quarantine area" below).
Fail-closed for text (P61 audit): a transcript the offline tier could not read as text (binary
sniff, oversize, or the tool unavailable) is diverted to `needs_review`, never routed unscreened.
Two-pass handoff (P62): the offline verdict is pass 1. Every routed / needs-review record carries
its `offline_pattern_scan` prior AND `pass2_pending: true`, so a Claude session that later reads the
record runs the authoritative semantic guard (pass 2) with the prior as advisory input and writes a
reconciled verdict. A sealed file is terminal (`pass2_pending: false`); the session never sees it.
Model: `shared/injection-guard-engine.md` "Two-pass handoff" + `docs/INJECTION-TWO-PASS.md`.
The `inbox_scan` job type wires the same scan into the runner (read-only; the proposal lands in the
job result for review from any surface; approval stays on the wizard `/inbox` screen with its
single-use batch token).
`<!-- verify: tools/handoff/inbox.py::scan -->`
`<!-- verify: tools/handoff/inbox.py::approve -->`
`<!-- verify: tools/handoff/inbox.py::_confined_inbox_file -->`

## Free-text screening (P61, SEC-ALL)
`validate_ticket` runs the offline injection pattern tier (`tools/injection_scan.py`) over every
attacker-reachable free-text field in a ticket (`consent_note`, `requested_by`, and every string
value nested in `params`). A QUARANTINE or BLOCK verdict is a validation error, so the runner
refuses the ticket. This is DEFENSE IN DEPTH on the "tickets are data" rule and the lock that keeps
the wizard's work-order amendment textarea (which lands in `consent_note`) from ever becoming an
instruction channel. It FAILS CLOSED: if `injection_scan` cannot be imported, a ticket carrying
free text is refused, never silently passed.
`<!-- verify: tools/handoff/queue.py::_screen_free_text -->`

## Job builders (P61 additions and the R1 fix)
- `transcript_normalize` (new): a dropped transcript has no library record to attach to, so the job
  normalizes it into segments + silence gaps + suggested chapters via `shared/docintel/transcripts.py`.
  Attaching to a library `video_key` stays session work (honest; the result copy says so).
- `library_complete` (fixed): the shipped builder passed positional inputs, but the CLI requires
  `--export-dir` and rejected them, so EVERY queued job of this type failed with an argparse error.
  The builder now passes `--export-dir <inputs[0]>`. A runner selftest runs the built argv against
  an empty temp dir and asserts argparse accepts it, so that failure can never silently recur.
- **WRITE-OPTIN** (`library_complete --write`): a job writes to the store ONLY when its ticket sets
  `params.apply` AND the runner confirms the LOCAL `job_store_writes_enabled` capability at build
  time. A forged ticket flag alone can never enable a write (selftested both ways). Default is
  proposal-only.
- `transcribe_media`: the builder passes `--out-dir <hub>/Jobs/results` so the SRT lands beside the
  result, not inside `Inbox/Processed/`.
- **Outbox delivery (P61, R7)**: a report-style job that finishes `done` (the `OUTBOX_TYPES` set)
  also gets its stdout JSON delivered atomically to `<hub>/Outbox/<job_type>.<stamp>Z.mac.json`,
  with `outputs[]` listing both files. Failed jobs and non-JSON stdout never deliver;
  `transcribe_media` stays out (its artifact is the SRT). Transport B's `poll_once` uploads
  staged Outbox artifacts too (create-only; a hub without an Outbox folder degrades to
  results-only, never a failed pass).
  `<!-- verify: tools/handoff/runner.py::_deliver_outbox -->`
- **API-lane token refresh (P61, R6)**: `project_docs._api_token` now reuses the watcher's proven
  refresh path (`oauth_flow.get_valid_access_token` + `_persist_publish_creds`) instead of reading
  the stored access token verbatim, so the Docs lane no longer 401s an hour after connect. A dead
  grant degrades to the honest "reconnect on /drive-hub" note.
  `<!-- verify: tools/handoff/watcher.py::_persist_publish_creds -->`
- `keyword_offline` (wired, P61 KW-FULL): the last allowlisted-but-refused type is now real —
  `tools/keyword_offline.py report` walks every committed keyword-library file plus the scoop cache,
  zero network. HONESTY IS STRUCTURAL: the report's `search_volumes` is always null and its
  `data_basis` names the local sources (live volumes are network-only by the seo-keywords spoke's
  design and are never estimated). The builder validates `params.query` (non-empty string, max 500
  chars). Because every schema type now has a builder, the runner selftest exercises the
  not-wired refusal branch (kept for future types) by temporarily popping a key from
  `JOB_BUILDERS` and restoring it.
  `<!-- verify: tools/keyword_offline.py::report -->`

## Known failure modes
- **A schema/allowlist drift** (schema enum edited without `queue.ALLOWED_JOB_TYPES`, or vice
  versa) is caught by the first queue selftest check, which compares the two.
- **A wired builder for an unshipped tool** would produce confusing failures; keep the "not wired
  in this version" refusal for job types whose implementation lands in a later phase.

## Fragile fallbacks that must not become defaults
- The selftest-only `allow=True` gate override. Production callers (watcher, MCP tools) must let
  `run_pass` read the capability itself.

## Regression cases (mapped to the selftests; the tools layer has no evals/evals.json)
1. A `publish` job_type is refused with ZERO subprocesses spawned —
   `python3 tools/handoff/runner.py --selftest` ("all five hostile tickets refused, zero spawns").
2. Duplicate job_id and Drive conflict pairs run exactly once — same selftest ("duplicate job_id
   skipped", "conflict pair runs once").
3. An `input_ref` of `../../etc/passwd` is refused — queue selftest ("escaping input_ref refused")
   and runner hostile-ticket check.
4. The capability gate holds: with `compute_handoff_enabled` off, the queue is not even read —
   runner selftest ("gate off -> gated, queue untouched").
5. A timeout lands as an honest `failed` result naming the budget — runner selftest.
6. The stdlib allowlist mirrors `shared/schemas/compute-job.json` — queue selftest first check.
7. The offline scan never guesses a content category (a PDF lands in `needs_review` with
   `classified_as` null) and never routes without a matching format rule —
   `python3 tools/handoff/inbox.py --selftest` ("pdf is never guessed") and scenario S10.
8. Approval refuses a file whose content changed since its scan (sha256 re-verify) and an
   unchanged Inbox re-scan proposes nothing — inbox selftest ("changed-since-scan refused",
   "idempotent re-scan"), mirrored in `skills/atoms/inbox-routing/evals/evals.json` case 3.

## Approval-gated changes
Adding or removing a job type (schema enum + `JOB_BUILDERS` + this doc together); widening the
finance/competitor builders beyond read-only; changing the confinement rule; changing the gate
default; letting any transport bypass `run_pass`.

## Contributor gotchas
- `runner.py` inserts `tools/` on `sys.path` before importing the package, so it runs directly
  (`python3 tools/handoff/runner.py`) as well as via `PYTHONPATH=tools`.
- Result files are keyed by job_id, EXCEPT unparseable tickets, which are keyed by the ticket
  filename stem (there is no trustworthy id inside a file that does not parse).

## Update checklist
Change code here -> update this doc and `docs/DRIVE-HUB.md` in the same commit -> run the two
selftests -> `python3 tools/sync_check.py` must exit 0.
