# Creator OS — GPT API Function Calling Integration

Five OpenAI function specs covering the most-used Creator OS entry points.

## Files

| File | Function name | Use when |
|---|---|---|
| `creator_core.yaml` | `creator_core_dispatch` | Any request; hub routes to right spoke |
| `keyword_compare.yaml` | `keyword_compare` | Quick cross-platform keyword comparison |
| `seo_keywords.yaml` | `seo_keywords` | Full keyword strategy deliverable |
| `competitor_analysis.yaml` | `competitor_analysis` | Competitor gap report |
| `video_development.yaml` | `video_development` | Full video production package |

## Python integration

```python
import openai
import yaml
from pathlib import Path

# Load all function specs
functions = [
    yaml.safe_load(f.read_text())
    for f in sorted(Path("implementation/gpt/api").glob("*.yaml"))
    if not f.name.startswith("README")
]

client = openai.OpenAI()

# Responses API (the current primary API; the Assistants API sunsets 2026-08-26 and
# chat.completions remains supported but is not where OpenAI's tooling investment goes).
response = client.responses.create(
    model="gpt-5.6",
    instructions=Path("implementation/gpt/web/custom-instructions.md").read_text(),
    input="Plan a seasonal home decor project video",
    tools=[{"type": "function", **fn} for fn in functions],
)

print(response.output_text)
```

## Live Creator OS tools from the API (P72)

The "no MCP from OpenAI" era is over: the Responses API takes hosted MCP servers directly, so a
deployed Creator OS endpoint gives API calls the same live tools as Claude Desktop:

```python
response = client.responses.create(
    model="gpt-5.6",
    input="Which of my tracked keywords fit an October publish?",
    tools=[{"type": "mcp", "server_label": "creator-os",
            "server_url": "https://YOUR-HOST/mcp",
            "allowed_tools": ["search", "fetch", "cache_query"],
            "require_approval": "always"}],
)
```

See `implementation/gpt/mcp-connector/README.md` for deployment and the approval loop that maps
Creator OS's human-confirmation invariant onto the API.

## Limitations vs Claude Desktop (without a deployed endpoint)

- Without a hosted MCP endpoint: competitor tag extraction, cache queries, and source staleness
  detection are unavailable; deploy the connector or use the Claude Desktop + MCP setup.
- No voice-profile.json hook: voice personalization requires the local file.
- All SEO estimates remain labeled [estimated]; no volume API is connected.

For full capability, use Claude Desktop with `tools/mcp_server.py` instead.
