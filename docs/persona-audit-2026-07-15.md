# Persona audit -- 2026-07-15 (first run)

> **Historical snapshot.** This audit reflects the pre-P51 state. The structural stumbles it triaged
> to the maintainer -- notably #8 (YouTube publishing dead end), #9 (Instagram/TikTok/Pinterest setup),
> and #10 (folder picker) -- were remediated in P51 (real publishing OAuth + live upload, gated) and
> P50/P51 (the native folder picker). See `STATE.md` and `docs/PUBLISHING.md`. The body below is left
> as-written as a point-in-time record; do not read its "not built / stub" language as current.

Persona: **Alex**, a non-technical YouTube creator. Protocol: `docs/PERSONA-AUDIT.md`. Harness:
`tools/persona_audit.py` (23 screens after P50, all green, 0 orphans, 0 token leaks).

This is the inaugural audit. It records the twelve stumbles the read-through surfaced, split into the
low-risk ones fixed in this pass and the structural ones triaged to the maintainer (fixing them is a
product decision beyond a cosmetic pass, per the audit's own rule).

## Fixed in this pass (low-risk, in-scope)

| # | Stumble | Category | Fix |
|---|---|---|---|
| 1 | `/freshness-setup` was reachable only by typing the URL | orphan | Added a link from the welcome screen (`_screen_welcome`); the harness now confirms 0 orphans. |
| 2 | "uv" and "Node.js" shown on the Desktop screen with no explanation | jargon | Added a plain-language gloss ("free helper programs ... the wizard handles them; a checkmark means you are ready") and softened the status lines (`_screen_desktop`). |
| 3 | The Freshness store dropdown showed internal tokens (`cross_platform -> google_drive`, `on_device -> local_fs`) | leaked token | Humanized both sides ("More than one AI -> saved in your Google Drive", "This computer only -> saved on this computer"); the harness confirms no store token in visible text (`_screen_freshness`). |
| 4 | Brand-deals switches were labeled with raw flag identifiers (`contract_management`, `finance_management`, ...) | leaked token | Each switch now leads with a plain name ("Review brand contracts", "Track invoices and money"), with the identifier kept only as a dim secondary hint; buttons say "Turn on <name>" (`_screen_brand_deals`). |

## Triaged to the maintainer (structural; not auto-fixed)

These change product behavior or onboarding architecture, not just wording, so they are logged for a
deliberate decision rather than patched in a cosmetic pass:

| # | Stumble | Category | Why it is deferred |
|---|---|---|---|
| 5 | The wizard itself must be launched from a terminal (`python3 tools/wizard.py`) | required-install-no-fallback | A double-click launcher / packaged app is a distribution decision. |
| 6 | The welcome screen presents ~9 branches at once (two Claude options + ChatGPT + Gemini + "more than one" + four shortcuts) | decision overload | Reworking the first-screen information architecture needs a design pass. |
| 7 | The Google Cloud OAuth step (create project, enable APIs, configure consent screen, make an OAuth client, copy client id/secret) is the classic abandon point | jargon wall | The only softer path (claude.ai native connector) is on a different branch; unifying them is a flow change. |
| 8 | YouTube publishing is a genuine dead-end: the OAuth authorization callback is a stub, so the flag never turns on | dead-end | Requires building the real OAuth code exchange (a feature, not a fix). |
| 9 | Instagram/TikTok/Pinterest setup assumes developer-console knowledge and multi-day app review | jargon wall | Inherent to the platforms' APIs; needs a "we'll guide you / paste later" redesign. |
| 10 | The Import screen front-loads raw shell commands (`python3 tools/import_parse.py`, ...) | jargon | A guided file-picker UI is a larger build; a plain-language fallback already exists alongside the commands. |
| 11 | Node.js-missing and Homebrew-missing paths point at `docs/SETUP_MAC.md` with no in-wizard recovery | required-install-no-fallback | An in-wizard installer/recovery is a bigger UX build. |
| 12 | Picking "Gemini" lands on the cross-modality screen, which opens with A/B/C capability-class theory | decision overload | Needs a Gemini-specific entry screen. |

## Update -- P50: structural stumbles 5, 6, 7, 10, 11 resolved

The maintainer took five of the triaged structural stumbles and built them out (the remaining ones --
8 YouTube OAuth, 9 platform developer-console walls, 12 Gemini entry -- are separate features):

| # | Stumble | What shipped |
|---|---|---|
| 5 | wizard needs a terminal | Double-click launchers at repo root (`Start Creator OS Setup.command` with the executable bit + Gatekeeper note; `Start Creator OS Setup.bat` with the SmartScreen note), plus a `launch_setup` MCP tool so a user talking to Claude Desktop/Code can open the wizard by asking. |
| 6 | ~9 first-screen branches | `_screen_welcome` collapsed to one primary question (Claude / ChatGPT / more-than-one); the two Claude buttons fold into a single `/claude` chooser; task shortcuts moved to their own "jump to a task" section; new "Bring what you already have" hub (`/bring`). |
| 7 | Google Cloud OAuth wall | `_screen_google` now leads with the zero-config built-in Google connector and demotes the Cloud Console client-ID/secret flow to an advanced expander. New storage folder-permission step (`/storage-folder`) registers a filesystem connector scoped to one chosen folder. |
| 10 | import screen front-loads shell commands | `_screen_import` reworked into "just ask Claude" + a guided form (platform checkboxes, folder path, Scan -> preview -> Approve via `/api/run-import`); raw commands demoted to an "Advanced" expander. |
| 11 | Node/Homebrew-missing point at a doc with no in-wizard recovery | Default dependency installer (`tools/setup.py --install-deps` + the wizard "Set up my computer" screen) installs every free pip set + uv + Playwright's browser and reports each outcome; `_screen_node_missing` folds recovery inline with an "I've installed it -- re-check" button. |

The four undeclared pip deps were declared and the `configure-stats-tool` atom was reconciled to the
canonical registry (see `docs/DEPENDENCIES.md`) so the default installer is correct and honest.

## Harness result

```
$ python3 tools/persona_audit.py --selftest
  [ok] every screen renders without error
  [ok] every screen has a heading
  [ok] every screen offers a next action
  [ok] no orphan routes
  [ok] no store token leaks into visible text
selftest: PASS (5 of 5 checks)
```

No new stumbles beyond the twelve above were surfaced by this run. Re-run the harness and refresh this
log after any wizard change.
