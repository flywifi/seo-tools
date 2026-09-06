# 44. P61 Two-step work orders, universal ingest screening, and the last unwired job paths

- Date: 2026-07-17
- Status: Accepted

## Context

P60 shipped the Drive hub and its compute hand-off but left seven addressable gaps: the inbox
approval screen promised follow-up work it never ran; the `library_complete` job builder was
incompatible with its own CLI (every queued job of that type failed with an argparse error,
reproduced live); `keyword_offline` was allowlisted but refused with no offline keyword capability
anywhere; the offline inbox scan never read file contents, so the quarantine safety net had never
fired automatically; nothing wrote the documented `Outbox/` area; the `project_docs` Google Docs
lane read a stored access token verbatim and 401ed after about an hour; and the MCP server had no
selftest at all. P61 closed every one of these without a Mac; Mac-dependent behaviors stay on the
ADR 0043 hands-on checklist untouched.

Six decisions were made explicitly by the user during planning and are binding:

- **A-CONFIRM2.** Approval is a TWO-STEP work order: Approve files the batch, then a second
  screen lists the exact follow-up work (tailored when the user asked for something specific)
  with per-item include/exclude and an amendment box; amendments travel as human-review notes,
  never as machine-executed text.
- **SEC-ALL.** Injection-pattern screening runs on ALL ingested documents as a buffer layer
  before action, passing the exact matched phrasing to the user for review.
- **KW-FULL.** `keyword_offline` is a real tool reading all 8 keyword-library files plus the
  scoop cache, honestly labeled library-derived, never live volumes.
- **GATE-QUEUE.** Work approved while the compute switch is OFF queues and waits, and the
  switch's state plus how to change it is shown at multiple points.
- **WRITE-OPTIN.** Jobs are proposal-only by default; direct library saves exist only behind an
  explicit local capability whose wizard toggle requires an acknowledged risk warning, and the
  runner honors it only from the LOCAL setting, never from a ticket flag alone.
- **Q-SEAL.** Quarantined files are MOVED to a sealed `Inbox/Quarantine/<date>/` area that no
  scan re-reads and no route can touch, with the move and the exact findings logged.

## Decision

**The offline pattern tier (`tools/injection_scan.py`).** The injection-guard engine's
machine-scoreable spec implemented verbatim: eight categories with per-match points, the SOCIAL
co-occurrence rule (urgency alone never triggers below a combined score of 5), the
CLEAN/REVIEW/QUARANTINE/BLOCK thresholds, and the engine's own record shape. A selftest asserts
the tool's category set equals the engine's headings, so the rulebook and the program cannot
drift silently. Naming honesty is structural: the offline verdict travels as
`offline_pattern_scan`, never `injection_scan_result` (the session guard's field), and every
surface says "pattern tier only; the full guard in a session stays authoritative."

**The buffer at every unattended surface (SEC-ALL).** Ticket free text (`consent_note`,
`requested_by`, nested string params) is screened in `queue.validate_ticket` and FAILS CLOSED (a
missing scanner refuses free-text tickets, never silently passes). The offline inbox scan reads
text-decodable files (2MB cap, binary sniff, both honestly reported); QUARANTINE/BLOCK verdicts
land in a `quarantined[]` section and `sweep_quarantine` (the second sanctioned Inbox writer
beside `approve`) seals each file into `Inbox/Quarantine/<date>/` with the full findings in the
ledger. Four independent resurrection locks: scan skips the subtree, approve refuses its paths,
`plan_followups` emits no job for it, and no `inbox_rules.json` rule reaches it. Import previews
carry a `pattern_summary`; the wizard renders every matched phrase escaped.

**The two-step work order (A-CONFIRM2 + GATE-QUEUE + WRITE-OPTIN).** `plan_followups` is a pure,
selftested mapping from approved files to proposed jobs (video/audio to `transcribe_media`,
transcripts to the new `transcript_normalize`, unambiguous exports to `import_parse_preview`;
ambiguous export kinds are never guessed). The wizard files the batch, shows the tailored work
list with checkboxes and the amendment box, and a second single-use token queues only the checked
jobs; the amendment text is stored in `consent_note` and the ledger, never parsed into argv
(selftested), and C2's screening guards it at the queue boundary. Switch banners appear on the
work-order and inbox screens. Direct saves live behind `job_store_writes_enabled` (default off,
acknowledged toggle, capabilities 61 to 62); the runner re-reads the LOCAL capability at build
time, so a forged `params.apply` alone is powerless.

**The last unwired paths.** `tools/keyword_offline.py` (KW-FULL): a shape-tolerant flattener over
every keyword-library file plus scoop-cache hits, ranked deterministically, with the structural
honesty envelope (`search_volumes` always null; `data_basis` names the local sources). The
`library_complete` builder now passes `--export-dir` (the shipped positional argv failed argparse
on every run; a selftest runs the built argv so the failure cannot silently recur).
`transcribe_media` writes its SRT under `Jobs/results/`. `project_docs._api_token` reuses the
watcher's proven refresh-and-persist path and degrades to an honest reconnect note on a dead
grant. Report-style done jobs deliver their JSON to `<hub>/Outbox/` (dated create-only names,
both paths listed in `outputs[]`; failed jobs never deliver), and Transport B uploads staged
Outbox artifacts. `tools/mcp_server.py` gained a two-tier `--selftest`: package-independent
checks always run (config deep-merge, both Transport C refusal strings, a line-anchored static
tool count), and with the mcp package installed the full tier asserts live registered count ==
static count. The first-ever live import ran in a sandbox venv (`mcp` resolved to 1.28.1 exactly
as researched): 58 tools live, all checks pass. The `requirements-mcp.txt` pin is unchanged per
the standing F2 deferral.

## Alternatives rejected

- **Auto-queueing follow-up work on approval.** Rejected by the user: the second screen exists so
  the human and the machine agree on the exact work before any compute is committed.
- **Parsing or acting on the amendment text.** Rejected as an instruction channel. The note is
  data by schema (`consent_note`), shown to the human who reviews the work, and additionally
  pattern-screened at validation; it never changes what the computer runs.
- **Flag-in-place quarantine.** Rejected: a flagged trap left in the working folder can be
  re-scanned or re-proposed later. The sealed area is structurally unreachable, and nothing is
  deleted; moving a false positive back out is a deliberate human act.
- **A thin cache wrapper for `keyword_offline`.** Rejected by the user in favor of the full tool:
  seven of the eight library files are dict-shaped and invisible to the cache indexer, so a
  wrapper would have read almost none of the library.

## Consequences

Every allowlisted job type now runs; every unattended ingest surface is screened before action;
the runner selftest covers the not-wired refusal branch by temporarily popping a builder key
(no permanently-unwired vehicle remains). ADR 0043's line that `keyword_offline` "remains an
allowlisted-but-refused job type" is historical and superseded by this ADR. Counts: capabilities
61 to 62 and degraded notes 46 to 47; spokes/atoms/skills/scenarios/MCP tools unchanged at
22/106/130/10/58. The Mac-dependent items (mirror latency, launchd, live Docs conversion,
Transport B against real credentials) remain on the ADR 0043 hands-on checklist.
