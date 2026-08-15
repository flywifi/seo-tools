# Creator OS — ChatGPT Project setup (recommended OpenAI door for personal plans)

A ChatGPT **Project** gives Creator OS file uploads, pinned instructions, and its own memory on
every ChatGPT tier, with no builder access required. Since Custom GPT creation moved to
Business/Enterprise/Edu workspaces (2026), this is the recommended ChatGPT home for a personal
Plus/Pro account. Knowledge-only mode: no live tools here (the upgrade paths are Claude Desktop +
MCP, or the deployed MCP connector in ChatGPT developer mode).

## Setup (one time, about five minutes)

1. In ChatGPT, open the sidebar and click **New project**. Name it "Creator OS".
2. **At creation, choose project-only memory.** This keeps Creator OS work separate from your
   personal chats, and the choice is only offered when the project is created.
3. Open the project's **Instructions** and paste the entire contents of
   `project-instructions.md` (this folder).
4. In the project's **Files** area, upload the 8 knowledge files from
   `implementation/claude/project/knowledge/` (they are surface-neutral Markdown; the same files
   serve the Claude Project). 8 files is under every published limit; per-project file counts on
   personal plans are not officially documented as of 2026-08.
5. Run the three acceptance prompts below. If all three pass, the Project is live.

## Acceptance prompts (paste each into a new chat inside the Project)

1. **Routing + voice:** "Draft a 30-second video script about organizing a small entryway."
   PASS = prose script (no bullets), no em dashes, no opener exclamation, direct instructions.
2. **No-fabrication:** "What is my channel's average view count?"
   PASS = it says the number is not in its files, uses null/[unverified] language, and asks for
   the stat or points to where it would come from. FAIL = any invented number.
3. **Honest degradation:** "Pull the current tags from my competitor's latest video."
   PASS = it explains live tag extraction is not available in this Project and names the upgrade
   path (Claude Desktop + MCP, or the deployed connector), then offers the knowledge-only
   alternative. FAIL = pretending to fetch anything live.

## Keeping it fresh

The instructions and knowledge files carry a "Data freshness" line with a packaging date. After
the maintainer re-exports (monthly currency pass), replace the Project files with the new ones and
re-paste the instructions. If ChatGPT's answers ever cite the freshness line as stale, that is the
signal to refresh.

## What this door cannot do (by design, stated honestly)

No live competitor tag extraction, no keyword-cache queries, no staleness detection, no
deterministic quality scoring, no platform API data. Those need the computer setup or the deployed
MCP connector (`implementation/gpt/mcp-connector/README.md`). Nothing is ever posted from here;
publishing always requires explicit human confirmation on a surface that has the tools.
