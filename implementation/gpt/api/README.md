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
import json
import openai
import yaml
from pathlib import Path

# Load all function specs
functions = [
    yaml.safe_load(f.read_text())
    for f in sorted(Path("implementation/gpt/api").glob("*.yaml"))
    if not f.name.startswith("README")
]

# Map each function name to the code that runs it. You write these five callables.
HANDLERS = {
    # "creator_core_dispatch": your_dispatch_function,
    # "keyword_compare": your_keyword_compare_function,
    # "seo_keywords": your_seo_keywords_function,
    # "competitor_analysis": your_competitor_analysis_function,
    # "video_development": your_video_development_function,
}

# strict is set to False explicitly; see "Strict mode is off on purpose" below.
TOOLS = [{"type": "function", "strict": False, **fn} for fn in functions]

client = openai.OpenAI()

# Responses API (the current primary API; the Assistants API was sunset on 2026-08-26 and the
# Responses API is its replacement, with stateful context via store: true; chat.completions
# remains supported but is not where OpenAI's tooling investment goes).
response = client.responses.create(
    model="gpt-5.6",  # stable alias routing to GPT-5.6 Sol; OpenAI's current flagship is gpt-6-astra
    instructions=Path("implementation/gpt/web/custom-instructions.md").read_text(),
    input="Plan a seasonal home decor project video",
    tools=TOOLS,
)

# The model answers in prose, or asks for one or more of the functions. Run each requested
# function, send its result back, and repeat until the model stops asking.
while True:
    calls = [item for item in response.output if item.type == "function_call"]
    if not calls:
        break
    outputs = []
    for call in calls:
        result = HANDLERS[call.name](**json.loads(call.arguments))
        outputs.append({"type": "function_call_output", "call_id": call.call_id,
                        "output": json.dumps(result)})
    response = client.responses.create(
        model="gpt-5.6",
        previous_response_id=response.id,
        input=outputs,
        tools=TOOLS,
    )

print(response.output_text)
```

`HANDLERS` is yours to supply: this folder ships the five function specs, not their
implementations. Each handler takes the arguments the spec declares and returns something
`json.dumps` can serialize. The loop follows OpenAI's function-calling guide
(developers.openai.com/api/docs/guides/function-calling, read 2026-11-16): each `function_call`
item in `response.output` carries `name`, JSON-encoded `arguments` and a `call_id`, and the
result goes back as a `function_call_output` item with the same `call_id`.

**Strict mode is off on purpose.** The guide recommends `strict: true`, which requires
`additionalProperties: false` on each object and each property listed as required. The specs
here keep `minItems`/`maxItems` (keyword_compare), `minimum`/`maximum` (competitor_analysis) and
`default` values, so the example sets `strict: False` explicitly: when the flag is omitted, the
Responses API tries to normalize the schema into strict mode and falls back to best-effort
calling when it cannot (same guide, "Strict mode"). Validate the arguments in your handler.

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
    # connector_id is deprecated for models released after 2026-09-01: use server_url, or
    # tunnel_id for a Secure MCP Tunnel (developers.openai.com tools-connectors-mcp, 2026-09-19).
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

```sources
[
  {"id": "openai-function-calling", "name": "OpenAI function calling guide (tool loop, strict mode)",
   "url": "https://developers.openai.com/api/docs/guides/function-calling",
   "category": "ai-surface-spec", "tier": "T1"}
]
```
