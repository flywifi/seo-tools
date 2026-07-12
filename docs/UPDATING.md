# Updating Creator OS (for an established user)

You already use Creator OS and have your own saved data. This is the plain-language runbook for how a
new version reaches you on each place you use it, and what it never disturbs. Written for a
non-technical user; the exact facts per surface were verified against current vendor documentation
(observed 2026-07-12). Claims that depend on a fast-moving vendor feature are tagged
`[NEEDS VERIFICATION]` and should be re-checked against the linked page.

## The one thing to know first: an update never touches your data
Everything you have saved (your rate card, deals, contracts, saved templates, profile, freshness
notes) lives in local files that are **gitignored**, which means git and any repo update leave them
completely alone. Updating the code can never overwrite, delete, or conflict with your saved values.
See docs/LOCAL_CONTEXT.md. If a newer version changes the shape of a data file, old files keep working
(missing new fields simply read as null and are flagged), and any actual repair is opt-in and
reversible (see "Your data after an update" below).

## Am I on the latest version?
- On a computer: run `python3 tools/update_check.py report` (read-only; it checks the public release
  page and never changes anything), or open the wizard's **Updates** screen (`python3 tools/wizard.py`
  then `/updates`).
- On a pasted/uploaded surface (ChatGPT, claude.ai Projects, Gemini): compare the `Packaging version:`
  line at the top of what you pasted with the version the wizard shows.
- You can opt in to a quiet background check (`background_update_check`, off by default) that tells you
  once, only when you are behind, and never applies anything. It honors the never-nag rule
  (docs/FRESHNESS.md).

---

## Per-surface runbook

### Claude Code (command line)
Two ways, both effectively hands-off once set up:
- **As a plugin (recommended for true background updates).** Creator OS ships a git-backed marketplace
  (`.claude-plugin/marketplace.json`) and a plugin (`.claude-plugin/plugin.json`). Claude Code can
  auto-update installed plugins at the start of a session; a notice then prompts `/reload-plugins` to
  apply mid-session. Official Anthropic marketplaces auto-update by default; **third-party marketplaces
  (like this one) have auto-update OFF by default**, so a personal user turns it on once, or a
  Team/Enterprise admin forces it by setting `"autoUpdate": true` on an `extraKnownMarketplaces` entry
  in managed settings. New SKILL.md text hot-reloads within a session; changes to hooks/`.mcp.json`
  need `/reload-plugins` or a new session.
  (Source: code.claude.com/docs/en/discover-plugins.)
- **As a git clone.** Run `python3 tools/update.py` (git pull + drift guard + cache rebuild; it never
  touches `*.local.json`), or a small pull cron. The CLI itself also auto-updates in the background
  unless `DISABLE_AUTOUPDATER` is set. (Source: code.claude.com/docs/en/setup.)

### Claude Desktop (with a local MCP server)
- The Desktop app auto-updates itself (Team/Enterprise admins can manage this centrally via MDM).
- Your Creator OS **server code is read from disk each time the app launches the server**, so updating
  is: `python3 tools/update.py` (or a pull), then restart the server or the app. Nothing else to do.
- If instead you installed Creator OS as a packaged **Desktop Extension (`.mcpb`)**: extensions from
  Claude's official directory update automatically, but a **privately distributed `.mcpb` does NOT
  auto-update** (you reinstall a new, version-bumped bundle). Note that mid-2026 Desktop builds gated
  managed `.mcpb` behind `isDesktopExtensionEnabled` and removed installing extensions from local
  `.mcpb` files in managed deployments. `[NEEDS VERIFICATION: consumer directory vs enterprise .mcpb
  gating, claude.com/docs/connectors/custom/desktop-extensions]`.

### Claude Cowork
- Cowork runs each session in a **fresh, temporary sandbox** (created at session start, destroyed at
  the end), so a session picks up your current installed plugins automatically. Updating is delivered
  through the plugin/marketplace, not a manual pull.
- For an organization, an owner turns on **"Sync automatically"** (Organization settings > Plugins);
  then "changes take effect on each member's next session or plugin refresh."
- **Important release rule:** Cowork org auto-sync fires **only when a pull request that bumps the
  plugin version is merged to the default branch**. A direct push to the default branch does NOT
  trigger a sync. So a Creator OS release meant for Cowork users must bump `version` (in
  `.claude-plugin/plugin.json` / `versions.json`) in the merged PR. (Source:
  support.claude.com/.../13837433.)
- **Data caveat (this is the trade-off):** the Cowork sandbox is ephemeral. Your `.local` data does
  not persist there, and local (stdio) MCP servers do not run in Cowork at all. Keep stateful data on
  a persistent surface (Claude Desktop / Claude Code) or reach it through a hosted connector; do not
  treat Cowork as your data's home. (Source: support.claude.com/.../14479288.)

### claude.ai in a browser (web and mobile)
- If you use it through a **custom remote MCP connector** you (or your developer) host, updating is the
  best case: update the machine that hosts the endpoint once (a pull + restart), and every connected
  session is current the next time it connects. See "Connected setup" below.
- If you use **pasted instructions or uploaded Project knowledge**, that is a frozen copy: compare the
  `Packaging version:` line to the wizard's version and re-paste / re-upload when it is lower.
- Google Docs added via the Google Workspace connector live-sync from Drive (always the latest), so
  knowledge you keep in a connected Doc updates without a re-upload.

### Connected setup (a hosted remote MCP endpoint, serves claude.ai and ChatGPT)
This is the only way any browser AI gets **true background updates**: the AI calls your live endpoint,
so the behavior and data it serves update the moment you update the endpoint machine. Design and
hosting details, including the important limit that the tool **contract** (the set of tool names) must
stay stable, are in docs/CROSS-MODALITY.md and implementation/gpt/mcp-connector/README.md. You or your
developer host it behind HTTPS with authentication; the repo ships the server code and a runbook, not
a hosted service.

### ChatGPT
ChatGPT has no way to auto-edit a custom GPT's Knowledge or a Project's files (there is no management
API for them; they are web-UI only), so a **pasted/uploaded** copy is frozen and updates only when you
re-paste / re-upload. The frictionless version of that loop: compare the `Packaging version:` line to
your wizard's version, then use the export prompt to regenerate the pack. The **background** version of
ChatGPT is to point a stable **custom GPT Action** or a **developer-mode MCP connector** at your hosted
endpoint, so the data it serves updates server-side with no rebuild. Full per-flavor detail (plain
chat, custom GPT, Projects, desktop app, agent mode) is in docs/TRANSITIONS.md and docs/CROSS-MODALITY.md.

### Gemini
Gems are a frozen paste (re-paste on a version change); a Gemini API backend you control updates when
you update that backend. See docs/CROSS-MODALITY.md.

---

## Your data after an update (schema changes)
Most updates only add code and content and never touch your data shapes. When a data shape does gain a
new version:
1. **Old files keep working by default.** Missing new fields read as null and are flagged; nothing is
   rewritten. This is `tools/migrate_local.py`'s `compat_view` behavior and the reason an update is
   safe to take without doing anything to your files.
2. **See what changed, only if you want to.** `python3 tools/local_audit.py` prints one quiet line when
   a saved file uses an older format; `--details` shows which files and the human-written reason it
   matters to your data (from CHANGELOG.migrations.json). It writes nothing.
3. **Repair is opt-in and reversible.** `python3 tools/migrate_local.py plan <file>` shows exactly what
   would change (a dry run). `apply <file> --yes` fills the missing fields as null, stamps the new
   version, backs the file up first, and can be undone byte-for-byte with `rollback <file>`. It never
   alters an existing value. Backups and the rollback log are gitignored local files.

## Honest ceilings (what "background" cannot do)
- Pasted/uploaded knowledge on ChatGPT, claude.ai Projects, and Gemini Gems can never auto-update: it
  is a snapshot, and the only signal is the `Packaging version:` line you compare yourself.
- Even a hosted connector propagates a changed **tool contract** unreliably mid-session (claude.ai has
  shown a stale cached tool list; ChatGPT needs a manual "Refresh"), which is why Creator OS pushes
  evolving content through a small **stable** tool set. `serverInfo.version` is a poll signal, not a
  push. `[NEEDS VERIFICATION: mid-session list_changed / resources.updated honoring on claude.ai and
  ChatGPT.]`
- There is no update notification for a pure paste-only user who never opens the wizard on a computer.
- The system never pushes, opens a PR, or pulls on your behalf. Every update is something you choose.

## Verify
```bash
python3 tools/update_check.py --selftest     # release-poll compare logic (offline)
python3 tools/local_audit.py --selftest      # read-only schema audit
python3 tools/migrate_local.py --selftest    # consent-gated, reversible migration
python3 tools/update_notify.py --selftest    # consent-gated passive notice
```
