# Creator OS — Gemini Setup

## Gemini Advanced (Gems)

1. Open Gemini Advanced → Gems → New Gem.
2. Name it "Creator OS".
3. Paste the full contents of `system-instruction.md` into the Instructions field.
4. Save. Use the Gem for all creator requests.

## Gemini API

```python
import google.generativeai as genai
from pathlib import Path

genai.configure(api_key="YOUR_API_KEY")

system_instruction = Path("implementation/gemini/system-instruction.md").read_text()

model = genai.GenerativeModel(
    model_name="gemini-2.0-flash",
    system_instruction=system_instruction,
)

response = model.generate_content("Plan a dark moody fall mantel video")
print(response.text)
```

## Capability notes

Gemini runs in knowledge-only mode — the same limitations as ChatGPT Web apply.
No MCP tools, no local Python tooling, no API credentials. For full capability
use Claude Desktop. See `docs/DEPLOYMENT.md` for the capability matrix.
