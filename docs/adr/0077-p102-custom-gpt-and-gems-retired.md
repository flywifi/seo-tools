# ADR 0077 — The custom GPT and Gemini Gems surfaces and their export atoms are retired; the wizard writes the Claude Desktop settings file the app reads

- Status: accepted
- Date: 2026-10-05
- Phase: P102

## Context

OpenAI's retirement FAQ (help article 20001519) says custom GPTs are scheduled to retire on
2026-12-11, or 2027-02-11 for Enterprise workspaces with an approved deferral, and that custom
actions do not transfer through the migration workflow. ADR 0060 kept the `export-gpt` atom and
the custom GPT door while steering new setups to a ChatGPT Project.

Google's help center (support.google.com/gemini/answer/18560919) says Gems transition to skills
from November 2026 for personal Google Accounts, March 2027 for Workspace business, enterprise
and non-profit accounts and June 2027 for education accounts, and that existing Gems are
recreated as skills. Skills are offered to personal accounts first (answer/17094296).

On Windows, the packaged (MSIX) build of Claude Desktop reads its settings from
`%LOCALAPPDATA%\Packages\Claude_<id>\LocalCache\Roaming\Claude`, while the wizard wrote
`%APPDATA%\Claude` (claude-code issue 26073), so the Creator OS tools did not appear there.

## Decision 1: the two surfaces and their export atoms leave Creator OS

`chatgpt_custom_gpt` and `gemini_gems` leave `shared/cross-modality/transitions.json` with the
five pair overrides that named them, drift invariant 32's key list and the wizard's surface
options; links that named them land on `chatgpt_projects` and `gemini_web`. The S10 scenario
checks the rows stay absent. The `export-gpt` and `export-gem` atoms, their capability flags and
degraded-mode messages, and the GPT Action pack (`implementation/gpt/actions/`) are deleted.
ChatGPT setups use a Project (the single combined knowledge file on Free); Gemini setups paste
`implementation/gemini/system-instruction.md` into a chat or save it as a skill. The
profile-import prompt still reads a custom GPT's knowledge until the retirement date, so a
person can bring it home first. This supersedes ADR 0060.

## Decision 2: the wizard writes the settings file Claude Desktop reads

On Windows the wizard writes to the file named on Claude Desktop's newest "Reading
claude_desktop_config.json from" log line, when that file's folder exists; else to the packaged
app's folder, plus `%APPDATA%\Claude` when that file already exists; else to `%APPDATA%\Claude`
(`wizard._claude_config_targets`). Each file is merged from its own content, and a new file
starts from a copy of an existing one. The log line is app wording, not a documented interface,
so a missing or reworded line falls back to the folder rules.

## Consequences

- Atoms go from 106 to 104 and skills from 130 to 128; the transitions matrix holds nine surfaces.
- A person on a work or school Google account keeps Gems until 2027 and may not have skills yet;
  the plain-chat route works for every account.
- The jurisdiction overlay has no no-code ChatGPT route after 2026-12-11; the developer-mode
  connector is the live route.
- CHANGELOG history, the ledger and earlier ADRs keep their wording.

```sources
[
  {"id": "openai-custom-gpt-retirement", "name": "Custom GPT retirement and migration FAQ (help center)", "url": "https://help.openai.com/en/articles/20001519-custom-gpt-retirement-and-migration-faq", "category": "ai-surface-spec", "tier": "T1"},
  {"id": "gemini-gems-to-skills", "name": "About the transition from Gems to skills (Gemini Apps Help)", "url": "https://support.google.com/gemini/answer/18560919", "category": "ai-surface-spec", "tier": "T1"},
  {"id": "gemini-skills-manage", "name": "Create and manage skills (Gemini Apps Help)", "url": "https://support.google.com/gemini/answer/17094296", "category": "ai-surface-spec", "tier": "T1"},
  {"id": "claude-desktop-msix-config-path", "name": "Claude Desktop MSIX build reads a different claude_desktop_config.json (claude-code issue 26073)", "url": "https://github.com/anthropics/claude-code/issues/26073", "category": "ai-surface-spec", "tier": "T2"}
]
```
