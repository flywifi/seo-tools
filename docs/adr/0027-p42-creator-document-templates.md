# 27. P42 Creator Document Templates

- Date: 2026-07-11
- Status: Accepted

## Context

Creators asked to upload contract examples and build reusable, creator-specific templates with individually swappable clauses. Separating template-assemble from contract-draft keeps the audited never-authors-legalese boundary intact: vetted text is creator-supplied and mechanically passed through, never generated.

## Decision

Built the creator document-template lane: block-structured, reusable templates for contracts, rate-card display docs, analytics overviews, and terms/conditions, with swappable clause blocks. Store: pipeline/templates/ gitignore-inverted (four all-null committed starters; real templates and attorney text only in gitignored .local files; drift invariant 31 enforces starter purity). Engine: shared/doc-template-engine.md defines the block model (kind, clause_family, fill_fields, applicability with advisory conditions plus code-enforced never_with/requires, variant groups for mutually exclusive alternatives) and the authorship boundary: the system never authors block body text; assembly is concatenation plus bracket substitution, proven by a byte-equality selftest. Tool: tools/doctemplates.py (stdlib, offline) validate/list/list-blocks/assemble/diff with fills from profile/deal/rate-card/export/manual sources, null-and-flag gaps, and writes gated by the new document_templates flag (contract types additionally behind the contract flags). Atoms: template-ingest (proposal-only, playbook-bootstrap discipline, exact-quote bodies via usage-rights-check, human saves by hand) and template-assemble (model selects whole blocks with reasons, code assembles; contract safety envelope preserved: banner, ready_to_sign false, profile_gaps). Wiring: template_manage hub classification to document-studio (template_proposal/from_template artifact types); contract-desk branches drafting to template-assemble when a vetted contract template exists, contract-draft stays the no-template path and reports availability. creator-profile.template.json gained legal_name/business_address/governing_law_state, closing the contract-draft profile_gaps mismatch. Regression: scenario S8 (swap the paid-usage variant in, exclude exclusivity, assert exact fixture sentences pass through and excluded text is absent) plus a 26-check tool selftest; wizard /brand-deals gained the flag switch and a saved-templates row.

## Consequences

Ledger status at record time: `accepted`. Source: `ledger/ledger.json` id `P42-creator-document-templates`.
