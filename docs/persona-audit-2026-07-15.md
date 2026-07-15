# Persona audit -- 2026-07-15 (first run)

Persona: **Alex**, a non-technical YouTube creator. Protocol: `docs/PERSONA-AUDIT.md`. Harness:
`tools/persona_audit.py` (19 screens, all green, 0 orphans, 0 token leaks after the fixes below).

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
