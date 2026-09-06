# 41. P58 Audit-Hardening (LOW cluster + coverage gap)

- Date: 2026-07-16
- Status: Accepted

## Context

The P56 adversarial audit confirmed 12 findings; P57 fixed everything exploitable (ADR 0040) and left
two things open: a LOW hardening cluster (drafted-not-applied in the audit findings log) and a coverage
hole — three surfaces the P56 research agents never mapped when they hit a session limit. None of the
LOW items is exploitable today (the publishing ones are all behind `live_publishing_enabled=OFF`), but
they are real robustness/honesty gaps in credentialed network code, and "the three surfaces are clean"
was assumed rather than proven.

## Decision

Close the LOW cluster with a test each, and map + adversarially verify the three surfaces.

**OAuth (A1):** `import urllib.error` made explicit (was transitive); `refresh()` maps a transient 400
to a retryable `OAuthError` while only `401`/terminal codes force `ReauthRequired`; a dead Instagram
long-lived token raises `ReauthRequired` so `instagram.publish` returns a clean `auth_required`.

**Publishing clients (A2):** reject a 0-byte media file before any network init (no INIT POST / no
malformed `bytes 0--1/0`); pin the YouTube resumable-PUT session URL to a `googleapis.com` host so a
spoofed init `Location` cannot exfiltrate the upload token; Instagram requires a real `ig_user_id` and
no longer falls back to `account_id` (the linked Facebook Page id).

**Honesty (A3):** `ftc_disclosure_verified` is documented at the source, in the schema, and in the gate
copy as a presence check (text supplied/prepended), not a content validation. The key is kept for
schema/MCP back-compat.

**Wizard (A4):** a bounded, malformed-safe request-body read (`_read_body`, 5 MB cap); a corrupt Claude
Desktop config is backed up to `.corrupt.bak` before any overwrite; the fetch-model tier is allowlisted
before shelling `transcribe.py`; an import batch is tied to a single-use token echoed in the approve
form so two tabs cannot cross-approve each other's scan.

**Deferred (A4d part 2 — ThreadingMixIn):** making the single-threaded wizard multi-threaded would
introduce concurrency on the unlocked config-file read-modify-write paths (`_write_claude_config`,
`_update_config_section`) that P57 F5/F8 just hardened. The finding (one slow scan freezes other tabs)
is MED and not exploitable on a single-user local tool; the regression risk outweighs the UX gain.
Recorded here as a conscious trade, not a silent drop.

**Track B (map + verify the three un-mapped surfaces):** no new findings. The installer runs only on an
explicit `--install-deps` flag and reports per-package results honestly; the P52 drift guards fire on
genuinely bad input (a verify marker to a missing symbol trips inv 49; an unregistered `sources`-block
id trips inv 52) and pass on valid input; P55's `source_sync` + invariant 52 stay green after all the
P57/P58 changes.

## Consequences

The credentialed network code and the browser-driven wizard are hardened against the remaining
robustness/honesty gaps; publishing stays OFF by default (no feature change). The three previously
un-audited surfaces are proven clean rather than assumed. One MED item (wizard threading) is
deliberately deferred with the rationale above.

**Verified by:**
- New/extended selftests: `python3 -m publishing --selftest` (4/4), `oauth_flow` (transient-400 /
  IG dead-token / urllib.error), the four `publishing/*` clients (empty_media, host-pin, IG identity),
  `wizard` (body-bound, config-backup, model-allowlist, batch-token), `publishing_compliance` (20/20)
- Green baseline preserved: `sync_check.py` clean @ 52 invariants; `scenario_check.py` 9/9; the P57
  harnesses still read KILLED; `secret_scan --staged` clean each commit
- Track B probes recorded in `scratchpad/audit/findings.md`

Ledger status at record time: `shipped`. Source: `ledger/ledger.json` id `P58-audit-hardening`.
