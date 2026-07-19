# 48. P66 Remediation of the P65 full-system audit findings

- Date: 2026-07-19
- Status: Accepted

## Context

The P65 full-system audit — the first run under `docs/AUDIT-PROTOCOL.md` — confirmed fifteen
findings. None was a live wrong-output bug a user would hit today, and publishing/CRM/privacy
safety held; but three were HIGH because the underlying accident (committing a real credential
or a financial spreadsheet) is realistic and the guard that exists to prevent it failed open:

1. **F-SKPROJ-21.** The `generic_sk_key` pattern (`sk-` + alnum-only body) missed every current
   provider key format — modern key bodies are base64url with hyphens and underscores — so the
   very keys issued today sailed through the content scan.
2. **F-SUFFIX-21.** The tracked-content scan only read files whose suffix was on a text
   allowlist; a credential in `secrets.conf` or an extensionless `credentials` file was
   invisible to BOTH the content scan and the suffix blocklist.
3. **F-XLSM-20.** The forbidden-suffix list held seven entries; a macro spreadsheet
   (`budget.xlsm`), a password-manager database, a contacts export, or a mailbox committed
   clean.

The remaining twelve findings shared one root cause the audit named the RC5/RC6 class: guards
verified the PRESENCE of tokens, not the PROPERTY they protect — the keystone invariant could
not see a labeled-but-unregistered check, the residual-origin claim was a prose substring test,
CI ran three of ~60 behavioral selftests, nine selftest summaries printed hardcoded
denominators (four already wrong), the fabrication detector gated nothing, the registry's
"sanctioned-writer-only" rule was conventional for content edits, sixteen CLIs raw-tracebacked
on a >255-byte path, and the "sanitized" competitor export never actually sanitized.

## Decision

Fix every finding under three defaults the user approved:

1. **Security first.** The three HIGH gaps plus the invariant-36 keystone shipped in the first
   commit. The scanner broadened the `sk-` body to `[A-Za-z0-9_-]`, added fine-grained
   `github_pat_` tokens, and replaced the suffix gate with a binary sniff (NUL-byte test) so
   every tracked text file is content-scanned; a full-repo false-positive pass came back clean.
   The forbidden suffixes became ONE shared tiered list, `FORBIDDEN_DATA_SUFFIXES` in
   `tools/secret_scan.py` (~145 entries: spreadsheets, delimited/columnar exports, financial
   application files, credential/key stores, databases, backups, email/PIM/contacts, disk
   images, archives, office binaries, GPS-bearing capture media), imported by invariant 20, the
   staged pre-commit gate, and CI so the lists cannot drift. Web graphics and text formats stay
   allowed: the census proved only text and SVG are committed, so the blocklist costs nothing
   and the pipeline allowlist remains the deliberate escape hatch. Privacy invariants 19/20/21
   print a loud DID-NOT-RUN advisory in a non-git copy instead of silently passing.
2. **Instances plus targeted assertions for the guards.** Every VERIFIED instance was fixed and
   the two highest-value property assertions added: invariant 36 now fails on a
   labeled-but-unregistered check (the exact repro that could silently disable the top
   invariant), and invariant 54 gained Layer 3 (the sixteen audited CLIs keep a thin `main()`
   that try-wraps `_main()` with an OSError handler) plus a wider fs-call set. Invariant 55's
   residual escape became an explicit `_residual_origins` list plus a per-origin
   surface-affinity table (the phantom-origin repro now fails; a new origin requires a
   deliberate mapping edit). Invariant 15 asserts every agent definition's PROSE names the
   verification envelope its schema requires. The designed-but-unverified substring recipes
   against invariants 14/16/17 are a documented backlog in `docs/DOC-MAINTENANCE.md` with
   drafted property-level fixes — deep-rebuilding all three at once risks a false-positive
   storm for gaps nothing reaches by accident today.
3. **Broaden-plus-sniff for the scanner, no entropy tier.** Entropy scoring adds tuning risk;
   the broadened patterns, the placeholder allowlist, and the DEV-TRAP fixture convention
   closed every verified bypass.

Structural additions beyond the findings' minimum: NEW advisory invariant 56 (count 55 to 56) —
`registry_io.save_registry` stamps a `_content_digest` over `sources[]` and the guard
recomputes it, so the audit's hand-edit repro (changing an existing entry's content in place)
now surfaces; the invariant-42 writer census became AST-level so prose or a read-only import
cannot false-positive it. CI gained the behavioral battery: `tools/selftest_sweep.py` discovers
every CLI selftest by scripted grep (argparse flag, argv probe, subcommand, `-m` package
entries) so the list can never rot, and the guard job runs it with `scenario_check`,
`count_truth`, and `doc_freshness --check`. Every selftest summary in the tree derives its
count from a run counter (four literals were already wrong: build_calc 24 vs 29 ran,
publishing_compliance 20 vs 15, mediaprobe 17 vs 19, scenario_check 13 vs 14).
`validate_agent_output` gained a selftest (auto-CI-gated by the sweep) and a loud degraded mode
for a missing authority allowlist. The competitor export now EARNS its "sanitized" claim: every
free-text field parsed from competitor HTML is screened by the offline injection scanner and
the secret/PII scanner before it may enter the committed summary — QUARANTINE/BLOCK or PII
matches are nulled and flagged (null-and-flag), REVIEW-level matches are flagged for the
session tier per the two-pass model.

## Alternatives considered

- **A gitleaks-style entropy scanner.** Rejected this phase: high tuning cost against a tree of
  synthetic fixtures; the regex+sniff+allowlist combination closed all three verified bypasses.
- **A dedicated surface per origin (for invariant 55).** Rejected: origin-to-surface is
  many-to-one by design in both directions (desktop and mac serve both local Claude apps; one
  cowork origin serves both Cowork modes); the affinity table encodes the true model instead.
- **Immediate property-level rebuilds of invariants 14/16/17.** Deferred with drafted fixes;
  the backlog section in `docs/DOC-MAINTENANCE.md` is the tracking record.
- **Blocking only `.xlsm`.** Rejected: the audit proved the CLASS (arbitrary sensitive formats
  commit clean), so the fix is the class-wide tiered list, not the instance.

## Consequences

Every P65 repro now fails against the tree: the three modern-key/unlisted-suffix probes exit
non-zero, eight tier-representative force-adds fail invariant 20 (PNG/MD controls stay clean),
the keystone top-drop fails naming the dropped check, all sixteen oversize-path probes return
the clean envelope, the phantom-origin and registry hand-edit repros trip their checks, and a
planted failing selftest reddens the CI sweep. The invariant count is 56 (one new advisory);
scenarios hold at 10, surfaces at 11, agent roles at 5. The known residual risk is documented,
not silent: the invariant 14/16/17 substring recipes (backlog), and the live-surface legs the
audit listed under its not-exercised section (real macOS/Gatekeeper, live provider surfaces,
live OAuth/publishing) remain hands-on items outside this remediation's scope.
