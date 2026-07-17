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
`needs_review` with `classified_as: null` — this tool never pretends to have read a document, and
the injection guard runs only in a Claude session (the atom). `approve` is the ONLY writer: it
re-verifies each sha256 (a file changed since its scan is refused), moves approved files to
`Inbox/Processed/<date>/`, and appends to the gitignored ledger
(`pipeline/inbox/inbox-ledger.local.json`) atomically. The `inbox_scan` job type wires the same
scan into the runner (read-only; the proposal lands in the job result for review from any
surface; approval stays on the wizard `/inbox` screen with its single-use batch token).
`<!-- verify: tools/handoff/inbox.py::scan -->`
`<!-- verify: tools/handoff/inbox.py::approve -->`

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
