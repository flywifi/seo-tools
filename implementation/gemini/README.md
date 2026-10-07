# Creator OS — Gemini Setup

## Gemini chat (web, mobile or desktop app)

1. Paste the full contents of `system-instruction.md` at the start of a chat.
2. On a personal Google Account you can save it as a skill instead: Settings, then Skills, then
   Create manually (or upload it as a SKILL.md on the web app or the Mac app).
3. Gemini Gems are retired: Google turns them into skills from November 2026 for personal
   accounts and in 2027 for work and school accounts.

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

response = model.generate_content("Plan a seasonal home decor project video")
print(response.text)
```

## Capability notes

Gemini runs in knowledge-only mode — the same limitations as ChatGPT Web apply.
No MCP tools, no local Python tooling, no API credentials. For full capability
use Claude Desktop. See `docs/DEPLOYMENT.md` for the capability matrix.
