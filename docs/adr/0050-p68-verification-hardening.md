# 50. P68 Verification hardening (why nine defects survived the audits)

- Date: 2026-07-20
- Status: Accepted

## Context

An adversarial audit of the P67 commits found nine defects — most seriously, eval cases whose
`expected_output_keys` were authored from SKILL.md prose and did not exist in any tool code
(`coverage_summary` for `summary`, `billable_milestones` for `ready_to_bill`, `nudge_date` for
`nudge_at`, and five more; eight keys appear in zero `.py` files). They survived a P65 full-system
audit, a P66 remediation, a green battery, and a structural eval linter built in the same slice.
The failure is not the nine defects; it is that the verification apparatus was blind to five
classes of mistake. Root causes: (RC-1) prose was treated as the source of truth for
machine-checkable data; (RC-2) self-review re-confirmed the author's mental model instead of
checking code; (RC-3) tests exercised the function written, not the entry surface a user hits
(the remote-MCP fail-safe was gated on `--serve-remote` but `--transport streamable-http` reached
the same bind); (RC-4) "battery green" was read as "correct" for properties the battery cannot see;
(RC-5) "cannot test here" was laundered into "verified."

## Decision

Convert each root cause from a discipline into a build check, and require every new guard to be
proven against the defect it targets, in four slices on `claude/repo-access-confirm-wxe50a`:

- **A (RC-1/RC-4).** New `tools/eval_key_manifest.json` names each skill's emitter function(s);
  new drift invariant 57 (`check_eval_output_keys`) AST-extracts the literal dict keys those
  functions emit and enforces (a) every eval case key is in the skill's authoritative set and
  (b) that set is itself a subset of the emitted code keys — so the manifest cannot invent keys
  either. Skills with no deterministic emitter mark each case `spec_only`. The nine eval files are
  corrected to the real keys.
- **B (RC-3).** The remote-MCP auth decision now fires for any non-stdio transport
  (`_auth_gate_fires`), not only `--serve-remote`; the token-gated path serves the transport-matched
  app. An argv-level selftest exercises the wiring.
- **C (RC-2/RC-5).** `docs/AUDIT-PROTOCOL.md` §7 requires an independent, fresh-context close-out
  pass that checks claims against code, plus a red-team proof per guard. ADR 0049-B's coverage
  claim is narrowed to what actually runs.
- **D.** The P67-A guard property checks (inv 14/16/17) are hardened against the false-positive and
  false-negative cases the audit found; missing eval fixtures are created; a doc-cited external
  authority (TikTok rate limit) is registered so invariant 52 tracks it.

## Consequences

A prose-invented eval key is now a build failure, and so is a manifest that claims a key no emitter
emits. The remote endpoint cannot be bound unauthenticated on any transport. The close-out protocol
now demands the independent-code-check step that the P67 self-review skipped.

Verified: invariant 57 was run against the pre-fix tree and flagged all eight invented keys (39
findings) before the corrections; the manifest-subset-of-code layer was shown to reject a
deliberately-mistyped authoritative key; the MCP argv selftest was shown to fail on the reintroduced
`serve_remote`-only wiring; the inv 14/16/17 changes were red-teamed against crafted bad inputs and
confirmed to still pass the 5 real agent defs and 5 real workflows. Full battery green after each
slice (drift clean at 57 invariants, scenarios 10/10, sweep 66/66, eval_lint 129 clean,
doc_freshness current).

NOT done: no version bump, tag, or launch-flag flip (those remain user-owned Tier-A/C decisions).
The remote-MCP gated `uvicorn.run` bind wiring is still not exercised in the sandbox (no
`mcp`/`uvicorn`); only the pure decision, the argv-gate predicate, the app-builder selection, and
the ASGI middleware are covered by the package-independent selftest, and the docs now say so.
