# Moving Creator OS between AIs: the transitions guide (P43)

Creator OS runs best where your files live, but you can carry it to any AI surface if you know
what travels, what stops working, and what to re-import. This doc mirrors the machine source of
truth at `shared/cross-modality/transitions.json`; the setup wizard's `/transitions` screen
renders any from/to pair from the same data (run `python3 tools/wizard.py` and pick "I use more
than one"). Anything tagged `[NEEDS VERIFICATION: ...]` depends on your ChatGPT or Gemini plan
and must be checked against your own account; the repo does not assert it.

## The nine surfaces

| Surface | What runs there | Flags enforced? |
|---|---|---|
| Claude Desktop (this computer) | everything (Class A, B, C native) | yes |
| Claude Code / command line | everything | yes |
| claude.ai in a browser (web and mobile) | knowledge natively; live tools via a deployed remote MCP connector | no (the endpoint's machine enforces) |
| ChatGPT web chat (plain chat at chatgpt.com) | knowledge-only (pasted custom instructions + uploaded files) | no |
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

## The common transitions

Each pair below is authored in the matrix; the wizard renders every other combination by deriving
it from the two surface records.

- **Claude Desktop to ChatGPT web chat:** export the knowledge pack (paste
  `implementation/gpt/web/custom-instructions.md` into ChatGPT settings) and carry data as dated
  export files. Everything computed locally stops: finance math, template assembly, obligation
  dates, the deterministic quality score, flag enforcement. Your computer stays authoritative.
- **Claude Desktop to a Custom GPT:** run the export-gpt package (instruction + up to 20
  knowledge files); optionally add the jurisdiction Action. The Action sends what you type to
  OpenAI and the public endpoint; the local ask-first consent step does not apply there.
- **Claude Desktop to ChatGPT Projects:** reuse the same package as Project instructions +
  files. Limits vary by plan [NEEDS VERIFICATION: check your plan].
- **Claude Desktop to the ChatGPT desktop app:** the strongest ChatGPT surface. Knowledge paste
  works like the web; live tools become possible by deploying the remote MCP endpoint
  (`implementation/gpt/mcp-connector/README.md`) and adding it as a developer-mode connector
  [NEEDS VERIFICATION: plan gating].
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
