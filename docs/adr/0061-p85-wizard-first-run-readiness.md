# ADR 0061 — Wizard first-run readiness: verified completion, resume, and the server it forgot

- Status: accepted
- Date: 2026-09-19
- Phase: P85 (setup-wizard readiness pass)

## Context

Ahead of the next real install, `tools/wizard.py` turned out never to have written the
`creator-os` MCP server entry into Claude Desktop's config — the flagship integration existed
only as a manual snippet with a placeholder path, while two docs claimed the wizard handled it.
Executing the documented smoke test also proved it broken (a bare `tools/list` is rejected
before the MCP `initialize` handshake). As reference material, the onboarding design of the
OpenClaw project was studied from its public documentation (docs.openclaw.ai, First steps
section, read 2026-09-19). **No OpenClaw software, dependency, component, or setup step was
adopted, installed, or shipped; only design patterns were compared.**

## Decisions

1. **Verified completion is the gate.** The wizard's install step is not "done" when the config
   file is written; it is done when a real MCP handshake plus tool listing answers from the
   exact interpreter the config names, with the tool count compared against `count_truth.py`
   output at probe time (never a hardcoded number). The Done page derives its Creator OS line
   from the probe result at render time and offers a re-probe ("Check again") for after the
   Claude Desktop restart. Pattern source: OpenClaw's "continuing remains locked until one
   backend has passed"; implementation entirely local.
2. **No silent fallbacks.** A failed verification shows the reason (stderr tail), a Retry, and
   the manual-merge fallback; a missing MCP SDK routes to the free-tools install with the plain
   reason. Skipping a first-run step is its own labelled button, never an implicit branch.
3. **Resume over restart.** Setup progress persists to a gitignored `.local.json` flag file
   written through the atomic writer; relaunch shows a resume banner; only the explicit "Start
   over" clears it. Re-running the wizard never wipes anything.
4. **Progress is shown, not implied.** The two >60-second steps run in a worker thread behind a
   self-refreshing wait page with guaranteed terminal states (a crashed worker stores its
   error). The per-package honest reporting is unchanged.
5. **Deliberately NOT adopted** from the reference design: daemon/service installation,
   telemetry consent steps, multi-provider pickers, channel pairing, and localized copy.
   Creator OS installs exactly one server, runs no background service from the wizard, collects
   nothing, and ships English copy; adding those surfaces would be scope without a user.
6. The double-click launcher was audited and left untouched: its interpreter probing (including
   the dead-venv trap handled in P73), Homebrew PATH handling, and Gatekeeper wording already
   meet the bar. A Python-floor guard was added to `main()` instead, because the docs also
   invite `python3 tools/wizard.py` directly, bypassing the launcher.

## Consequences

- A first-run user who finishes the wizard has working Creator OS tools in Claude Desktop or an
  explicit, actionable statement of why not — never a silent gap.
- The selftest locks the new surface: a 31-screen render sweep, the config merge round-trip
  (other servers survive; corrupt configs are backed up), state persistence, and worker
  semantics all run on every battery pass.
- The setup docs now describe reality; the broken smoke test is replaced with the working
  three-message probe.

```sources
[
  {"id": "openclaw-onboarding-docs", "url": "https://docs.openclaw.ai/start/wizard"}
]
```
