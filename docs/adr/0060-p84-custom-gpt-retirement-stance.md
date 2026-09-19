# ADR 0060 — Custom GPT retirement: keep export-gpt, steer new setups elsewhere

- Status: accepted
- Date: 2026-09-19
- Phase: P84 (walled-page banking pass)

## Context

The user hand-delivered browser saves of the help.openai.com articles the container cannot fetch
(Cloudflare challenge on datacenter egress). The Creating-and-editing-GPTs article (8554397, read
in full) states that Custom GPTs are being retired in favor of Plugins: Enterprise workspaces on
2026-12-11 (public GPTs from affected workspaces included even when used from other plans), a
migration flow targeted for 2026-09-17, and "other plans are expected to follow the same
timeline." The repo ships an export-gpt atom, a Custom GPT transition door, and Actions packaging
that all target the GPT Builder.

## Decision

The export-gpt atom stays, unchanged in function, carrying a retirement notice. Workspaces keep
their GPTs until retirement and the atom's output (dense instruction file + knowledge files) is
exactly the material the announced migration flow would carry into a Plugin. The transition door
and the atom banner now steer NEW setups toward the ChatGPT Project or the MCP connector door,
and the date is machine-tracked in `canonical-sources/moving-dates.json` (`custom-gpt-retirement`,
effective 2026-12-11), so drift invariant 43 raises the took-effect advisory if the date passes
unverified.

Revisit triggers, whichever lands first: the migration flow becomes observable in a workspace
(evaluate whether export-gpt should emit Plugin-shaped output instead), or the non-Enterprise
retirement date is announced (extend moving-dates and reconsider whether the atom's description
still names a live surface).

## Consequences

- No packaging is deleted while the surface still works; users on workspaces lose nothing today.
- The repo will not be surprised in December: the moving date drives the advisory, and the
  registry source (`openai-gpt-creation-policy`) is on the browser-handoff list for re-checks.
- The Actions YAML (`implementation/gpt/actions/`) inherits the same horizon; it is not
  deprecated here because the article ties retirement to GPTs, not to Actions in general (the
  GPT Actions production guide remains live, per the P83 PASS ledger).
