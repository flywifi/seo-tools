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

response = client.chat.completions.create(
    model="gpt-4o",
    messages=[
        {
            "role": "system",
            "content": (
                Path("implementation/gpt/web/custom-instructions.md").read_text()
            ),
        },
        {"role": "user", "content": "Plan a seasonal home decor project video"},
    ],
    tools=[{"type": "function", "function": fn} for fn in functions],
    tool_choice="auto",
)

print(response.choices[0].message)
```

## Limitations vs Claude Desktop

- No MCP tools: competitor tag extraction, cache queries, and source staleness
  detection require the Claude Desktop + MCP setup.
- No voice-profile.json hook: voice personalization requires the local file.
- All SEO estimates remain labeled [estimated] — no volume API is connected.

For full capability, use Claude Desktop with `tools/mcp_server.py` instead.
