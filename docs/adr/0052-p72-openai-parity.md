# ADR 0052 — OpenAI parity is one MCP server plus thin per-surface doors

- Status: accepted
- Date: 2026-08-15
- Phase: P72 (OpenAI surface parity)

## Context

The household's primary creator prefers OpenAI products, and the requirement is that Creator OS
works equally well on every OpenAI format: ChatGPT web, Projects, the desktop app, Codex (CLI,
desktop, IDE), MCP connectors, the API, and the 2026 plugin system. Research against OpenAI's
official documentation (2026-08-15; two agent sweeps plus direct fetches, every fact carrying its
URL in `docs/TRANSITIONS.md` and the connector runbook) found the existing packaging stale in one
load-bearing way and the landscape reshaped in three:

1. Custom GPT creation and publishing moved to Business/Enterprise/Edu workspaces; personal plans
   can use but not build GPTs (help.openai.com articles 8554397, 8798878 — excerpt confidence,
   the help site refuses direct fetches). Our GPT packaging targeted a door a personal account can
   no longer open.
2. The Assistants API sunsets 2026-08-26; the Responses API is the only forward path (recorded as
   a moving date backed by `openai-migrate-to-responses`).
3. On 2026-07-09 the App directory became a Plugin directory shared by ChatGPT and Codex; a
   "plugin" is now an MCP server plus optional UI, skills, and templates.
4. Codex consumes MCP servers on all its surfaces through one shared `config.toml`, including
   stdio servers, and reads repo-root `AGENTS.md` files with a 32 KiB combined budget
   (learn.chatgpt.com/docs/extend/mcp, /docs/agent-configuration/agents-md).

Measured in our own tree: the shipped custom instructions had never been paste-validated (one box
alone exceeded the old cap; the combined content exceeded the current cap under its stricter
reading), the MCP tool count machinery depends on the bare-decorator spelling, the cache CLI
prints to stdout (fatal inside a stdio JSON-RPC server), and the cache indexes gitignored
`.local.` files when present.

## Decision

One MCP server serves every OpenAI client; each surface gets only a thin artifact.

1. **The server satisfies the plain-connector contract.** `search` and `fetch` tools, shaped
   exactly per developers.openai.com/api/docs/mcp, back the no-developer-mode tier and deep
   research. They read the cache index directly over a read-only SQLite connection (never the
   printing CLI), refuse `.local.` records, and survive hostile FTS syntax by falling back to
   LIKE.
2. **Annotations are applied post-registration, with a completeness gate.** Decorators stay bare
   because the static count matches that exact spelling. Classification came from reading every
   tool body: eight tools mutate state (`schedule_post` alone is destructive-hinted); mutation-
   NAMED but pure tools live in an explicit verified-read list. Any mutation-signal name in
   neither list fails the selftest — and that gate caught a missed tool on its first run.
3. **ChatGPT Projects is the recommended personal-plan door**, replacing the Custom GPT as
   default guidance. The bundle reuses the eight surface-neutral knowledge files the Claude
   Project ships, so there is no second copy to drift.
4. **AGENTS.md is a registered projection of CLAUDE.md**, never hand-edited, hash-pinned by the
   projection manifest, and budget-checked against Codex's documented 32 KiB cap.
5. **External caps are machine-enforced.** `tools/surface_budgets.py` fails the selftest sweep
   when any packaged artifact exceeds a documented platform cap, citing the authority per budget.

## Alternatives considered

- **Per-surface servers or an OpenAPI Actions facade.** Rejected: N implementations drifting
  apart, and Actions live only inside Custom GPTs, which personal accounts can no longer build.
- **Custom GPT as the primary OpenAI door.** Rejected on the workspace-only creation change.
- **Plugin-directory submission.** Rejected for now: it requires a verified organization and
  review, and an unlisted connector delivers the same tools to one household without either.
- **Trusting excerpt-sourced numbers as fetched facts.** Rejected: help.openai.com figures are
  marked excerpt-confidence in the registry and the docs say "not officially documented" where
  OpenAI has published no number.

## Consequences

- Her ChatGPT setup is a five-minute Project creation plus file uploads, with three acceptance
  prompts; the maintainer's Codex and API access use the same server and the same honesty rules.
- Adding an MCP tool now requires classifying it (write or verified-read) or the build fails;
  the tool count in docs is invariant-checked, and a deploy that adds tools requires a connector
  refresh on connected clients (recorded in the runbook, since clients cache tool contracts).
- The unconfirmed numbers (consumer per-project file counts, per-field instruction caps, consumer
  Skills availability) are stated as unconfirmed wherever they appear, and the artifacts are
  sized under the worst confirmed reading, so none of them can invalidate a shipped door.
