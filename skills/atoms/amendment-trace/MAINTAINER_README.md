---
file: skills/atoms/amendment-trace/MAINTAINER_README.md
purpose: keep amendment-trace a source-grounded version tracer that quotes exactly, classifies each material difference with exactly one engine label, applies document source-precedence, and never rules on enforceability, validity, or which version legally controls.
---

# amendment-trace: Maintainer README

## Purpose
Trace two or more contract versions into a net current state view plus a labeled change_log,
watch_items, and conflicts. Read-only. Legal information only, never legal advice. It describes the
document record; it never decides which version legally wins.

## Non-negotiable invariants
- Emits the verbatim RESEARCH NOTES header (em-dash-free) as the first line of every output.
- Every difference in change_log carries exactly one label from shared/contract-engine.md: unchanged,
  clarified, expanded, narrowed, added, removed, contradictory, or uncertain. No coined labels, never
  two labels on one difference.
- operative_text, from_text, to_text, and every evidence_text are quoted exactly from a source version
  or null. Never paraphrased into a quote, never invented.
- Applies the engine's source-precedence order (final/operative, explicit amendment or side letter,
  referenced order form or exhibit, redline/comparison copy, conservative structural inference,
  otherwise missing/uncertain). resolved_by_precedence is document ordering only, never a legal ruling.
- Aligns by section number, then exact heading, then topic; weak alignment uses aligned_by "weak" and
  the uncertain label rather than a forced match.
- A topic dropped from the operative version is a removed entry with to_text null, not a silent gap.
- Never states or implies that a version is valid, controlling as a matter of law, or that a term is
  enforceable; never drafts binding language.
- Requires two or more resolvable versions; fewer returns insufficient_versions. Neither contract_id
  nor versions returns no_source. Unresolvable refs set provisional true and list in retrieval_gaps.
- human_review_required true; recommend_counsel true whenever anything is contradictory, uncertain,
  weakly aligned, or a version could not be resolved.
- Reuses usage-rights-check for per-version clause extraction; does not re-parse rights, exclusivity,
  ownership, or FTC language, and does not re-implement exclusivity-check.

## Known failure modes
- Ruling on which version legally wins or whether an amendment is valid or enforceable (a boundary
  violation): the atom must apply document source-precedence to name the operative wording and stop.
- Fabricating a second version, a version label, a date, or clause text to complete a trace.
- Forcing an alignment when section numbers and headings diverge instead of labeling uncertain.
- Attaching more than one difference label to a single change, or inventing a new label.
- Paraphrasing a clause into operative_text or evidence_text instead of quoting exactly.
- Dropping a removed topic instead of recording it as a removed change with to_text null.
- Re-parsing rights and FTC language instead of calling usage-rights-check.

## Regression cases to preserve
1. Amendment narrows exclusivity and adds a kill fee: change_log shows narrowed and added, operative
   text quoted from the later version, source_precedence_applied populated.
2. Renumbered/renamed sections across versions on the same topic: aligned_by weak, uncertain label,
   topic in watch_items, recommend_counsel true.
3. Only one version supplied: `{ "error": "insufficient_versions" }`; no invented second version.
4. Two undated drafts with directly conflicting payment terms: contradictory label plus a conflict with
   resolved_by_precedence null and both quotes in evidence_text; no enforceability claim.
5. A version supplied as an unresolvable ref: provisional true, ref in retrieval_gaps, only resolvable
   versions traced.
6. User asks which amendment is legally valid / overrides enforceably: the atom names the operative
   wording by document precedence and refuses any validity or enforceability ruling.

## Update checklist
- Run python3 tools/sync_check.py (must be clean).
- Verify the atom is composed by skills/contract-desk/workflow.json (a step and in shortcut_atoms).
- Verify shared/contract-engine.md still defines the eight difference labels and the source-precedence
  order this atom relies on; if the labels or ordering change, update the SKILL.md, the evals, and this
  README together.
- Confirm the contract_redline flag (which requires contract_management) still gates this atom and that
  creator-os-config.json degraded_behavior for contract_redline_disabled still describes the off state.
