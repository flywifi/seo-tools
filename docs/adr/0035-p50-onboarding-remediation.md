# 35. P50 Onboarding Remediation

- Date: 2026-07-15
- Status: Accepted

## Context

A non-technical creator (Alex) could not start setup without a terminal, faced nine first-screen choices, hit the Google Cloud Console wall, and met raw shell commands to import. These were the highest-friction abandon points; each is now guided, batteries-included, and honest (propose-then-confirm preserved; nothing keyed/paid installed by default; every degrade null-and-flag).

## Decision

Built out five structural persona-audit stumbles into the wizard onboarding. (5) No-terminal launch: double-click Start Creator OS Setup.command (executable bit + Gatekeeper note) and .bat (SmartScreen note) launchers, plus a launch_setup MCP tool. (6) First-screen IA collapsed to one primary AI question with a /claude browser-vs-desktop chooser and a /bring 'bring what you already have' hub. (7) Native-first Google: _screen_google leads with the built-in connector and demotes Google Cloud Console to an advanced expander; a /storage-folder step registers a filesystem MCP scoped to one chosen folder. (10) Guided import: _screen_import reworked into ask-Claude plus a Scan/preview/Approve form (/api/run-import) with raw commands in an expander. (11) Default install: tools/setup.py --install-deps and a wizard 'Set up my computer' screen install every free pip set + uv + Playwright's browser with honest per-package reporting; _screen_node_missing gains inline recovery + a re-check button. Blockers: configure-stats-tool reconciled to the canonical MCP registry; numpy/python-dateutil/sqlite-vec/PyYAML declared and seeded for invariant 23; new docs/DEPENDENCIES.md.

## Consequences

Ledger status at record time: `accepted`. Source: `ledger/ledger.json` id `P50-onboarding-remediation`.
