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

## Keeping pasted packs fresh (the re-sync procedure)

Every packaging artifact carries a first line reading `Packaging version: <version>`. The wizard
shows the current Creator OS version on its ChatGPT and transitions screens.

- Compare the version line at the top of what you pasted (custom instructions, GPT instruction
  file, Gem instruction) with the wizard's current version.
- If yours is lower: re-export the pack, then re-paste custom instructions, or re-upload the GPT
  or Project knowledge files, or re-paste the Gem instruction.
- There is no automatic push; pasted text never updates itself.

## What never changes, anywhere

Human review before anything outward. No fabrication: a number the surface cannot verify is a
null and a flag, never a guess. End-user deployments never touch GitHub. Assembled contracts are
always drafts for counsel, on every surface.
