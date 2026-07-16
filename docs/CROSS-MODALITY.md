# Cross-Modality Access (where/how a capability runs outside Claude)

Creator OS is authored as Claude Agent Skills, but a capability should be reachable from whatever AI
surface (or no AI) the user has. This doc is the per-surface map. The jurisdictional overlay is the
worked example; the same pattern (`shared/cross-modality-engine.md`) applies to every skill.

## The core idea: the universal path
Many capabilities can offload their heavy step to a **public server-side endpoint**, so any caller
that can make an HTTPS request gets the same answer. The jurisdictional overlay is the clearest case:
the ArcGIS / FEMA / U.S. Census endpoints do point-in-polygon and geocoding **server-side**, keyless,
so the model never needs a local GIS engine. The offline `tools/geo_overlay.py` engine is the
**privacy / no-network** path for surfaces that have a local runtime; the public REST is the
**universal** path for everything else.

## Per-surface matrix (jurisdictional overlay)

| Surface | Runs the offline engine? | Reaches the answer? | Mechanism | Packaged |
|---|---|---|---|---|
| **Claude Desktop (local MCP)** | Yes | Yes | `tools/mcp_server.py` -> `jurisdiction_resolve` (offline) + consent-gated live | `implementation/claude/desktop/` | <!-- verify: tools/mcp_server.py::jurisdiction_resolve -->
| **Claude Code / CLI** | Yes | Yes | Runs the tools directly, or `geo_source_fetch.py resolve` | native |
| **claude.ai web + mobile** | Sandbox-only | Yes | A hosted **remote-MCP** connector (`tools/mcp_server.py --serve-remote`) fronting the same tools | transport defined; you host it |
| **Custom GPT (OpenAI)** | No | Yes | A **GPT Action** whose OpenAPI schema targets the public endpoints | `implementation/gpt/actions/jurisdiction_overlay_action.yaml` |
| **Gemini API (developer)** | No (your backend does) | Yes | **Function calling**: Gemini emits the call, your app executes the HTTPS request | `implementation/gemini/jurisdiction-function-declarations.json` |
| **Gemini "Gems" (consumer UI)** | No | **No** | No custom-tool / outbound-call surface at all | dead end |
| **Human + curl / browser** | If they have Python | Yes | Curl the `/query` endpoint (browser may hit CORS; curl doesn't) | `tools/geo_source_fetch.py` |

**One honest dead end:** the consumer Gemini "Gems" UI has no custom-tool surface, so it cannot resolve
overlays from live data. A Gem user must paste a lon/lat, use the Gemini API, or use a hosted remote-MCP
connector.

## How each surface wires it

- **Claude Desktop:** add the MCP server from `implementation/claude/desktop/claude_desktop_config_snippet.json`.
  `jurisdiction_resolve(lon, lat, facts_json)` runs offline; the first live lookup in a session asks for
  consent (`geo_consent`), and a decline or headless run makes no call.
- **claude.ai web/mobile:** deploy `python3 tools/mcp_server.py --serve-remote` somewhere reachable from
  the provider cloud, then add it as a **custom connector** (remote MCP). One deployed endpoint CAN
  also serve ChatGPT (developer mode, web and desktop app) and Gemini, IF hosted behind HTTPS with
  authentication; the repo ships the server code and the runbook
  (`implementation/gpt/mcp-connector/README.md`), not a hosted service, and implements no
  authentication itself. ChatGPT registration steps carry needs-verification tags (plan gating).
- **Custom GPT:** in the GPT builder, add an **Action** and paste
  `implementation/gpt/actions/jurisdiction_overlay_action.yaml`. Auth = none (all endpoints are keyless).
  The GPT calls the public ArcGIS/FEMA/Census endpoints itself.
- **Gemini API:** load `implementation/gemini/jurisdiction-function-declarations.json` as
  `functionDeclarations`; when the model returns a call, your app makes the HTTPS request and returns the
  result. (A consumer Gem cannot do this.)
- **A human:** `python3 tools/geo_source_fetch.py resolve "809 E Amelia St, Orlando FL 32803"`, or curl
  the endpoints directly.

## Where capability flags are enforced (and where they are not)

Capability flags (`creator-os-config` capabilities) are evaluated only where the Creator OS
Python tools run: Claude Desktop/Code on your computer, your own Gemini API backend, or a
deployed remote MCP endpoint (which enforces them on ITS machine). On ChatGPT (web, custom
GPT, Projects, desktop without a connector) and Gemini Gems, nothing evaluates the flags:
they are at best text the model has read. Treat every gate as advisory on those surfaces,
and see docs/PASTE-SAFETY.md before moving private data there.

## Keeping a connected surface current (updates)
A hosted remote-MCP connector is the only browser-AI path with true background updates: update the
endpoint machine once (`tools/update.py` + restart) and every connected session serves the new
behavior on its next connect. Two rules make this hold, and one is a hard limit:
- Expose a **small, stable tool set** and push evolving content through tool **responses** (and MCP
  resources), never by adding or renaming tools. Neither claude.ai nor ChatGPT reliably picks up a
  changed tool contract mid-session: claude.ai has served a stale cached tool list even across
  reconnect (anthropics/claude-ai-mcp #137), and ChatGPT requires the user to click "Refresh" on the
  connector after the tool list changes. `[NEEDS VERIFICATION: mid-session list_changed /
  resources.updated honoring on claude.ai and ChatGPT.]`
- Bump the ecosystem VERSION each deploy; `serverInfo.version` (exchanged at MCP `initialize`, current
  spec 2025-11-25) is a poll signal read on a new session, never pushed into a live one. The
  `get_server_info` tool surfaces it. <!-- verify: tools/mcp_server.py::get_server_info -->

Knowledge-only surfaces (pasted packs, uploaded Project/GPT knowledge, Gems) never auto-update: the
`Packaging version:` line is the only staleness signal, compared by hand. Full runbook: docs/UPDATING.md.

## Boundaries that hold on every surface
- Every output carries the **advisory-not-legal-determination** boundary; genuine legal conflicts return
  `human_review_required` (a safety floor is never silently discarded).
- Live network is **ask-first** where the surface supports consent (Claude MCP); where it does not
  (a GPT Action, a Gemini backend), the *builder* is choosing to enable the call, and the schema
  descriptions carry the advisory + "planning only" language.
- No fabrication: values behind ToS-limited portals (Municode setback tables, ICC/FBC text) are
  null-flagged, not scraped, on every surface.

## Caveats
- **Browser CORS:** ArcGIS FeatureServers are usually CORS-enabled; FEMA/Census vary. Server-to-server
  callers (GPT Actions, a Gemini backend, an MCP host, curl) are unaffected.
- **claude.ai sandbox egress** to arbitrary hosts may be restricted; the remote-MCP connector is the
  reliable web/mobile route.
- **GPT Action multi-host:** the Action schema uses per-operation server overrides for the three hosts.
  If a GPT importer rejects that, split it into one Action per host (Census, Orlando ArcGIS, FEMA).
