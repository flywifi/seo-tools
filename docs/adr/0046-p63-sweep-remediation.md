# 46. P63 Sweep remediation (four confirmed defects, each locked by a proof that fails on the old code)

- Date: 2026-07-18
- Status: Accepted

## Context

A diagnose-only sweep (2026-07-18) ran every Mac-testable workflow in the Linux sandbox plus four
new cross-skill workflows that carried one dataset across many atoms and tools (brand-deal
lifecycle, back-catalog to distribution, the P62 two-pass injection drop folder, and a
currency/cross-modality chain). 124 checks passed — the P62 two-pass core, STT backend routing,
wizard screens, launcher, and the seal/reconcile machinery are correct — but four real defects
surfaced, none caught by the existing selftests or drift guard because each lived in a seam the
guards never execute:

1. **Connector resolver crash.** The `google_drive_hub` entry (added P60) was the only 1 of 39
   connectors missing `default_flag`; `resolve()` and `cmd_list()` indexed the key unconditionally,
   so `connectors.py --plan/--list/--json` crashed with `KeyError` and the MCP `get_connectors`
   tool returned an error JSON instead of the evidence plan. Invariants 18/23/41 inspect the
   registry statically and never run the resolver.
2. **transcript_normalize under-delivery.** The runner passed `--json --gap-metrics
   --suggest-chapters`, but the transcripts CLI dispatches if/elif — the modes are mutually
   exclusive — so every job result and Outbox artifact carried gap metrics only, silently poorer
   than the documented "segments + silence gaps + suggested chapters". The runner selftest asserted
   only the argv string, never the output.
3. **finance/obligations raw tracebacks.** Both CLI payload loaders did an unguarded
   `Path.read_text` + `json.loads`, so a bad path or inline JSON dumped a Python stack trace across
   ten entry points, violating the repo's own P46 no-traceback posture. Invariant 35 covers only
   the importers and import_parse.
4. **build_invoice crash on plain-English terms.** `terms.get("net_days")` assumed a dict; a
   truthy string like a plain net-30 phrase crashed with AttributeError, though the function's own
   contract is "nulls become gaps".

## Decision

Fix each defect with the minimal pattern-matching change and lock each defect CLASS with a proof
mechanism that fails on the pre-fix code:

- **Connectors:** add `default_flag: not_installed` to `google_drive_hub` (the data rule is
  unambiguous — every `requires_capability` connector defaults to `not_installed`, and the
  capability mapping flips it to available when `drive_api_polling` is enabled); harden the two
  read sites with `.get(..., "not_installed")` so a malformed future entry degrades to off, never
  crashes. **NEW invariant 53** dynamically imports the resolver and runs `resolve({})` over the
  committed registry, fail-closed.
- **Transcripts (decision TRANS-FLAG):** an ADDITIVE `--normalize` mode on
  `shared/docintel/transcripts.py` emits one combined object (segments + silences + chapters;
  per-mode min-gap defaults 5.0/8.0 preserved, an explicit `--min-gap-seconds` applies to both),
  plus the tool's first `--selftest`, which also asserts the single-mode arms are unchanged (the
  footage-analysis atom runs them as separate calls and must keep working). The runner builder
  switches to `--normalize`, and the runner selftest now RUNS the built argv on the committed
  workshop-footage fixture and asserts all three keys in the parsed stdout — the exact assertion
  class whose absence let the defect ship.
- **Finance/obligations (decision GUARD-BOTH):** both payload loaders raise a tagged
  `PayloadError` that a thin `main()` wrapper converts to the repo's `{"error","next_step"}`
  envelope with exit 1 (the video_library `_fail` idiom, kept per-tool local); `build_invoice`
  gap-flags a non-dict `terms` as `malformed_terms`. **NEW invariant 54** AST-asserts both loader
  guards stay in place (the invariant-35 sibling scoped to exactly these two files), fail-closed.

## Alternatives rejected

- **Combined output when multiple flags are passed** (transcripts): an implicit contract keyed to
  flag count; the explicit `--normalize` flag is self-documenting and trivially testable.
- **Runner merges three subprocess calls:** three process spawns per job plus merge logic living
  outside the tool that owns the output shape.
- **Selftests only, no new invariants:** would leave both defect classes with no build-time lock;
  the P46 invariant-35 precedent shows the AST guard is cheap and effective.

## Consequences

All three connector CLI paths and the MCP `get_connectors` tool return the evidence plan;
`transcript_normalize` Outbox artifacts carry the full documented payload (verified end-to-end:
segments 20 / silences 3 / chapters 3 on the fixture); the finance/obligations CLIs fail cleanly.
Invariant count moves 52 to 54 (the only count change); negative tests confirmed both new
invariants fire on the pre-fix tree. Selftests grew: transcripts 7/7 (new), runner 27/27,
finance 102/102, obligations 16/16. The sweep log (`scratchpad/mac-sweep-2026-07-18.md`, local)
records the full evidence trail; the harness-artifact non-defects it lists were verified correct
and left untouched.
