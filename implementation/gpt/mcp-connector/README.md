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
   token enforced by the proxy). The MCP server itself binds plainly and trusts the proxy.

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

## Security notes

- Never run `--serve-remote` on a public interface without the HTTPS proxy and auth in front.
- The endpoint can read your gitignored local stores; treat its credentials like your own.
- Revoke the connector on the surface AND rotate the token when a device is lost.
- This runbook does not change the repo's rule: end-user deployments never touch GitHub.
