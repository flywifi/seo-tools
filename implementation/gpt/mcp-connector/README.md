# Remote MCP connector runbook (ChatGPT, claude.ai, Gemini)

Creator OS ships a remote MCP transport (`tools/mcp_server.py --serve-remote`) that CAN serve
claude.ai, ChatGPT (developer mode), and Gemini from one deployed endpoint, IF you or your
developer host it. **This repo ships the server code and this runbook, not a hosted service.** The
authentication boundary is your reverse proxy; the server adds two in-process backstops (P67-B) so
a misconfiguration cannot silently expose an open endpoint, but it is NOT a substitute for the
proxy. Never expose it without the protections below: the endpoint reads your private local stores
(deals, rates, contracts, templates).

**In-process backstops (defense in depth, not a replacement for the proxy):**
- Any network bind (`--serve-remote`, or a bare `--transport streamable-http`/`sse`) **refuses to
  start** when `--host` is a non-loopback interface and neither `CREATOR_OS_MCP_TOKEN` (nor
  `remote_mcp_token` in `creator-os-config.local.json`) is set and `--insecure` is not passed. This
  makes an accidental open, unauthenticated public bind impossible without an explicit
  acknowledgement, on every transport (P68-B closed a bypass where `--transport streamable-http`
  without `--serve-remote` skipped the check).
- When a token IS set, the server enforces an **in-process bearer gate** (`Authorization: Bearer
  <token>`, constant-time compared, 401 otherwise) in addition to whatever the proxy enforces.
- A loopback bind (`--host 127.0.0.1`, the documented pattern) needs no token: the proxy in front
  is the auth boundary.
- A loopback bind behind a proxy DOES need `--allowed-host YOUR-HOST` (or `remote_mcp_allowed_hosts`
  in the local config): the SDK's DNS-rebinding protection otherwise rejects the proxied Host header
  with 421. See "Start the server" below.

## What YOU must provide

1. A machine that keeps running (your computer that stays on, or a small server) with your
   Creator OS folder on it.
2. A public HTTPS hostname in front of it (a reverse proxy such as Caddy or nginx handling TLS).
3. Authentication in front of the endpoint (an OAuth layer or at minimum a long random bearer
   token enforced by the proxy). The MCP server binds to loopback and trusts the proxy; optionally
   set `CREATOR_OS_MCP_TOKEN` so it ALSO enforces the bearer token in-process (defense in depth).
   If you
   implement full OAuth to satisfy a provider's connector requirements, the MCP spec's
   Authorization model expects an OAuth 2.1 resource server: OAuth 2.0 Protected Resource
   Metadata (RFC 9728), PKCE (OAuth 2.1 mandates the S256 code-challenge method), the RFC 8707
   `resource` parameter, token-audience validation, and HTTPS on every authorization endpoint.
   (Source: modelcontextprotocol.io/specification/2026-07-28/basic/authorization; requirement
   list re-verified against the 2026-07-28 revision, 2026-09-12.)

## Start the server (behind the proxy, never directly exposed)

```bash
python3 tools/mcp_server.py --serve-remote --host 127.0.0.1 --port 8080 --allowed-host YOUR-HOST
```

`--allowed-host` (repeatable) or `remote_mcp_allowed_hosts` (a list) in `creator-os-config.local.json`
names the public hostname your proxy forwards in the Host header. The MCP SDK (1.28 onwards and 2.x
alike) enables DNS-rebinding protection for a loopback bind and allow-lists only loopback, so without
this every proxied request is answered `421 Invalid Host header` after the bearer gate has passed.
The server prints a warning at startup when no allowed host is configured. Direct loopback clients
keep working either way. Browser-based clients also need `--allowed-origin https://<their-origin>`
(or `remote_mcp_allowed_origins`); server-to-server proxies send no Origin header and need none. A
malformed value (a URL instead of a hostname, `*`, a string where a list is expected) stops the
server at startup with the reason.

The proxy terminates TLS and auth, then forwards to 127.0.0.1:8080. Capability flags and consent
gates are enforced HERE, on this machine, for every surface that connects.

## Register the connector, per surface

- **claude.ai (web and mobile):** available on Free, Pro, and Max (Customize, then Connectors,
  then Add custom connector) and on Team/Enterprise (an Owner adds it under Organization
  settings, then Connectors). Use the HTTPS URL ending in `/mcp`; a URL ending in `/sse`
  selects the older SSE transport. Authentication settings cannot be changed after a connector
  is added; remove and re-add to change them. (Source:
  claude.com/docs/connectors/custom/remote-mcp, fetched 2026-09-19.)
- **ChatGPT web (developer mode):** Settings, then Security and login, then turn on Developer
  mode; add the server at chatgpt.com/plugins (the plus button). Available on Pro, Plus,
  Business, Enterprise, and Education accounts on the web. On personal plans (including Pro),
  developer mode connects MCP servers with read and fetch permissions only; write and modify
  actions are a workspace beta (next card). MCP apps are web only, not available on the mobile
  apps. Agent mode does not use custom apps; deep research can, for read and fetch actions only.
  (Sources: developers.openai.com/api/docs/guides/developer-mode, fetched 2026-09-19;
  help.openai.com article 12584461, read in full 2026-09-19.)
- **ChatGPT workspaces (Business, Enterprise, Edu) -- custom MCP apps with write actions
  (beta):** an admin or owner must enable developer mode first (Business: each admin toggles it
  for themselves under Workspace Settings, then Permissions and Roles, then Connected Data;
  Enterprise/Edu: Settings, then Apps, then Advanced Settings, with RBAC to grant it to chosen
  members). Configure the app (endpoint, auth, Scan Tools), test it as a draft, then an
  admin/owner publishes it from Workspace settings, then Apps, then Drafts. Operational notes
  that matter for Creator OS deploys: (1) the workspace pins a frozen snapshot of the tool
  contract at approval -- after any deploy that adds or changes tools, an admin must hit
  Refresh on the app (Business plans cannot update a published app at all: recreate and
  republish); (2) if the server uses OAuth, the provider must issue refresh tokens (advertise
  `offline_access` in its discovery metadata) or ChatGPT loses access when the first
  authorization expires; (3) a server on a private network or dev machine cannot be added
  directly -- OpenAI's Secure MCP Tunnel runs an outbound-only `tunnel-client` beside the
  private server (tunnel_id from Platform tunnel settings; outbound HTTPS to api.openai.com:443
  only; supports developer-mode testing but not public plugin distribution).
  (Sources: help.openai.com article 12584461, read in full 2026-09-19;
  developers.openai.com/api/docs/guides/secure-mcp-tunnels, fetched 2026-09-19.)
- **ChatGPT desktop app (developer mode):** same as web (Settings, then Security and login;
  servers managed at chatgpt.com/plugins). The desktop app merged Chat, Work, and Codex into one app in July
  2026 (the previous app remains available as "ChatGPT Classic"); menu paths may differ between
  the two. [NEEDS VERIFICATION: plan gating, connector scope, and the merge details, which come
  from secondary reporting.]
- **Gemini (CLI / Agent Platform):** register the endpoint per Google's MCP client
  configuration. [NEEDS VERIFICATION: which Gemini surfaces accept remote MCP on your plan.]

## What becomes reachable

With a working connector, Class B and Class C capabilities run for that surface: the endpoint's
machine executes the tools, enforces the capability flags, and applies the consent gates. Without
a connector, every non-Anthropic surface is knowledge-only (Class A) via the pasted packs.

**Compute hand-off over this endpoint (P60 Transport C, opt-in).** When BOTH the
`remote_compute_endpoint` and `compute_handoff_enabled` capabilities are on, the endpoint also
registers `submit_compute_job` and `job_status`: a cloud session can queue an allowlisted local
job (transcription, library analysis, import previews, read-only finance reports) and poll its
result, live, without Drive latency. The same queue/runner as the Drive transports executes it, so
the same guarantees hold: allowlist-only, idempotent by job id, hub-confined inputs, nothing posts
or reads credentials from a job, results carry human_review_required. With either flag off, the
tools refuse with a plain message. See `docs/DRIVE-HUB.md`.

## Keeping a connected setup current (the update story for this path)

A connected setup is the only browser-AI path that gets true background updates: the AI calls your
live endpoint, so the moment you update the endpoint machine, every connected session serves the new
behavior on its next connect. To update: on the endpoint machine run `python3 tools/update.py` (or a
pull), then restart the server. That is the whole update; connected clients need no rebuild.

Two rules make this reliable, and one honest limit:

- **Keep the tool set small and STABLE; push all evolving content through tool RESPONSES.** Add
  capability by enriching what the existing tools return, not by adding or renaming tools. Neither
  claude.ai nor ChatGPT reliably picks up a changed tool list (the tool *contract*) on a live
  connection: claude.ai has served a stale cached tool list even across reconnect
  (github.com/anthropics/claude-ai-mcp #137), and ChatGPT requires the user to click **Refresh** on
  the connector in Settings after the tool list or descriptions change. If you must change the tool
  contract, tell users to reconnect or Refresh. `[NEEDS VERIFICATION: mid-session
  notifications/tools/list_changed and resources.updated honoring on claude.ai and ChatGPT.]`
- **Bump `serverInfo.version` every deploy.** The MCP `initialize` handshake exchanges
  `serverInfo {name, version}` at session start, so a version bump is the poll-able "this endpoint is
  newer" signal. It is observed only on a new session (a poll), never pushed into a live one. The
  `get_server_info` tool surfaces the running version so a client or a monitor can read it.
- **Content modeled as MCP resources** can use `resources/subscribe` + `notifications/resources/updated`
  for finer-grained refresh where the client supports it, but treat new-session re-fetch as the
  dependable path. (Source: modelcontextprotocol.io/specification/2026-07-28/server/{tools,resources,
  lifecycle}.)

## Security notes

- Never run `--serve-remote` on a public interface without the HTTPS proxy and auth in front.
- The endpoint can read your gitignored local stores; treat its credentials like your own.
- Revoke the connector on the surface AND rotate the token when a device is lost.
- This runbook does not change the repo's rule: end-user deployments never touch GitHub.


## Per-client connection cards (P72; every OpenAI client, one server)

Deploying a NEW tool set? Connected clients cache the tool contract: after any deploy that adds or
renames tools, use each client's "Refresh" on the connector (or remove and re-add it) or the new
tools stay invisible. Bump VERSION so `get_server_info` reflects the deploy.

### ChatGPT (her door: web, Plus/Pro)
Two tiers, same server:
- **Without developer mode (chat + deep research):** this server ships connector-contract `search`
  and `fetch` tools over the knowledge cache, the pair ChatGPT's connector contract is built
  around (developers.openai.com/api/docs/mcp). OpenAI no longer hard-requires search and fetch
  for connected servers generally (help article 12584461 FAQ, read 2026-09-19), but they remain
  what citations and company knowledge run on ("only apps with search/fetch functionality are
  included" in company knowledge), so this server keeps shipping them. Both return the payload
  twice, as structuredContent and as mirrored text content, per that contract. Both tools declare an
  output schema, and every result carries a non-empty `url`: ChatGPT creates citation metadata
  only when `url` is a non-empty string (developers.openai.com/api/docs/mcp, fetched
  2026-09-19). Add the connector by URL `https://YOUR-HOST/mcp`.
- **Developer mode (full tool set):** Settings -> Security and login -> turn on Developer mode,
  then add `https://YOUR-HOST/mcp` at chatgpt.com/plugins (available on
  Pro/Plus/Business/Enterprise/Edu on the web; developers.openai.com/api/docs/guides/developer-mode,
  fetched 2026-09-19, first-party documented). Write tools carry accurate
  `destructiveHint`/`readOnlyHint` annotations, so ChatGPT prompts for confirmation on
  `schedule_post` and friends -- that is the Creator OS human-confirmation invariant surfacing in
  ChatGPT's own UX.

### OpenAI Responses API (maintainer automation)
```json
{"model": "gpt-5.6", "input": "...",
 "tools": [{"type": "mcp", "server_label": "creator-os",
            "server_url": "https://YOUR-HOST/mcp",
            "allowed_tools": ["search", "fetch", "cache_query", "quality_score"],
            "require_approval": "always",
            "authorization": "Bearer <token>"}]}
```
`require_approval: "always"` maps the human-confirmation invariant onto the API: the model emits
`mcp_approval_request` and nothing runs until your code replies with an approval
(developers.openai.com/api/docs/guides/tools-connectors-mcp). The token is resent per request and
never stored by OpenAI. No fee beyond tokens. Note: `connector_id` is deprecated for models
released after 2026-09-01; use `server_url` (or `tunnel_id` for a Secure MCP Tunnel), and pass an
OAuth token via `authorization` when the server requires one (same page, fetched 2026-09-19).

### OpenAI Agents SDK
```python
from agents import HostedMCPTool
tool = HostedMCPTool(tool_config={
    "server_label": "creator-os", "server_url": "https://YOUR-HOST/mcp",
    "require_approval": "always"})
```
(openai.github.io/openai-agents-python/mcp/)

### Codex (CLI, desktop app, IDE -- one shared config)
`~/.codex/config.toml` (or project-scoped `.codex/config.toml`;
learn.chatgpt.com/docs/extend/mcp):
```toml
# local stdio -- the SAME server Claude Desktop runs, no hosting needed:
[mcp_servers.creator-os]
command = "/ABSOLUTE/PATH/seo-tools/.venv/bin/python3"
args = ["/ABSOLUTE/PATH/seo-tools/tools/mcp_server.py"]

# or remote:
# [mcp_servers.creator-os]
# url = "https://YOUR-HOST/mcp"
# bearer_token_env_var = "CREATOR_OS_MCP_TOKEN"
```
Or: `codex mcp add creator-os -- /ABSOLUTE/PATH/.venv/bin/python3 /ABSOLUTE/PATH/tools/mcp_server.py`

```sources
[
  {"id": "openai-connector-contract", "name": "Connect ChatGPT to MCP servers (search/fetch contract)",
   "url": "https://developers.openai.com/api/docs/mcp",
   "category": "ai-surface-spec", "tier": "T1"},
  {"id": "codex-mcp-config", "name": "Codex MCP configuration (config.toml)",
   "url": "https://learn.chatgpt.com/docs/extend/mcp",
   "category": "ai-surface-spec", "tier": "T1"},
  {"id": "openai-responses-mcp",
   "url": "https://developers.openai.com/api/docs/guides/tools-connectors-mcp"}
]
```
