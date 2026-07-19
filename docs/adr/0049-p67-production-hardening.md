# 49. P67 Production-readiness hardening (in-repo slices)

- Date: 2026-07-19
- Status: Accepted

## Context

With the P65 audit findings remediated (P66) and the battery green, the question was "what stands
between green-in-sandbox and shippable?" Three parallel read-only agents mapped it. The honest
verdict: no material engineering is half-done; what remains splits into true production gates that
need real hardware/credentials (cutting the GitHub release, live OAuth/publish/Mac/provider/Drive
validation) and in-repo hardening that is fully doable here. The user selected three in-repo
slices and explicitly deferred release-cutting and the version bump.

## Decision

**A. Guard-shallowness backlog (invariants 14/16/17) closed.** The P65 audit designed
false-negative recipes against three agent-contract guards that were substring/marker tests; P66
deferred them to avoid a false-positive storm. P67 rebuilt all three as property checks in
`tools/sync_check.py`, each tuned against the real tree (5 agent defs, 5 workflows) with a
crafted-bad proof:
- **14** (`check_agent_contracts`): the `## Allowed tools` allowlist must parse to at least one
  `- <Tool>` item. A generic allow/forbid disjointness check would be unsound (`Bash` legitimately
  appears in both the Allowed read-only and Forbidden writes sections), so the read-only property
  lives on 17 instead.
- **16** (`check_workflow_verification`): the marker check is retained AND a structural check
  (`_workflow_consumes_agent_output`) requires some `agent()` call to interpolate a value derived
  (to a fixpoint) from an earlier agent/parallel/pipeline result. A marker in a comment with no
  consuming second agent now fails.
- **17** (`check_readonly_mandate`): the mandate substring is retained AND the allowlist is
  cross-checked against the write vocabulary (`Write`/`Edit`/`NotebookEdit`).
Invariant count is unchanged at 56 (existing guards hardened, none added).

**B. Remote MCP endpoint auth (fail-safe, default-secure).** `tools/mcp_server.py --serve-remote`
bound plainly and trusted the reverse proxy for auth. It now adds two in-process backstops behind
that proxy: it refuses to bind a non-loopback `--host` with no `CREATOR_OS_MCP_TOKEN` (or
`remote_mcp_token` in the gitignored local config) and no `--insecure`, and enforces an in-process
bearer gate (constant-time, 401) when a token is set. A loopback bind behind the proxy is
unchanged. Coverage is a package-independent selftest (serve decision + ASGI bearer gate), since
the `mcp` package is not installed in the sandbox.

**C. Doc + honesty truth-up.** The `live_publishing_disabled` degraded-behavior prose called the
`tools/publishing/` clients "stubs"; they are complete OAuth + upload REST clients gated off, now
stated correctly. `docs/ROADMAP.md` inventories the genuine `NotImplementedError` stubs (DaVinci
Resolve, Compressor, CommandPost, the `remote_mcp` store backend) and the CEA-608 `.scc` deferral,
with verify markers, so unbuilt paths are documented rather than silent. The TikTok rate-limit
`[NEEDS VERIFICATION]` was resolved to the documented 600 requests/minute per endpoint (one-minute
sliding window), no total-video cap, verified against developers.tiktok.com; the remaining
`[NEEDS VERIFICATION]` markers are genuinely plan-gated vendor claims that stay flagged.

**D. Eval testing model.** CI only `json.loads`-ed each `evals/evals.json`, so a well-formed file
with hollow scaffold cases passed. `tools/eval_lint.py` (offline structural linter, CI-wired,
discovered by `selftest_sweep`) replaced that step: every case needs a unique id and either a
non-empty input or a concrete expectation, so a no-input refusal case is valid while an empty
scaffold fails. It surfaced 27 hollow scaffold cases across 9 skills (the P30/P35 task and finance
atoms plus task-desk); all were authored into real, fabrication-aware eval cases. Behavioral eval
execution (which needs model calls) is documented as an intentional opt-in maintainer step, not a
push gate, so the absence is recorded rather than silent.

## Consequences

The three agent-contract guards now verify their property, not a token. The remote endpoint cannot
silently expose an unauthenticated public bind. The docs no longer overstate stubs or understate
built clients. The eval corpus is structurally guarded and no longer hollow. Not done here and
handed off: cutting the GitHub release / 0.2.0 version bump (Tier A1/C1, deferred by the user), and
live-surface validation of OAuth/publishing/Mac/provider/Drive paths (needs real hardware and
credentials). No launch flags were flipped; no git tag was cut.
