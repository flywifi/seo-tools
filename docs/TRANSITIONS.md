# Moving Creator OS between AIs: the transitions guide (P43)

Creator OS runs best where your files live, but you can carry it to any AI surface if you know
what travels, what stops working, and what to re-import. This doc mirrors the machine source of
truth at `shared/cross-modality/transitions.json`; the setup wizard's `/transitions` screen
renders any from/to pair from the same data (run `python3 tools/wizard.py` and pick "I use more
than one"). Since P90 the wizard also carries guided DOING lanes for the two big web surfaces
(`/chatgpt-setup` and `/claudeai-setup`): copy buttons for every paste, a staged upload folder,
and paste-back verification -- the surface rows below note them as the fastest path. Anything tagged `[NEEDS VERIFICATION: ...]` depends on your ChatGPT or Gemini plan
and must be checked against your own account; the repo does not assert it.

## The nine surfaces

| Surface | What runs there | Flags enforced? |
|---|---|---|
| Claude Desktop (this computer) | everything (Class A, B, C native) | yes |
| Claude Code / command line | everything | yes |
| claude.ai in a browser (web and mobile) | knowledge natively (Project uploads, or the GitHub connector into project knowledge with manual Sync now, support/10167454); plugin skills on paid plans (Customize > Plugins, GitHub-URL marketplaces, support/13837440) and self-contained skill ZIPs on any plan (support/12512180); live tools via a deployed remote MCP connector (Free holds one custom connector, support/11176164) | no (the endpoint's machine enforces) |
| ChatGPT web chat (plain chat at chatgpt.com) | knowledge-only (pasted custom instructions + uploaded files); the Google Drive app can create and update Drive files where the plan, workspace and Google permissions allow it (help.openai.com/en/articles/10929079); live tools need a developer-mode MCP connector, which is a separate setup and not "plain" chat | no |
| ChatGPT Projects (a Project with files at chatgpt.com) | knowledge pack as Project instructions + files | no |
| ChatGPT desktop app | Chat, Work and Codex in one app since July 2026 (help.openai.com/en/articles/20001276); knowledge paste in Chat and Work; Codex runs the repo tools on this computer; live tools in Chat or Work via a developer-mode MCP connector to a deployed endpoint [NEEDS VERIFICATION: developer mode is documented for ChatGPT web] | only inside Codex (the endpoint's machine enforces for a connector) |
| Gemini API (developer integration) | function calling through your own backend | only if your backend runs the tools |
| Gemini web app (gemini.google.com) | pasted instructions, or a Gemini skill on a personal account (support.google.com/gemini/answer/17094296); the hub Doc attached from Drive; Export to Docs saves a new Doc in Drive; live tools via a deployed MCP endpoint connected as a custom app (US personal accounts, support.google.com/gemini/answer/17209137) | no (the endpoint's machine enforces) |
| Gemini desktop app (Mac and Windows) | pasted instructions and uploads; on the Mac, Gemini Spark edits, renames, reorganizes and can permanently delete files in folders you connect (support.google.com/gemini/answer/17208717); no Creator OS tools | no |

Two facts hold on every non-local surface, and nothing there changes them:
1. **Capability flags are enforced only where Python runs.** On ChatGPT and Gemini the flags in
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
Max over the following weeks, so both UIs coexist for a while. Creator OS retired its two Cowork
rows in P102 (ADR 0075): work on this computer runs in Claude Desktop with its trusted folders,
and agentic cloud tasks start from a claude.ai conversation. Projects themselves remain, on every plan including Free (five-project cap,
automatic RAG for large knowledge; support article 9517075).

One more fact about agentic tasks started from claude.ai: **their cloud sandbox is ephemeral.** It
is cleared when the task ends, and nothing written to its local disk survives — including `.local` store
files. Keep durable state in Google Drive or behind a hosted connector, and treat anything the
sandbox produced as an export you save before the task ends (the same append-new-dated-file
model as claude.ai web). Plugin updates for an organization sync only when a version-bump PR merges
(see `docs/UPDATING.md`).

Compute-job **origins** (the `origin` field on a queued job, enum in
`tools/handoff/queue.py::ALLOWED_ORIGINS`) map to surfaces many-to-one in both directions by
design: `desktop`, `mac`, `windows` and `linux` all belong to the two local Claude apps (Desktop
and Code), the last three naming the computer that queued the job by its system, and `other` is a
forward-compatibility residual no surface may claim (declared in `transitions.json`
`_residual_origins`). The `cowork` origin was retired with the Cowork rows: a ticket that still
carries it is refused with the reason in `tools/handoff/queue.py::RETIRED_ORIGINS`. Drift invariant 55
reconciles the enum, the schema, and the surface claims against a per-origin affinity table, so
adding a new origin requires a deliberate mapping edit, never just an enum append.

## The common transitions

Each pair below is authored in the matrix; the wizard renders every other combination by deriving
it from the two surface records.

- **Claude Desktop to ChatGPT web chat:** export the knowledge pack (paste
  `implementation/gpt/web/custom-instructions.md` into ChatGPT settings) and carry data as dated
  export files. Everything computed locally stops: finance math, template assembly, obligation
  dates, the deterministic quality score, flag enforcement. Your computer stays authoritative.
- **Claude Desktop to ChatGPT Projects:** set the Project instructions to
  `implementation/gpt/project/project-instructions.md` and upload the knowledge files from
  `implementation/claude/project/knowledge/` (on Free, the single combined file
  `implementation/claude/project/creator-os-combined.md`, since Free holds 5 files; help article
  10169521). Custom GPTs retire on 2026-12-11 (help article 20001519, which names plugins as
  OpenAI's migration target); Creator OS uses a Project because it holds the instructions and
  knowledge files Creator OS needs.
- **Claude Desktop to the ChatGPT desktop app:** the strongest ChatGPT surface. Knowledge paste
  works like the web; live tools become possible by deploying the remote MCP endpoint
  (`implementation/gpt/mcp-connector/README.md`) and adding it as a developer-mode connector
  [NEEDS VERIFICATION: developer mode is documented for Business, Enterprise and Edu workspaces
  on ChatGPT web, help.openai.com/en/articles/12584461]. The desktop app holds Chat, Work, and
  Codex in one app since July 2026, and the previous app remains available as "ChatGPT Classic"
  (help.openai.com/en/articles/20001276). Cloud Work chats continue across web and desktop, and
  Codex works with local files, so opened on your Creator OS folder it runs the repo tools and
  the flags hold there.
- **Gemini web to the Gemini desktop app:** the same Google account; attach the hub's "About me
  and my voice" Doc to a chat from Drive when a reply should use your voice. The desktop app runs no Creator OS tools. If you use Gemini
  Spark on the Mac, connect only the hub's Inbox folder: Spark changes files by default and can
  permanently delete them. Work comes back to the computer as new dated files in the Inbox.
- **ChatGPT (any) back to Claude Desktop:** run the profile-import prompt
  (`implementation/gpt/profile-import/PROMPT.md`) once per ChatGPT context, paste the JSON back
  home, and the profile-import atom proposes `creator-profile.local.json` with per-field
  provenance for you to save by hand. Drop your dated export files into the store folder; the
  local tools union-merge them. Enforcement (flags, consent, deterministic tools) returns.
- **ChatGPT web to the ChatGPT desktop app:** same account, so chats, memory, and custom
  instructions carry over; the desktop app adds the connector option.
- **Gemini Gems are retired:** Google turns them into skills from November 2026 for personal
  accounts and in 2027 for work and school accounts (support.google.com/gemini/answer/18560919).
  Paste `implementation/gemini/system-instruction.md` into a chat, or save it as a skill on a
  personal account.

## Bringing your data back (the read-back procedure)

On plain ChatGPT web, Projects, and Gemini chats, the store is **export-and-you-save**: the
AI gives you a dated file and you keep it in your Drive folder. These surfaces cannot merge
files; if you upload two dated files, treat the newest as the truth there. Real merging happens
on your computer: when the dated files come home, the local tools union-merge them
automatically. Procedure:

1. At the end of a session away from home, ask for a dated export of anything you changed.
2. Save it into your store folder (Drive or local), keeping the date in the filename.
3. At the start of a session away from home, upload the newest dated file so the AI has it.
4. When you are back on your computer, nothing to do: the tools fold the files in on read.

One refinement for claude.ai web and mobile: with the Google Drive connector connected and file
creation enabled, Claude can CREATE the dated export directly in your Drive folder, so step 2
happens in the chat instead of by hand. The connector can now also share, move and trash files,
with your approval by default, and edit Google Docs live (beta); Creator OS still asks every
surface other than your computer to create new dated files only and never move, edit or trash a
file the computer manages. That is the same append-new-dated-file model the union-merge already
expects; see `docs/DRIVE-HUB.md` for the shared hub folder built on it. (Source: the Claude Help
Center article "Use Google Workspace connectors", checked 2026-10-01.)

## Keeping pasted packs fresh (the re-sync procedure)

The ChatGPT custom instructions carry a first line reading `Packaging version: <version>`, and
the knowledge files and the Gemini system instruction carry a `Data freshness: as of <date>`
line. The wizard shows the current Creator OS version on its ChatGPT and transitions screens.

- Compare the version or date line at the top of what you pasted (custom instructions, Project
  files, the Gemini system instruction) with the wizard's current version.
- If yours is older: re-paste custom instructions, re-upload the Project knowledge files, or
  re-paste the Gemini system instruction.
- There is no automatic push; pasted text never updates itself.

## Updating by ChatGPT surface (which paths auto-update, which do not)

The re-paste loop above applies to frozen copies. Whether you can avoid it depends on how you
connected Creator OS to ChatGPT:

- **Plain chat (pasted custom instructions):** frozen. Re-paste when the packaging version is lower.
- **Project files:** frozen, and there is no API to write them (Projects are set up in the web
  UI only), so re-upload by hand.
- **Developer-mode MCP connector (ChatGPT web or desktop):** the tools run against your live endpoint,
  so their output updates server-side. If you change the tool list or descriptions, ChatGPT needs a
  manual **Refresh** on the connector. `[NEEDS VERIFICATION: developer-mode availability, plan gating,
  and the read-only vs write split; see developers.openai.com/api/docs/guides/developer-mode.]`
- **Agent mode:** it can browse your public repo, read the version, and assemble an updated pack in
  its own workspace, but it **cannot** write it into your Project (no management API) and
  it does not use custom connectors for actions. Treat it as a helper that prepares the pack; a human
  still pastes or uploads. `[NEEDS VERIFICATION: the "agent mode will not use custom apps" scope;
  help.openai.com is not machine-fetchable.]`

The durable way to skip re-uploads entirely on ChatGPT is the live path (a developer-mode
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
| ChatGPT Project | RECOMMENDED home | `implementation/gpt/project/` + the shared knowledge files (the single combined file on Free) | project-only memory chosen at creation and changeable later in the project's settings, and it turns off ChatGPT Work in that project; file caps 5 Free / 25 Go-Plus / 40 Edu-Pro-Business-Enterprise, max 10 files per upload; project instructions replace global custom instructions inside the project (help/10169521, read in full 2026-09-19) |
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
   "category": "ai-surface-spec", "tier": "T1"},
  {"id": "openai-chatgpt-desktop-move", "name": "Moving to the new ChatGPT desktop app (help center)",
   "url": "https://help.openai.com/en/articles/20001276-moving-to-the-new-chatgpt-desktop-app",
   "category": "ai-surface-spec", "tier": "T1"},
  {"id": "openai-google-drive-app", "name": "Google Drive app and setup in ChatGPT (help center)",
   "url": "https://help.openai.com/en/articles/10929079-google-drive-app-and-setup-in-chatgpt",
   "category": "ai-surface-spec", "tier": "T1"},
  {"id": "claude-google-workspace-connectors", "name": "Use Google Workspace connectors (Claude help center)",
   "url": "https://support.claude.com/en/articles/10166901-use-google-workspace-connectors",
   "category": "ai-surface-spec", "tier": "T1"},
  {"id": "gemini-gems-to-skills", "name": "About the transition from Gems to skills (Gemini Apps Help)",
   "url": "https://support.google.com/gemini/answer/18560919",
   "category": "ai-surface-spec", "tier": "T1"},
  {"id": "gemini-skills-manage", "name": "Create and manage skills (Gemini Apps Help)",
   "url": "https://support.google.com/gemini/answer/17094296",
   "category": "ai-surface-spec", "tier": "T1"},
  {"id": "openai-custom-gpt-retirement", "name": "Custom GPT retirement and migration FAQ (help center)",
   "url": "https://help.openai.com/en/articles/20001519-custom-gpt-retirement-and-migration-faq",
   "category": "ai-surface-spec", "tier": "T1"},
  {"id": "gemini-mac-app", "name": "Use the Gemini app on Mac (Gemini Apps Help)",
   "url": "https://support.google.com/gemini/answer/17011627",
   "category": "ai-surface-spec", "tier": "T1"},
  {"id": "gemini-windows-app-launch", "name": "The Gemini app is now available for Windows (Google blog)",
   "url": "https://blog.google/innovation-and-ai/products/gemini-app/gemini-app-now-on-windows/",
   "category": "ai-surface-spec", "tier": "T1"},
  {"id": "gemini-spark-mac", "name": "Use Gemini Spark with the Gemini app on Mac (Gemini Apps Help)",
   "url": "https://support.google.com/gemini/answer/17208717",
   "category": "ai-surface-spec", "tier": "T1"},
  {"id": "gemini-custom-mcp-apps", "name": "Connect custom apps to Gemini Apps (Gemini Apps Help)",
   "url": "https://support.google.com/gemini/answer/17209137",
   "category": "ai-surface-spec", "tier": "T1"},
  {"id": "gemini-export-responses", "name": "Export responses from Gemini Apps (Gemini Apps Help)",
   "url": "https://support.google.com/gemini/answer/14184041",
   "category": "ai-surface-spec", "tier": "T1"},
  {"id": "gemini-connected-apps", "name": "Use & manage Connected Apps in Gemini (Gemini Apps Help)",
   "url": "https://support.google.com/gemini/answer/13695044",
   "category": "ai-surface-spec", "tier": "T1"}
]
```
