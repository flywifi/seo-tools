# 40. P56/P57 Publishing + Wizard Adversarial Audit and Remediation

- Date: 2026-07-16
- Status: Accepted

## Context

The trailing 24 hours shipped the repo's first credentialed, network-touching code (P51 real
publishing OAuth + live upload for four platforms) and a large browser-driven onboarding wizard (P50).
Both passed their own selftests on the way in, but those are the author's own oracles. P56 ran an
independent adversarial audit with sandboxed, zero-network harnesses (kept in the session scratchpad,
never the repo) and confirmed 12 findings. Every finding is behind `live_publishing_enabled=OFF`
(default), so no user was exposed; but several meant the live publish path had never worked end to end
and the loopback wizard had a browser-CSRF / arbitrary-file-read surface.

## Decision

Fix all 12 findings (P57), each with a harness that flips from CONFIRMED to KILLED and the green
baseline preserved. Make the safety properties **structural** rather than caller conventions:

- **Publish path.** `dispatch()` now enforces the live-publishing flag and an explicit human
  confirmation itself (F2/F8), so a mis-wired or alternate caller cannot reach the network; the
  dashboard passes the full `{platform: {...}}` credentials map (F1); a `persist` callback is threaded
  so a rotated TikTok refresh token is saved (F3); the scheduler dispatches only a `direct_api`-tier
  platform (F7); add-to-queue strips caller-supplied control fields so an injected `status='scheduled'`
  cannot masquerade as human confirmation (F8).
- **OAuth.** Pinterest/Instagram redirect host `localhost` -> `127.0.0.1` (F9): the wizard binds
  `127.0.0.1` only, and `localhost` can resolve to IPv6 `::1` and lose the callback.
- **Wizard.** `_confined_folder()` confines the import scan and the filesystem-MCP folder to the user's
  home tree via a symlink-resolved containment test (F4/F6, was `os.path.isdir` only); a shared
  `_origin_allowed()` guard rejects any mutating POST whose Origin/Referer is not the loopback origin
  (F5); `_valid_git_ref()` + HTML escaping close the `nightly_branch` XSS and git argument-injection
  (F10/F11, the value feeds `git pull origin <branch>`).
- **Test gap.** Added the missing `publishing_compliance --selftest` (F12).

The LOW hardening cluster (over-broad reauth classification, Instagram dead-token classification,
zero-byte chunk guards, YouTube resumable-PUT host pinning, single-thread DoS, etc.) is
drafted-not-applied. Three audit surfaces not reached under a session limit (launch/install, the P52
drift guards audited as oracles, a fresh P55 regression pass) are deferred.

## Consequences

The live publish path is correct and defended in depth, but publishing stays **OFF by default** — these
fixes do not enable it. The wizard can no longer be driven by a visited website or pointed at arbitrary
files. Doc-truth was reconciled in the same change (the PUBLISHING.md redirect/refresh claims, the
`__init__.py` gate docstring, the storage-folder copy). No behavior change to any other feature.

**Verified by:**
- Audit harnesses flip: dispatch_shape / gate_both_ways / wizard_pathconf / wizard_robustness /
  tiktok_rotation all read NOT-reproduced (KILLED)
- New/updated selftests: `python3 -m publishing --selftest` (dispatch gate), `oauth_flow` (127.0.0.1
  redirect assertions), `wizard` (Origin guard + git-ref validation), `publishing_compliance` (20/20),
  the four publishing clients (0 network)
- Green baseline preserved: `sync_check.py` clean @ 52 invariants; `scenario_check.py` 9/9;
  `secret_scan --staged` clean each commit

Ledger status at record time: `shipped`. Source: `ledger/ledger.json` id
`P56-P57-publishing-wizard-audit`.
