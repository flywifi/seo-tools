_Data freshness: as of 2026-09-24 (Creator OS baseline 9953a93c). Live updates come from your own store; see docs/FRESHNESS.md. Source and updates: github.com/flywifi/seo-tools._

# Creator OS -- setup help and what works where

This file lets Creator OS walk you through its own setup from inside a chat. If you are
reading this in a Claude Project or a ChatGPT Project, the setup that put this file here is
already mostly done. Facts below were verified against the vendors' own help pages on
2026-09-20; anything that could not be verified first-party says so plainly.

## Which Claude am I in?

Since 2026-09-16, Claude chat and Claude Cowork are one Claude: there is no separate mode to
pick, and Claude routes quick answers and longer agentic work itself. The change is rolling
out in stages starting with Pro and Max plans, so an account may still show a separate Cowork
tab for a while; this Project behaves the same either way. Claude Docs and Claude Slides
(collaborative documents and presentations) exist in beta on paid plans.

- **claude.ai (web or mobile)**: full routing, scripts, SEO, documents, and deal pipeline
  guidance from this Project's knowledge. Skills and connectors work here too (see the doors
  below). No local tools: no competitor tag extraction, no keyword cache, no staleness checks,
  no deterministic quality scoring. When you ask for one of those, Creator OS says so honestly
  and names the upgrade -- it never pretends.
- **ChatGPT Project**: the same knowledge-only mode, same honesty rules.
- **Claude Desktop (the computer app)**: everything above PLUS the live tools through a small
  local server. Even in the merged Claude, local files and local tools work only while the
  Desktop app is open on that computer.

## Four ways to run Creator OS on claude.ai, best first

1. **The plugin (paid plans).** Everything installs in one step: open Customize, then Plugins,
   and add the Creator OS marketplace link (github.com/flywifi/seo-tools). Skills and
   connectors from the plugin work in any conversation; deeper automation runs in agentic
   sessions. The repository is public, so the link needs no access grant; marketplace plugins
   are a paid-plan feature, so on Free use door 2 or 3.
2. **This Project, fed straight from GitHub.** In the Project's knowledge area, choose the "+"
   button, pick GitHub, select the Creator OS repository, and choose the folder
   `implementation/claude/project/`. Syncing is manual: press "Sync now" after the maintainer
   ships an update. The repository is public, so no special access is needed; just sign in to
   GitHub when the connector asks. The plan requirements for this connector are not stated in
   the vendor's article, so check it on your plan.
3. **This Project, fed by uploaded files.** Works on every plan, including Free (Free is
   capped at five projects). Upload the numbered knowledge files, or the single combined file
   `creator-os-combined.md` -- one or the other, not both. See "Getting the files" below.
4. **Individual skill uploads (any plan).** Enable code execution under Settings, then
   Capabilities ("Code execution and file creation"), then upload a skill ZIP under Customize,
   then Skills. Plain skill files reference shared engine files and dangle on their own, so
   ask the maintainer to build the STANDALONE zips: the setup wizard's claude.ai screen has a
   one-click "Build upload-ready skill ZIPs" button that bundles each skill's engine text
   inside. Multi-skill orchestration still needs the plugin door.

## Finishing a claude.ai Project (5 minutes, no terminal)

1. On claude.ai: Projects, then New Project. Name it "Creator OS".
2. Paste the contents of `system-prompt.md` into "Set project instructions" and save.
3. Add the knowledge using door 2 or door 3 above.
4. Test with: "Plan a seasonal home decor project makeover video." You should get a Content
   lane routing and a structured output with hooks, titles, and a script outline.

## Getting the files with no repository on your computer

- Ask the maintainer of your Creator OS install to send them, or to mirror them into the
  shared "Creator OS" Google Drive folder under `Knowledge/` (the setup wizard's Drive hub
  screen does this in one click); you can then download them from Drive.
- Every file is on the public GitHub page (github.com/flywifi/seo-tools) under
  `implementation/claude/project/`.
- Or skip files entirely: doors 1 and 2 above read from the repository directly.

## Finishing a ChatGPT Project

Fastest path: on the maintainer's computer, the setup wizard (`python3 tools/wizard.py`, the
ChatGPT button) copies each paste for you, stages the exact upload folder for the plan, and
then verifies the setup from pasted answers. The manual path: same files, different door: New project, choose project-only memory, paste
`project-instructions.md` (from `implementation/gpt/project/`) as the project instructions,
then upload the same numbered knowledge files. Plan file caps (confirmed 2026-09-19): 5 on
Free, 25 on Go and Plus, 40 on Edu, Pro, Business, and Enterprise, at most 10 files per
upload. On Free the full bundle does not fit; upload 01 through 05 first. Do not build a new
Custom GPT for this: OpenAI retires Custom GPTs for Enterprise on 2026-12-11 and other plans
are expected to follow; the Project door is the recommended home.

## Connecting Google on claude.ai

claude.ai has a built-in Google Workspace connector: open Customize, then Connectors, find
Google Workspace, click Add, sign in, and click Allow. Creator OS can then read Gmail (brand
pitches), Google Calendar (content schedule), and Google Drive files when you ask. Microsoft
365 is not available on claude.ai; it needs the Claude Desktop path.

## The Claude Desktop upgrade (what it adds, who does it)

Everything Creator OS installs stays inside the user's own account (home folder only, no
admin rights); the Claude Desktop app itself belongs in `~/Applications`, not the shared
`/Applications`. The upgrade is a maintainer task on the computer itself: run `python3 tools/wizard.py` in the
Creator OS folder and press "Set everything up". The wizard installs the tools, verifies the
Creator OS server actually answers before saying done, and walks Google, Microsoft, and
publishing connections step by step with a Skip on every screen. What you gain: competitor
hidden-tag extraction, the offline keyword cache, source staleness detection, deterministic
quality scoring, your real channel analytics, and local transcription. Publishing stays off
by default, and every post always requires explicit human confirmation.

## When something is not available here

Creator OS on a web surface answers with its best knowledge-only output, then names the
missing capability and the surface that has it. It never invents data, metrics, or sources
(anything unverified is flagged, not filled in), and it never posts anything anywhere from
any surface without explicit human confirmation.

## Keeping this Project fresh

Every knowledge file carries a "Data freshness" line near the top with a date. After the
maintainer updates Creator OS: a GitHub-connected Project re-syncs with one click ("Sync
now"), a Drive-fed Project updates when the maintainer refreshes the Knowledge folder, and an
upload-fed Project needs the changed files re-uploaded. If an answer ever cites a freshness
date that looks old, that is the signal to refresh.
