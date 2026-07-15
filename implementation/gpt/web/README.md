# Creator OS — ChatGPT Custom Instructions Setup

## Setup

1. Open ChatGPT → click your profile → Settings → Personalization → Custom Instructions.
2. Paste the "Box 1" text from `custom-instructions.md` into the first field
   ("What would you like ChatGPT to know about you?").
3. Paste the "Box 2" text into the second field
   ("How would you like ChatGPT to respond?").
4. Save. Every new conversation will now use Creator OS routing.

## What works in ChatGPT Web

- Full hub routing (Content / Document / Pipeline lanes)
- All 22 spokes: video development, SEO keywords, project builder, competitor analysis,
  shortform repurposing, seasonal trends, audience research, analytics insights, document studio,
  account manager, deal pipeline, deal resourcing, partnership mediakit, quality review
- Voice rules enforcement (no em dashes, no opener exclamations, object-first openings)
- Protocol enforcement (no fabrication, formatting, safety)
- SEO SERP feature map and seasonal lead times (from knowledge only)
- Deal lifecycle management (9 stages, evidence-gated)

## What does NOT work in ChatGPT Web

| Feature | Why not available | Upgrade path |
|---|---|---|
| Competitor video tag extraction | Requires local HTML snapshots + ytInitialPlayerResponse parsing | Claude Desktop + MCP |
| FTS5 keyword cache queries | Requires local SQLite index | Claude Desktop + MCP |
| Source staleness detection | Requires local source-registry + Python tooling | Claude Desktop + MCP |
| Deterministic quality scoring | Requires score.py execution | Claude Desktop + MCP |
| YouTube / Instagram / TikTok API data | Requires OAuth credentials + local tooling | Claude Desktop + integrations-engine |
| Voice profile personalization | Requires voice-profile.json populated locally | Claude Desktop |

For full capability, use Claude Desktop with the MCP server.
See `implementation/claude/desktop/README.md` and `docs/DEPLOYMENT.md`.
