# ADR 0059 — September currency: Plugins by their new name, and evidence before conformance

- Status: accepted
- Date: 2026-09-19
- Phase: P83 (September vendor-currency pass, Claude and OpenAI)

## Context

Nineteen days after the ChatGPT audit remediation, a scheduled currency sweep found fifteen of the
forty-six AI-surface seeds changed and twenty readable for the first time -- the Claude-side
authorities had been fetch-blocked since 2026-08-30 and cleared this week. OpenAI renamed the Apps
SDK to Plugins and moved the developer-mode toggle to Settings > Security and login, which made
two of the previous pass's excerpt-confidence tags closable at first-party quality. On the Claude
side, the plugin ecosystem's mechanics (marketplace precedence, org distribution limits, admin
controls, context-cost surfacing) became documented facts this repo distributes against.

## Decisions

1. Typed return models for the connector tools were tested under both supported MCP SDK majors
   and REJECTED on evidence: mcp 1.x None-pads absent TypedDict keys (an error response came back
   with five null contract fields) and breaks the structured/text mirror. The existing
   dict-annotated returns already declare an output schema on the wire under both majors, which
   is what the connector guidance asks; the wire selftest now pins that declaration and the
   non-empty-url citation rule instead of changing the return shape.
2. The `gpt-5.6` model alias stays in the examples. It is documented as a stable alias routing to
   GPT-5.6 Sol; the flagship (`gpt-6-astra`) is named in a comment rather than chased through
   four files. Revisit if the alias is deprecated; the GPT-5.5 retirement (2026-10-14) is tracked
   in moving-dates and does not touch the repo.
3. The skills frontmatter deviation is kept and documented rather than migrated: the Agent Skills
   spec's escape hatch for non-spec keys is `metadata`, a string-to-string map that cannot carry
   the repo's `load:` lists. The runtime tolerates the top-level keys today (Claude Code loads a
   skill body even on unknown metadata), the `agentskills-specification` seed watches the spec,
   and `claude plugin validate --strict` passes the tree. Revisit on any rejection signal.
4. Atoms-tier enumeration is recorded as UNVERIFIED-BY-RUNTIME. A real install through Claude
   Code v2.1.278 into a sandbox succeeded and the cache carries all 25 top-level skills and all
   106 atoms; whether the loader ENUMERATES the atoms (which sit one level below the documented
   skills/*/SKILL.md discovery depth) requires an authenticated session the sandbox cannot hold
   and the real user config must not be polluted to obtain. Standing stance until a runtime
   roster proves otherwise: atoms are internal composition units invoked through spokes'
   workflows, not user-invocable plugin skills. No restructuring of the atoms tier on an
   assumption.
5. `plugin.json` no longer carries `autoUpdate`: the runtime's own validator calls it an unknown,
   ignored field. Auto-update is a marketplace-level mechanism. The two manifest descriptions are
   now identical, because Claude Code prefers the marketplace entry's text and the pair had
   diverged -- the fuller text (what Creator OS is for) won over the inventory list.
6. The dead docs.anthropic.com seeds are re-pointed, not removed: removal changes the registry id
   set and triggers the freshness-bundle and projection cascade for a cosmetic gain. The
   google-drive-mcp-docs seed now shares a URL with claude-code-mcp-docs deliberately, recorded
   in its extraction hint, until their consumer sets are merged on purpose. The Claude Code
   release-notes seed resolves to an undated GitHub changelog, so its hint records that only
   version-header diffing can detect change there.
7. Deliberately not done: community-marketplace submission (outward distribution, the owner's
   call), Secure MCP Tunnel support, atoms restructuring, the three changed social-importer
   seeds (their consumer tools need their own review before a stamp blesses the new content),
   and the 404-page-with-widget-markers classifier edge found while probing dead URLs (a 404
   classified blocked stays conservative; watch item with the P82-9 fixtures as the pattern).

## Verification

Every vendor fact above was fetched from its canonical page on 2026-09-19 and the four registry
re-point targets were fetched through the repo's own getter and classifier before any registry
write was planned (all four classify as hashable content). The TypedDict rejection, the
schema-declaration proof, and the sandbox install are executed records in the session, not
predictions. The plugin validator passes --strict after the manifest changes.
