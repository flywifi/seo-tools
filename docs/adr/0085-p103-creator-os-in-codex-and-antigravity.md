# 0085. Creator OS runs in Codex and Antigravity through the same local server entry

- Date: 2026-11-07
- Status: Accepted

## Context

ADR 0084 sorts inbound mail on this computer when the session runs in Claude Desktop, which starts
`tools/mcp_server.py` on stdio from one entry in its settings file. The person asked for the same on
the other assistants with no steps per run: no export file to save, nothing to paste. Two routes
were turned down. The ChatGPT, Gemini and claude.ai web chats reach a tool on this computer only
through the remote connector (`implementation/gpt/mcp-connector/README.md`: a public HTTPS host
with authentication in front of it), and a Gmail reader of Creator OS's own needs a Google Cloud
OAuth client, whose grants expire after seven days while the client is in Testing.

Two assistants run local tools from a settings file the way Claude Desktop does. Codex (the ChatGPT
desktop app's Codex view, the `codex` command and the IDE extension) reads `[mcp_servers.<name>]`
tables from `~/.codex/config.toml`, one file for the three; its plugins, the Gmail plugin among
them, work "in Codex in the ChatGPT desktop app", and "Codex CLI also has a plugin browser"
(learn.chatgpt.com). OpenAI's Gmail plugin "connects Gmail for searching mail, reading threads,
drafting and organizing messages, and triaging an inbox". Antigravity's IDE and its `agy` command
read `mcpServers` from the global file `~/.gemini/config/mcp_config.json`; the Antigravity app shows
its settings file's path behind a "Copy Config File Path" button, and the docs do not say it is the
same file. An unconfigured tool runs in Ask mode; Antigravity replaced Gemini CLI for the free, AI
Pro and AI Ultra plans on 2026-06-18. Gmail in Antigravity is a tool of its own: Google's Workspace
extension for Gemini CLI (its README asks for a Google sign-in and describes no read-only mode;
Gmail tools that search, read, modify, send, draft and label; a warning against processing mail
from unverified sources),
brought in with `agy plugin import gemini`, or Google's Workspace MCP servers, which need a Google
Cloud project, the Workspace Developer Preview Program and an OAuth client. The Gemini web and
mobile app takes a hosted server address, on personal accounts.

## Decision

1. **One entry, three apps.** The wizard's Install screen gets two optional buttons beside the
   Claude Desktop one. "Add to Codex and verify" writes the `creator-os` entry
   (`tools/wizard.py::_update_codex_config`) into `~/.codex/config.toml` as the
   `[mcp_servers.creator-os]` and `[mcp_servers.creator-os.env]` tables, strings written as TOML
   basic strings (JSON escaping up to U+FFFF, `\UXXXXXXXX` above it). The file's own `creator-os`
   table is replaced and
   its other tables and keys are kept, which the writer checks by parsing the text before it saves
   it: it refuses, writing nothing, when the file does not parse as TOML, when the entry itself is
   not valid TOML (a path holding a lone surrogate), when a `creator-os` entry
   is written there in a form it does not rewrite (an inline table or dotted keys), or when the
   result would not parse, would change another key, or would not read back as the entry. "Add to
   Antigravity and verify" writes the same entry (`_update_antigravity_config`) into
   `~/.gemini/config/mcp_config.json`, keeping the file's other servers and keys; a file that does
   not parse is backed up beside itself first, as the Claude Desktop writer does, and an
   `mcpServers` that is not an object is refused. Each button then runs the handshake probe the
   Claude Desktop button runs and tells the person to restart the app. A missing file is created;
   a settings file the system refuses to write shows the reason and runs no probe.
2. **The same tool, unmasked.** The three apps start the server on stdio, so `mail_triage` shows
   the CRM side of each match (ADR 0084). The `mail-triage` atom names Codex and Antigravity beside
   Claude Desktop.
3. **The Gmail side is the app's own.** The wizard installs no Gmail tool. The docs say which tool
   each app uses, that each can send or change mail when asked, and that Creator OS asks for reads.
   For Antigravity the docs give both routes with their limits; which works on an account is
   checked on the computer, not promised.
4. **Scope.** Antigravity is not added to the surfaces model
   (`shared/cross-modality/transitions.json`); the maintainers' table in `docs/TRANSITIONS.md`
   gets a row. The Gemini web app's custom apps and the remote connector are unchanged.

## Consequences

- On a computer with Codex or Antigravity, "check my inbox for brands" sorts mail there after one
  press of the button and the app's own Gmail tool is installed; the person does nothing per run.
- Codex's `config.toml` holds settings beyond servers, so the writer refuses rather than rewrite a
  file it cannot keep whole; the person is told to fix or move the file.
- The Antigravity writer treats a file that does not parse as the Claude Desktop writer does: a
  backup beside the file, then a file holding the entry.
- Not done: checking on a Mac that the Gmail plugin is on the person's ChatGPT plan, which
  Antigravity Gmail route works on a personal account, and that the Antigravity app reads
  `~/.gemini/config/mcp_config.json`, the file its IDE and `agy` command read. These are the
  owner's live step.

## Sources

```sources
[
  {"id": "codex-mcp-config", "name": "Codex MCP configuration (config.toml)", "url": "https://learn.chatgpt.com/docs/extend/mcp", "category": "ai-surface-spec", "tier": "T1"},
  {"id": "codex-plugins", "name": "ChatGPT Learn - Plugins (ChatGPT and Codex)", "url": "https://learn.chatgpt.com/docs/plugins", "category": "ai-surface-spec", "tier": "T1"},
  {"id": "openai-gmail-plugin", "name": "OpenAI plugins - Gmail plugin README", "url": "https://github.com/openai/plugins/tree/main/plugins/gmail", "category": "ai-surface-spec", "tier": "T1"},
  {"id": "chatgpt-inbox-use-case", "name": "ChatGPT Learn - Get your email to inbox zero (Gmail skill)", "url": "https://learn.chatgpt.com/use-cases/manage-your-inbox", "category": "ai-surface-spec", "tier": "T1"},
  {"id": "antigravity-mcp", "name": "Google Antigravity Docs - Model Context Protocol (MCP)", "url": "https://antigravity.google/docs/mcp/", "category": "ai-surface-spec", "tier": "T1"},
  {"id": "antigravity-gcli-migration", "name": "Google Antigravity Docs - Migrating from Gemini CLI", "url": "https://antigravity.google/docs/cli/gcli-migration", "category": "ai-surface-spec", "tier": "T1"},
  {"id": "antigravity-plugins", "name": "Google Antigravity Docs - Plugins", "url": "https://antigravity.google/docs/plugins/", "category": "ai-surface-spec", "tier": "T1"},
  {"id": "gemini-cli-to-antigravity", "name": "Google Developers Blog - Transitioning Gemini CLI to Antigravity CLI", "url": "https://developers.googleblog.com/an-important-update-transitioning-gemini-cli-to-antigravity-cli", "category": "ai-surface-spec", "tier": "T1"},
  {"id": "gemini-cli-workspace-extension", "name": "Google Workspace extension for Gemini CLI (README and tool list)", "url": "https://github.com/gemini-cli-extensions/workspace", "category": "mcp-server", "tier": "T1"},
  {"id": "google-workspace-mcp-servers", "name": "Google Workspace - Configure the Google Workspace MCP servers", "url": "https://developers.google.com/workspace/guides/configure-mcp-servers", "category": "ai-surface-spec", "tier": "T1"},
  {"id": "gemini-custom-mcp-apps", "name": "Gemini Apps Help - Connect and manage custom apps", "url": "https://support.google.com/gemini/answer/17209137", "category": "ai-surface-spec", "tier": "T1"}
]
```
