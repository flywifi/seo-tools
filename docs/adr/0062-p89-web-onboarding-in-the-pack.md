# ADR 0062 — Web onboarding ships inside the knowledge pack, on the merged-Claude surface model

- Status: accepted
- Date: 2026-09-20
- Phase: P89 (cross-surface onboarding pass)

## Context

Claude on the web and ChatGPT on the web need to read the repo and walk a non-technical user
through setup, with the wizard's story holding across modalities. The walkthrough did not work: the knowledge pack contained zero setup content, its upgrade
pointer named a repo path a web user cannot open, and every "no terminal" doc began with "open
`implementation/...`" without saying how a person with no checkout obtains the file. By
2026-09-20 the surfaces themselves had also moved: on 2026-09-16 Anthropic merged
Claude chat and Cowork into one Claude (support article 16761823, staged rollout from Pro and
Max); claude.ai Projects gained a GitHub connector into project knowledge with manual sync
(support article 10167454); skill ZIP uploads are consumer-facing on every plan (support
article 12512180); and plugins install from any GitHub-URL marketplace on paid plans (support
article 13837440) — this repository already ships such a marketplace.

## Decisions

1. **Setup guidance ships INSIDE the knowledge pack** as a ninth knowledge file
   (`09-setup-and-surfaces.md`), because pack files are the only artifact that travels to the
   web surfaces; docs stay in a repo the web user cannot read. The file is registered in
   `projection_manifest.py` with the SETUP DOCS as its projection sources, so a change to any
   onboarding doc flags the pack file stale through the same invariant-47 machinery that
   guards engine projections.
2. **The claude.ai guidance is a four-door model, best first**: the plugin from the shipped
   marketplace (paid plans), a Project fed by the GitHub connector (manual "Sync now"), a
   Project fed by uploads (any plan), and individual self-contained skill ZIPs (any plan).
   Skills that reference repo-root `shared/` paths are documented as plugin-door-only, since a
   standalone ZIP severs those references.
3. **Every no-terminal entry doc states how the user obtains the files**: the maintainer sends
   them, the Drive hub `Knowledge/` mirror, the GitHub page, or the connector/plugin doors
   that need no files at all.
4. **The transitions surface roster is kept, not redesigned, during the staged rollout.** The
   three Claude rows carry dated merge notes; collapsing rows mid-rollout would misdescribe
   pre-merge accounts. Revisit trigger: the rollout reaching Free and Team plans.
5. **Unverifiable claims enter only as tags**: private-repo marketplace links on personal
   plans, the GitHub connector's plan gating, `claude_desktop_config.json` continuation after
   the vendor's pivot to `.mcpb` Extensions, and the `.skill`-extension acceptance on upload.
   None is asserted as fact anywhere.

## Consequences

The pack grows to nine knowledge files (eleven pack files with the system prompt and combined
pack); the count sweep touched every live "eight/8" claim, with frozen ADRs left as records. A
web Project can now answer "how do I set this up" with steps the user can actually take, and
the wizard's claude.ai screen and WIZARD.md describe the merged-Claude doors instead of only
the Google connector.
