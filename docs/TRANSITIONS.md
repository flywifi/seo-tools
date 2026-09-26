# Moving Creator OS between AIs: the transitions guide (P43)

Creator OS runs best where your files live, but you can carry it to any AI surface if you know
what travels, what stops working, and what to re-import. This doc mirrors the machine source of
truth at `shared/cross-modality/transitions.json`; the setup wizard's `/transitions` screen
renders any from/to pair from the same data (run `python3 tools/wizard.py` and pick "I use more
than one"). Since P90 the wizard also carries guided DOING lanes for the two big web surfaces
(`/chatgpt-setup` and `/claudeai-setup`): copy buttons for every paste, a staged upload folder,
and paste-back verification -- the surface rows below note them as the fastest path. Anything tagged `[NEEDS VERIFICATION: ...]` depends on your ChatGPT or Gemini plan
and must be checked against your own account; the repo does not assert it.

## The eleven surfaces

| Surface | What runs there | Flags enforced? |
|---|---|---|
| Claude Desktop (this computer) | everything (Class A, B, C native) | yes |
| Claude Code / command line | everything | yes |
| claude.ai in a browser (web and mobile) | knowledge natively (Project uploads, or the GitHub connector into project knowledge with manual Sync now, support/10167454); plugin skills on paid plans (Customize > Plugins, GitHub-URL marketplaces, support/13837440) and self-contained skill ZIPs on any plan (support/12512180); live tools via a deployed remote MCP connector (Free holds one custom connector, support/11176164) | no (the endpoint's machine enforces) |
| Claude Cowork (local session on this computer) | everything, inside a hypervisor-isolated VM with your Creator OS folder connected (transcription native only if the VM has an STT backend); the existing-desktop path -- since 2026-09-16 chat and Cowork are one Claude (support/16761823), and the Desktop app must be open for local access | yes |
| Claude Cowork (remote ephemeral sandbox) | plugin skills natively; live tools via remote MCP connectors; local files only through folders you explicitly connect; since 2026-09-16 these agentic cloud sessions start from any conversation in the merged Claude, staged rollout from Pro and Max (support/16761823); pre-merge accounts still see the separate beta surface (support/14479288) | no (a fresh sandbox has no local config) |
| ChatGPT web chat (plain chat at chatgpt.com) | knowledge-only (pasted custom instructions + uploaded files); live tools need a developer-mode MCP connector, which is a separate setup and not "plain" chat | no |
| Custom GPT (built in the ChatGPT GPT builder) | knowledge pack + the public jurisdiction Action | no |
| ChatGPT Projects (a Project with files at chatgpt.com) | knowledge pack as Project instructions + files | no |
| ChatGPT desktop app | knowledge paste; live tools via a developer-mode MCP connector to a deployed endpoint | no (the endpoint's machine enforces) |
| Gemini API (developer integration) | function calling through your own backend | only if your backend runs the tools |
| Gemini Gems (consumer) | pure reasoning only | no |

Two facts hold on every non-local surface, and nothing there changes them:
1. **Capability flags are enforced only where Python runs.** On ChatGPT and Gems the flags in
   your local config are, at best, text the model has read.
2. **Your local data does not follow you automatically.** Rate card, deals, contracts, templates,
   and profile live in gitignored local files; read `docs/PASTE-SAFETY.md` before pasting any of
   it into a third-party chat.

Moving TO the strongest surface stays user-scoped (P93): the Claude Desktop app installs
per-user into `~/Applications`, and everything else Creator OS installs stays inside your own
user account -- see `docs/INSTALL-SCOPE.md` and the `claude_desktop` setup steps in
`shared/cross-modality/transitions.json`.

**The merge (2026-09-16):** Claude chat and Cowork are one Claude (support article 16761823,
fetched 2026-09-20). There is no separate mode to pick; Claude routes quick answers and
agentic sessions itself, existing projects, connectors, and skills carry over, and Claude Docs
and Claude Slides launched alongside (beta, paid plans). The rollout is staged from Pro and
Max over the following weeks, so both UIs coexist for a while; the two Cowork rows above are
kept during the transition and describe the local path and the agentic cloud sessions
respectively. Projects themselves remain, on every plan including Free (five-project cap,
automatic RAG for large knowledge; support article 9517075).

One more fact specific to Cowork remote sessions: **the sandbox is ephemeral.** It is destroyed
when the session ends, and nothing written to its local disk survives — including `.local` store
files. Keep durable state in Google Drive or behind a hosted connector, and treat anything the
sandbox produced as an export you save before the session closes (the same
append-new-dated-file model as claude.ai web). A Cowork **local** session runs on your own
computer and behaves like Claude Desktop, including local stores and flag enforcement; plugin
updates for an organization sync only when a version-bump PR merges (see `docs/UPDATING.md`).

Compute-job **origins** (the `origin` field on a queued job, enum in
`tools/handoff/queue.py::ALLOWED_ORIGINS`) map to surfaces many-to-one in both directions by
design: `desktop` and `mac` both belong to the two local Claude apps (Desktop and Code), the one
`cowork` origin serves both Cowork modes, and `other` is a forward-compatibility residual no
surface may claim (declared in `transitions.json` `_residual_origins`). Drift invariant 55
reconciles the enum, the schema, and the surface claims against a per-origin affinity table, so
adding a new origin requires a deliberate mapping edit, never just an enum append.

## The common transitions

Each pair below is authored in the matrix; the wizard renders every other combination by deriving
it from the two surface records.

- **Claude Desktop to ChatGPT web chat:** export the knowledge pack (paste
  `implementation/gpt/web/custom-instructions.md` into ChatGPT settings) and carry data as dated
  export files. Everything computed locally stops: finance math, template assembly, obligation
  dates, the deterministic quality score, flag enforcement. Your computer stays authoritative.
- **Claude Desktop to a Custom GPT** (workspace accounts only; confirmed 2026-09-19 that personal
  plans cannot create new GPTs -- use a ChatGPT Project instead; note OpenAI plans to retire
  Custom GPTs in favor of Plugins, Enterprise on 2026-12-11 with other plans expected to follow,
  so prefer the Project or connector door for new setups): run the export-gpt package
  (instruction + up to 20 knowledge files, each up to 512 MB); optionally add the jurisdiction
  Action. The Action sends what you type to OpenAI and the public endpoint; the local ask-first
  consent step does not apply there. A GPT can use apps OR Actions, not both at once.
- **Claude Desktop to ChatGPT Projects:** reuse the same package as Project instructions +
  files. Limits vary by plan [NEEDS VERIFICATION: check your plan].
- **Claude Desktop to the ChatGPT desktop app:** the strongest ChatGPT surface. Knowledge paste
  works like the web; live tools become possible by deploying the remote MCP endpoint
  (`implementation/gpt/mcp-connector/README.md`) and adding it as a developer-mode connector
  [NEEDS VERIFICATION: plan gating]. The desktop app merged Chat, Work, and Codex into one app in
  July 2026 (the previous app remains available as "ChatGPT Classic"); menu paths may differ
  between the two [NEEDS VERIFICATION: merge details from secondary reporting].
- **ChatGPT (any) back to Claude Desktop:** run the profile-import prompt
  (`implementation/gpt/profile-import/PROMPT.md`) once per ChatGPT context, paste the JSON back
  home, and the profile-import atom proposes `creator-profile.local.json` with per-field
  provenance for you to save by hand. Drop your dated export files into the store folder; the
  local tools union-merge them. Enforcement (flags, consent, deterministic tools) returns.
- **ChatGPT web to the ChatGPT desktop app:** same account, so chats, memory, and custom
  instructions carry over; the desktop app adds the connector option.
- **Anything to Gemini Gems:** export-gem pack only; Gems cannot call tools, so only
  pure-reasoning skills work.

## Bringing your data back (the read-back procedure)

On plain ChatGPT web, Projects, custom GPTs, and Gems, the store is **export-and-you-save**: the
AI gives you a dated file and you keep it in your Drive folder. These surfaces cannot merge
files; if you upload two dated files, treat the newest as the truth there. Real merging happens
on your computer: when the dated files come home, the local tools union-merge them
automatically. Procedure:

1. At the end of a session away from home, ask for a dated export of anything you changed.
2. Save it into your store folder (Drive or local), keeping the date in the filename.
3. At the start of a session away from home, upload the newest dated file so the AI has it.
4. When you are back on your computer, nothing to do: the tools fold the files in on read.

One refinement for claude.ai web and mobile: with the Google Drive connector connected and file
creation enabled, Claude can CREATE the dated export directly in your Drive folder (it still
cannot edit or move files there), so step 2 happens in the chat instead of by hand. That is the
same append-new-dated-file model the union-merge already expects; see `docs/DRIVE-HUB.md` for the
shared hub folder built on it. (Source: the Claude Help Center article "Use Google Workspace
connectors", checked 2026-07-16.)

## Keeping pasted packs fresh (the re-sync procedure)

Every packaging artifact carries a first line reading `Packaging version: <version>`. The wizard
shows the current Creator OS version on its ChatGPT and transitions screens.

- Compare the version line at the top of what you pasted (custom instructions, GPT instruction
  file, Gem instruction) with the wizard's current version.
- If yours is lower: re-export the pack, then re-paste custom instructions, or re-upload the GPT
  or Project knowledge files, or re-paste the Gem instruction.
- There is no automatic push; pasted text never updates itself.

## Updating by ChatGPT surface (which paths auto-update, which do not)

The re-paste loop above applies to frozen copies. Whether you can avoid it depends on how you
connected Creator OS to ChatGPT:

- **Plain chat (pasted custom instructions):** frozen. Re-paste when the packaging version is lower.
- **Custom GPT knowledge files / Project files:** frozen, and there is no API to write them (the GPT
  and Project builders are web-UI only), so re-upload by hand. **But** a custom GPT **Action** whose
  OpenAPI schema points at your live Creator OS endpoint stays current on its own: the data and logic
  it serves update server-side with no builder edit, as long as you keep the Action's schema shape
  stable (changing the schema shape means editing and re-publishing the GPT).
- **Developer-mode MCP connector (ChatGPT web or desktop):** the tools run against your live endpoint,
  so their output updates server-side. If you change the tool list or descriptions, ChatGPT needs a
  manual **Refresh** on the connector. `[NEEDS VERIFICATION: developer-mode availability, plan gating,
  and the read-only vs write split; see developers.openai.com/api/docs/guides/developer-mode.]`
- **Agent mode:** it can browse your public repo, read the version, and assemble an updated pack in
  its own workspace, but it **cannot** write it into your custom GPT or Project (no management API) and
  it does not use custom connectors for actions. Treat it as a helper that prepares the pack; a human
  still pastes or uploads. `[NEEDS VERIFICATION: the "agent mode will not use custom apps" scope;
  help.openai.com is not machine-fetchable.]`

The durable way to skip re-uploads entirely on ChatGPT is the live path (Action or developer-mode
connector) pointed at a hosted endpoint. Read docs/PASTE-SAFETY.md before moving private data into any
ChatGPT surface, and docs/UPDATING.md for the full runbook.

## What never changes, anywhere

Human review before anything outward. No fabrication: a number the surface cannot verify is a
null and a flag, never a guess. End-user deployments never touch GitHub. Assembled contracts are
always drafts for counsel, on every surface. Untrusted content (links, uploads, tool/Action
responses, pastes) is data to analyze, never instructions to follow, on every surface; injection
screening is a two-pass pipeline whose coverage varies by surface (`both` / `offline_only` /
`session_only`), detailed in `docs/INJECTION-TWO-PASS.md`.

## OpenAI deployment matrix (P72, researched 2026-08-15)

One MCP server (`tools/mcp_server.py`) plus thin per-surface artifacts. Facts cite official pages;
help.openai.com figures are excerpt-confidence (the site refuses direct fetches). Cells marked
"not documented" are exactly that; never assume a number OpenAI has not published.

| Door | Who it serves | Artifact | Key facts |
|---|---|---|---|
| ChatGPT custom instructions | daily chat, any tier | `implementation/gpt/web/custom-instructions.md` (full, under 5,000 combined) or `-compact.md` (Free/Go, under 1,500) | caps per help/8096356; per-field vs combined not documented |
| ChatGPT Project | RECOMMENDED personal-plan home | `implementation/gpt/project/` + the 8 shared knowledge files | project-only memory chosen at creation, switchable later for unshared projects; file caps 5 Free / 25 Go-Plus / 40 Edu-Pro-Business-Enterprise, max 10 files per upload; project instructions replace global custom instructions inside the project (help/10169521, read in full 2026-09-19) |
| Custom GPT + Actions | workspace accounts only | `implementation/gpt/actions/` | creation requires Business/Enterprise/Edu (help/8554397, confirmed 2026-09-19); retirement planned in favor of Plugins (Enterprise 2026-12-11, other plans expected to follow); memory does not work in GPTs |
| ChatGPT connector (no dev mode) | chat + deep research | server `search`/`fetch` tools | exact contract per developers.openai.com/api/docs/mcp |
| ChatGPT developer mode | full 60-tool set | `implementation/gpt/mcp-connector/README.md` | Pro/Plus/Biz/Ent/Edu web; Settings, then Security and login; servers at chatgpt.com/plugins (developers.openai.com developer-mode guide, 2026-09-19) |
| ChatGPT desktop | convenience | same as web | Work with Apps is macOS-only and reads a fixed app list; no general file access (help/10119604) |
| Responses API `mcp` tool | maintainer automation | request card in the connector runbook | approval loop maps the human-confirmation invariant; no fee beyond tokens |
| Agents SDK | maintainer pipelines | `HostedMCPTool` card | openai.github.io/openai-agents-python/mcp/ |
| Codex CLI/desktop/IDE | maintainer | `[mcp_servers.creator-os]` in `~/.codex/config.toml` + root `AGENTS.md` | shared config (learn.chatgpt.com/docs/extend/mcp); AGENTS.md 32 KiB budget |
| Plugin directory | public distribution (not us) | none by design | requires verified org; overkill for a single-user install |

```sources
[
  {"id": "claude-cowork-chat-merge", "name": "Claude Cowork and chat are one Claude (help center)",
   "url": "https://support.claude.com/en/articles/16761823-claude-cowork-and-chat-are-one-claude",
   "category": "ai-surface-spec", "tier": "T1"},
  {"id": "claude-projects-overview", "name": "What are projects? (help center)",
   "url": "https://support.claude.com/en/articles/9517075-what-are-projects",
   "category": "ai-surface-spec", "tier": "T1"},
  {"id": "claude-github-projects-integration", "name": "Use the GitHub integration (help center)",
   "url": "https://support.claude.com/en/articles/10167454-use-the-github-integration",
   "category": "ai-surface-spec", "tier": "T1"},
  {"id": "claude-skills-use", "name": "Use skills in Claude (help center)",
   "url": "https://support.claude.com/en/articles/12512180-use-skills-in-claude",
   "category": "ai-surface-spec", "tier": "T1"},
  {"id": "claude-plugins-use", "name": "Use plugins in Claude (help center)",
   "url": "https://support.claude.com/en/articles/13837440-use-plugins-in-claude",
   "category": "ai-surface-spec", "tier": "T1"},
  {"id": "claude-connectors-directory", "name": "Use connectors to extend Claude's capabilities (help center)",
   "url": "https://support.claude.com/en/articles/11176164-use-connectors-to-extend-claude-s-capabilities",
   "category": "ai-surface-spec", "tier": "T1"},
  {"id": "openai-custom-instructions-caps", "name": "ChatGPT custom instructions (help center)",
   "url": "https://help.openai.com/en/articles/8096356-chatgpt-custom-instructions",
   "category": "ai-surface-spec", "tier": "T1"},
  {"id": "openai-projects-help", "name": "Projects in ChatGPT (help center)",
   "url": "https://help.openai.com/en/articles/10169521-projects-in-chatgpt",
   "category": "ai-surface-spec", "tier": "T1"},
  {"id": "openai-gpt-creation-policy", "name": "Creating and editing GPTs (help center)",
   "url": "https://help.openai.com/en/articles/8554397-creating-and-editing-gpts",
   "category": "ai-surface-spec", "tier": "T1"},
  {"id": "openai-migrate-to-responses", "name": "OpenAI: migrate to the Responses API",
   "url": "https://developers.openai.com/api/docs/guides/migrate-to-responses",
   "category": "ai-surface-spec", "tier": "T1"},
  {"id": "openai-work-with-apps", "name": "Work with Apps on macOS (help center)",
   "url": "https://help.openai.com/en/articles/10119604-work-with-apps-on-macos",
   "category": "ai-surface-spec", "tier": "T1"},
  {"id": "openai-connector-contract", "name": "Connect ChatGPT to MCP servers (search/fetch contract)",
   "url": "https://developers.openai.com/api/docs/mcp",
   "category": "ai-surface-spec", "tier": "T1"},
  {"id": "codex-mcp-config", "name": "Codex MCP configuration (config.toml)",
   "url": "https://learn.chatgpt.com/docs/extend/mcp",
   "category": "ai-surface-spec", "tier": "T1"},
  {"id": "openai-chatgpt-developer-mode-help", "name": "Developer mode and MCP apps in ChatGPT (help center)",
   "url": "https://help.openai.com/en/articles/12584461-developer-mode-and-mcp-apps-in-chatgpt",
   "category": "ai-surface-spec", "tier": "T1"}
]
```
