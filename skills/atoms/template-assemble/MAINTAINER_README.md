---
file: skills/atoms/template-assemble/MAINTAINER_README.md
purpose: preserve the non-negotiable operating rules for template-assemble so it stays stable under iteration.
---

# template-assemble: Maintainer README

## Purpose
Assembles a document from a saved doc-template: the model judges WHICH whole blocks apply (the
selections object with reasons); `tools/doctemplates.py` does everything that touches text
(structural selection validation, bracket fills, concatenation). Its job ends at the gated
artifact; templates are created via `template-ingest` + human save, and no-template contract
drafting stays with `contract-draft`.

## Non-negotiable invariants
- Shared: references the pipeline (`shared/method.md`); self-checks against
  `protocols/quality-gates.md`; obeys `protocols/no-fabrication.md` and
  `protocols/formatting-metadata.md`.
- The authorship boundary (`shared/doc-template-engine.md`): the atom never authors, rephrases,
  completes, or improves block text. A missing fill stays bracketed and gapped; the model's prose
  never enters a `vetted_text` block.
- Assembly is delegated to `tools/doctemplates.py assemble`; the atom presents the tool's output
  and never post-edits `document_text`.
- `selection_rationale[]` carries a stated reason for every exclusion and swap.
- Contract/terms outputs: RESEARCH NOTES banner line 1, `ready_to_sign: false`,
  `recommend_counsel: true`, profile gaps mirrored to `profile_gaps[]` with contract-draft field
  names.
- Manual fill precedence: deal_agreed then playbook_standard, labeled; never invented.
- `human_review_required: true` always; output passes through govern-artifact.
- Persistence is flag-gated (`document_templates`, plus the contract flags for contract/terms);
  the atom never bypasses the tool's gate.

## Known failure modes
- Structural selection violation: the tool aborts with `selection_errors`; the atom surfaces them
  verbatim and proposes a corrected selection.
- No saved template: report and point at template-ingest plus the committed starters.
- Missing source values: bracketed tokens + named gaps, never estimates.

## Fragile fallbacks that must not become defaults
- Assembling from a starter (all-null bodies) produces only gaps; acceptable solely as a shape
  demo, never presented as a document.
- `plain_language` blocks are creator-approved text saved in the template; treating them as
  editable at assembly time is forbidden.

## Regression cases to preserve
1. Variant swap plus exclusion assembles the right blocks; excluded text absent
   (evals: template-assemble-swap; scenario S8).
2. Vetted bodies pass through byte-for-byte apart from bracket substitution (doctemplates
   selftest; asserted via distinctive fixture sentences in S8).
3. Missing profile field stays bracketed, gapped, and mirrored to profile_gaps
   (evals: template-assemble-profile-gap).
4. Two variants of one group selected: selection_errors surfaced, no document text
   (evals: template-assemble-selection-error).
5. Contract banner first line + ready_to_sign false on every contract assembly (all evals).

## Approval-gated changes
The output envelope, the delegation-to-tool rule, the manual-fill precedence, and the
contract safety fields.

## Minority-report policy
When the deal record and the playbook point at different variants (for example the deal grants
paid usage but the playbook standard is organic-only), select from the DEAL (agreed beats
standard), state both signals in `selection_rationale`, and flag the divergence for deal-debrief.

## Update checklist
1. Edit SKILL.md and keep the envelope in sync with tools/doctemplates.py output and
   evals/evals.json.
2. Re-run the evals + `python3 tools/doctemplates.py --selftest`.
3. python3 tools/sync_check.py
Verify all backticked path references in this file and SKILL.md resolve to real files on disk.
