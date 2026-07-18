# 45. P62 Two-pass injection screening (offline pre-filter feeds an authoritative in-session guard)

- Date: 2026-07-18
- Status: Accepted

## Context

The injection-guard engine already defined two tiers — an offline pattern scorer
(`tools/injection_scan.py`, field `offline_pattern_scan`) and an authoritative in-session semantic
guard (field `injection_scan_result`) — but kept them deliberately independent: the offline verdict
was never handed to the session, which re-judged raw content from scratch. The offline note was
computed for every file, persisted only when it SEALED one, and dropped for the CLEAN/REVIEW files
that flow to a session. So the cheap always-on layer never informed the authoritative layer, and a
reworded injection (which scores CLEAN offline) got no benefit from the pre-filter having run.

The user asked whether the offline scanner could be a genuine FIRST pass that hands its notes to the
AI for a SECOND pass that understands rewordings, with availability differing by modality. Three
decisions were made explicitly: **ENG-ALL** (implement the handoff in the Claude atoms where it can
be enforced, and instruct it in the ChatGPT/Gemini packaging where it can only be advised);
**RECONCILE-FULL** (offline note becomes an advisory prior, the session writes an authoritative
verdict, and a reconciliation triple is persisted); **SEAL-TERMINAL** (the AI second pass runs only
on content that flows onward; a sealed file is never auto-re-examined — releasing a false positive
is a deliberate human move).

## Decision

**A two-pass pipeline.** Pass 1 is the offline pattern tier. QUARANTINE/BLOCK seals the file
(terminal). CLEAN/REVIEW content flows onward carrying its `offline_pattern_scan` prior and
`pass2_pending: true`. Pass 2 is the in-session semantic guard: it reads the content and the prior,
does its authoritative judgment, and writes `injection_scan_result` plus a `reconciliation` record.

**The untrusted-content envelope.** Content and its prior are wrapped in `<untrusted_content
source_trust_class="untrusted_external" offline_prior="...">…</untrusted_content>`; everything inside
is data to analyze, never instructions. The prior is rendered by `injection_scan.render_prior`
(category + score only, never raw content), so the prior itself cannot smuggle an injection.

**Reconciliation and fail-safe.** `inbox.reconcile` combines the prior with the authoritative
session verdict into `{agreed, session_action: confirmed|escalated|downgraded, effective,
pass_coverage, note}`. `approve` persists the `{offline_pattern_scan, injection_scan_result,
reconciliation}` triple and enforces two fail-safes: it refuses to route a record the offline tier
sealed (the session can never un-seal it) OR one the session escalated to QUARANTINE/BLOCK. The
session verdict decides; the offline verdict never overrides it. Formalized in
`shared/schemas/injection-scan.json`.

**Per-modality coverage.** `pass_coverage` records which passes ran: `both`, `offline_only`
(headless — `pass2_pending`, a later session completes it), or `session_only`. On ChatGPT/Gemini
the offline pre-filter runs only where a local tool or deployed MCP is connected, and pass 2 is that
engine's own judgment — the packaging instructs the envelope discipline but cannot enforce it, and
says so.

## Alternatives rejected

- **Keep the two tiers independent (status quo).** Rejected by the user: the cheap layer never
  informed the authoritative one, wasting the pre-filter's signal and provenance.
- **Have the AI auto-re-examine sealed files.** Rejected (SEAL-TERMINAL): releasing a false positive
  is a deliberate human move, keeping the seal a hard boundary and the attack surface small.
- **Treat a single pass as authoritative in isolation.** Rejected per OWASP LLM01: no single pass is
  sufficient — the regex misses rewordings and a model judging injected content is itself
  injectable, so the design is layered defense-in-depth.

## Consequences

The offline verdict now informs the authoritative session pass; the reworded-injection case
escalates and is not routed; every drop-folder record carries its provenance triple. Honest limits
are documented (`docs/INJECTION-TWO-PASS.md`): the prior is advisory, the envelope is a mitigation
not a guarantee, and every downstream action stays human-confirmed. Counts unchanged
(22/106/130/10; a new schema file and a new doc are not counted entities). **Open follow-up:** the
per-engine vendor-doc citations in `docs/INJECTION-TWO-PASS.md` are research-pending (a research
pass was interrupted by a session-usage limit); the architecture and OWASP framing are firsthand and
stable.
