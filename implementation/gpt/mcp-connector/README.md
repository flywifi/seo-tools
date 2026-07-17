# Remote MCP connector runbook (ChatGPT, claude.ai, Gemini)

Creator OS ships a remote MCP transport (`tools/mcp_server.py --serve-remote`) that CAN serve
claude.ai, ChatGPT (developer mode), and Gemini from one deployed endpoint, IF you or your
developer host it. **This repo ships the server code and this runbook, not a hosted service, and
the server implements no authentication itself.** Never expose it without the protections below:
the endpoint reads your private local stores (deals, rates, contracts, templates).

## What YOU must provide

1. A machine that keeps running (your computer that stays on, or a small server) with your
   Creator OS folder on it.
2. A public HTTPS hostname in front of it (a reverse proxy such as Caddy or nginx handling TLS).
3. Authentication in front of the endpoint (an OAuth layer or at minimum a long random bearer
   token enforced by the proxy). The MCP server itself binds plainly and trusts the proxy. If you
   implement full OAuth to satisfy a provider's connector requirements, the current MCP spec
   (2025-11-25, Authorization) expects an OAuth 2.1 resource server: OAuth 2.0 Protected Resource
   Metadata (RFC 9728), PKCE with S256, the RFC 8707 `resource` parameter, token-audience
   validation, and HTTPS on every authorization endpoint. (Source:
   modelcontextprotocol.io/specification/2025-11-25/basic/authorization.)

## Start the server (behind the proxy, never directly exposed)

```bash
python3 tools/mcp_server.py --serve-remote --host 127.0.0.1 --port 8080
```

The proxy terminates TLS and auth, then forwards to 127.0.0.1:8080. Capability flags and consent
gates are enforced HERE, on this machine, for every surface that connects.

## Register the connector, per surface

- **claude.ai (web and mobile):** Settings, then Connectors, then add a custom connector with
  your HTTPS URL. Follow the on-screen auth flow.
- **ChatGPT web (developer mode):** Settings, then Connectors; enable developer mode if your plan
  offers it, then add the endpoint URL. [NEEDS VERIFICATION: developer-mode availability, the
  exact settings path, and auth support depend on your ChatGPT plan; check before relying on it.]
- **ChatGPT desktop app (developer mode):** same as web, from the desktop app's Settings, then
  Connectors. [NEEDS VERIFICATION: plan gating and connector scope.]
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
  dependable path. (Source: modelcontextprotocol.io/specification/2025-11-25/server/{tools,resources,
  lifecycle}.)

## Security notes

- Never run `--serve-remote` on a public interface without the HTTPS proxy and auth in front.
- The endpoint can read your gitignored local stores; treat its credentials like your own.
- Revoke the connector on the surface AND rotate the token when a device is lost.
- This runbook does not change the repo's rule: end-user deployments never touch GitHub.
