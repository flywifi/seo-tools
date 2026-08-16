# Creator OS — ChatGPT Custom Instructions Setup

## Setup

1. Open ChatGPT → click your profile → Settings → Personalization → Custom Instructions.
2. Paste the "Box 1" text from `custom-instructions.md` into the first field
   ("What would you like ChatGPT to know about you?").
3. Paste the "Box 2" text into the second field
   ("How would you like ChatGPT to respond?").
4. Save. Every new conversation will now use Creator OS routing.

Size and tier notes (verified 2026-08): the custom-instructions cap is 1,500 characters on
Free/Go and 5,000 on Plus and above; whether the cap is per-field or combined is not officially
documented, so the full version is kept under 5,000 COMBINED and paste-validated by
`tools/surface_budgets.py`. On Free/Go, use `custom-instructions-compact.md` (under 1,500
combined). If you are on a personal plan and want a richer setup than two boxes, use a ChatGPT
Project instead (see `implementation/gpt/project/`): file uploads plus project instructions plus
project-only memory, on every tier.

## What works in ChatGPT Web

- Full hub routing (Content / Document / Pipeline lanes)
- All 22 spokes: video development, SEO keywords, project builder, competitor analysis,
  shortform repurposing, seasonal trends, audience research, analytics insights, document studio,
  account manager, deal pipeline, deal resourcing, partnership mediakit, quality review
- Voice rules enforcement (no em dashes, no opener exclamations, object-first openings)
- Protocol enforcement (no fabrication, formatting, safety)
- SEO SERP feature map and seasonal lead times (from knowledge only)
- Deal lifecycle management (9 stages, evidence-gated)

## What does NOT work in plain ChatGPT Web (pasted instructions only)

These are unavailable when Creator OS is only two pasted instruction boxes. Since P72 there are
TWO upgrade routes, not one: the local computer setup, or a deployed MCP connector that ChatGPT
itself can reach.

| Feature | Why not available here | Upgrade path |
|---|---|---|
| Competitor video tag extraction | Requires local HTML snapshots + ytInitialPlayerResponse parsing | Claude Desktop + MCP, **or** a deployed connector (`competitor_scan`) |
| FTS5 keyword cache queries | Requires the local SQLite index | Claude Desktop + MCP, **or** a deployed connector (`cache_query`; also reachable via the `search`/`fetch` pair with no developer mode) |
| Source staleness detection | Requires the local source-registry + Python tooling | Claude Desktop + MCP, **or** a deployed connector (`source_staleness`) |
| Deterministic quality scoring | Requires score.py execution | Claude Desktop + MCP, **or** a deployed connector (`quality_score`) |
| YouTube / Instagram / TikTok API data | Requires OAuth credentials + local tooling | Claude Desktop + integrations-engine (credentials stay on your machine) |
| Voice profile personalization | Requires voice-profile.json populated locally | Claude Desktop |

For full capability without leaving ChatGPT, deploy the MCP connector and add it in developer
mode: `implementation/gpt/mcp-connector/README.md`. For the local route, see
`implementation/claude/desktop/README.md` and `docs/DEPLOYMENT.md`. For a richer knowledge-only
setup on a personal plan, use a ChatGPT Project: `implementation/gpt/project/README.md`.

```sources
[
  {"id": "openai-custom-instructions-caps", "name": "ChatGPT custom instructions (help center)",
   "url": "https://help.openai.com/en/articles/8096356-chatgpt-custom-instructions",
   "category": "ai-surface-spec", "tier": "T1"},
  {"id": "openai-projects-help", "name": "Projects in ChatGPT (help center)",
   "url": "https://help.openai.com/en/articles/10169521-projects-in-chatgpt",
   "category": "ai-surface-spec", "tier": "T1"}
]
```
