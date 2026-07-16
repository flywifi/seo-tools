# 28. P43 Chatgpt Surfaces And Transitions

- Date: 2026-07-12
- Status: Accepted

## Context

The audit showed OpenAI coverage was really custom-GPT-Action coverage, the ChatGPT desktop app was unknown to the repo, a load-bearing remote-MCP claim was documentation without an artifact, and no one owned transitions. The fixes ship runbooks, honest claims, and a data-driven transition guide rather than hosting or auth theater; unverifiable product facts are tagged, never asserted.

## Decision

Fixed all 17 errors from the ChatGPT-surface audit and made the wizard walk non-technical users through any modality setup and transition. Single source of truth: shared/cross-modality/transitions.json (9 canonical surfaces incl. ChatGPT plain web, custom GPT, Projects, and the desktop app; 14 authored pair overrides; unverifiable OpenAI product claims tagged NEEDS VERIFICATION), mirrored by docs/TRANSITIONS.md and enforced by drift invariant 32 (matrix/doc/wizard-key consistency, packaging stamps, spoke-fallback ChatGPT tokens). Wizard: four-way welcome (Claude / ChatGPT / Gemini / more than one), a /chatgpt hub with per-flavor numbered steps, a /transitions screen rendering what travels, what stops working, and what to re-import for any pair (authored or honestly derived), a local-machine precondition banner on every writing screen, and page titles made em-dash-free. Honesty: every one-remote-MCP-endpoint-serves-ChatGPT claim reworded to CAN-serve-IF-deployed-behind-HTTPS-with-auth with the no-built-in-auth fact stated; deployer runbook at implementation/gpt/mcp-connector/README.md incl. ChatGPT web and desktop developer-mode registration. Reconciliation: connectors.json gained option_d2_chatgpt_connected (conditional Drive/MCP) resolving the freshness-matrix contradiction; the freshness screen states its choice only affects the local store. Profile import landed: implementation/gpt/profile-import prompt (per-context, per-field provenance) plus the proposal-only profile-import atom (named conflicts, injection containment, human saves) and provenance fields in the profile template. Privacy: docs/PASTE-SAFETY.md data classes, the DOCUMENT-TEMPLATES ChatGPT section (P42 code guarantees do not hold off-runtime), consent-asymmetry acknowledgment on the GPT Action, a flags-enforcement map, and packaging version stamps with a re-sync procedure. All 23 spoke Fallback lines now name their ChatGPT degradation path.

## Consequences

Ledger status at record time: `accepted`. Source: `ledger/ledger.json` id `P43-chatgpt-surfaces-and-transitions`.
