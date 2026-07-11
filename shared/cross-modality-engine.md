# Cross-Modality Engine

Source of truth for **where and how a Creator OS capability runs outside Claude**. Creator OS is
authored as Claude Agent Skills, but a user may be on Claude Desktop, Claude Code, claude.ai
web/mobile, a Custom GPT, the Gemini API, a Gemini Gem, or no AI at all. Every skill must know which
of those surfaces it can serve, by what mechanism, and what it falls back to. This engine defines the
model; each `SKILL.md` declares its own answer in a `## Cross-modality` section (below); the setup
wizard uses these declarations to guide per-surface setup; `docs/CROSS-MODALITY.md` carries the worked
example (jurisdictional overlay).

## 1. The three capability classes
Classify every skill/atom by what it fundamentally needs to run:

- **Class A: pure reasoning** (knowledge + the model). No tools. Runs on *every* surface including a
  consumer Gemini Gem. Example: brand-voice guidance, a formatting pass.
- **Class B: offloadable compute** — the heavy step is a call to a **public or hosted endpoint** that
  does the work server-side. Runs anywhere that can make an HTTPS request; the model just needs the
  call wired. Example: the jurisdictional overlay (ArcGIS/FEMA/Census do point-in-polygon server-side),
  a keyword pull, a currency check.
- **Class C: local-runtime compute** — needs a local Python/tool runtime (or an MCP host) to execute.
  Runs natively on Claude Desktop (MCP) and Claude Code; on other surfaces it degrades to Class B (via
  a hosted endpoint) or Class A (the model reasons under the engine spec, flagged unverified).
  Example: the offline GIS engine, media probing, offline money math.

The design goal: **push capabilities toward Class B** wherever a public/hosted endpoint can do the
work, because Class B is the universal path. When a capability is inherently Class C, provide a hosted
seam (remote MCP, a GPT Action over your own endpoint, or a Gemini-backend call) so it still reaches
non-Claude surfaces.

## 2. The surface matrix (what each surface can do)

| Surface | Local code exec | Calls external REST | Custom tools | Reaches Class B | Reaches Class C |
|---|---|---|---|---|---|
| Claude Desktop (local MCP) | yes (MCP server) | yes | yes (MCP) | native | native |
| Claude Code / CLI | yes | yes | yes | native | native |
| claude.ai web/mobile | sandbox only | via connector/sandbox | yes (remote MCP connector) | via remote MCP | via remote MCP |
| Custom GPT (OpenAI) | no | yes (Actions) | yes (Actions) | GPT Action -> public/hosted REST | only via a hosted endpoint |
| Gemini API (developer) | your backend | your backend | yes (function calling) | function call -> your backend executes | your backend runs the tool |
| Gemini "Gems" (consumer) | no | no | no | NO | NO |
| Human (curl/browser) | if they have it | yes | n/a | curl the endpoint | run the tool locally |

The **one hard dead end** is the consumer Gemini Gems UI (Class A only). Everything else reaches Class
B, and Class C where a runtime or a hosted seam exists.

## 3. The packaging map (how a capability is exposed per surface)
- **Claude Desktop / Code:** MCP tools in `tools/mcp_server.py` (+ `implementation/claude/`). Native
  Class C.
- **claude.ai web/mobile + cross-AI:** the **remote MCP** transport (`tools/mcp_server.py
  --serve-remote`). One deployed endpoint CAN serve Claude web/desktop/mobile, ChatGPT (developer
  mode, web and desktop app), and Gemini, IF you or your developer host it behind HTTPS with
  authentication; the repo ships the server code and the runbook
  (`implementation/gpt/mcp-connector/README.md`), not a hosted service, and implements no
  authentication itself. ChatGPT-side registration steps carry needs-verification tags (plan
  gating). Capability flags and consent gates enforce on the endpoint's machine, never inside the
  connecting surface.
- **Custom GPT:** a **GPT Action** OpenAPI schema under `implementation/gpt/actions/` targeting a
  public endpoint (Class B) or your hosted endpoint (Class C).
- **Gemini API:** **function declarations** under `implementation/gemini/` (the model emits the call,
  your app executes it).
- **Gemini Gems / any Class-A surface:** the knowledge-only packaging
  (`implementation/gemini/system-instruction.md`, `implementation/gpt/web/`) plus, for offloadable
  skills, an explicit "paste a coordinate / use the API" fallback note.
- **Human:** a documented `curl` / example script (e.g. `tools/geo_source_fetch.py`).

## 4. The fallback ladder (degrade, never fail silently)
For a Class B or C skill, resolve in this order and STATE which rung was used:
1. Native local tool (MCP / CLI).
2. Hosted seam (remote MCP, GPT Action, Gemini-backend).
3. Public endpoint direct (Class B universal path).
4. Model-reasons-under-spec (Class A), explicitly flagged as unverified, with the exact call the user
   could run themselves.
5. Ask the user for the missing input (e.g. a coordinate a Gem cannot fetch).

Never fabricate the result of a step that did not run; null-and-flag and name the rung.

## 5. Non-negotiables that hold on every rung
- Advisory/safety boundaries and human-review escalations travel with the capability, encoded in the
  Action/function descriptions and the skill instructions, not just the Claude path.
- Consent/no-surprise-network posture: where a surface supports consent (Claude MCP), it is ask-first;
  where the builder wires a direct call (a GPT Action), the schema descriptions carry the advisory and
  the builder is the one enabling it.
- No fabrication and no scraping of ToS-limited sources on any surface; ToS-limited values are
  null-flagged identically everywhere.
- Nothing in the deployed product writes to GitHub for end users on any surface.

## 6. The `## Cross-modality` declaration every skill carries
Add this section to each `SKILL.md`. Keep it short; reference this engine for the mechanics.

```
## Cross-modality
Class: B (offloadable)         # A pure-reasoning | B offloadable | C local-runtime
Runs on: Claude Desktop/Code (native); claude.ai + GPT + Gemini API (via <mechanism>); Gems: <no / knowledge-only>.
Mechanism: <MCP tool name> | <GPT Action file> | <Gemini declaration file> | public endpoint <url>.
Fallback: <the degrade ladder rung(s) this skill uses and what it asks the user for>.
See shared/cross-modality-engine.md.
```

## 7. Wizard integration
The setup wizard (`tools/wizard.py`) reads each skill's Class + Mechanism and, for the user's chosen
surface, prints the exact wiring steps (MCP config snippet, remote-MCP connector, GPT Action import,
Gemini declaration load, or the curl fallback), plus which skills are unavailable on that surface (the
Class-C-without-a-hosted-seam and the Gems dead ends). This is how a user "sets up" a capability on
their platform rather than discovering the gap at use time.
