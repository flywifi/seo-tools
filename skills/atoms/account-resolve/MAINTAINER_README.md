---
file: skills/atoms/account-resolve/MAINTAINER_README.md
purpose: preserve the non-negotiable operating rules for account-resolve so it stays stable under iteration.
---

# account-resolve: Maintainer README

## Purpose
Resolve a creator's fuzzy brand phrase to one account record, or surface the choice when the
phrase is ambiguous. The matching is `tools/accounts.py` (offline, deterministic, `difflib`);
this atom is the thin contract around it. It reads only.

## Non-negotiable invariants
- Shared: references the pipeline (`shared/pipeline-engine.md`) and obeys
  `protocols/no-fabrication.md` (never invent an account not on the roster; null and gap instead).
- READ-ONLY. No write path exists; account mutations are the spoke/SKILL contract's job.
- Never auto-picks past a confident exact or alias match. A category match, a nickname, or two or
  more close candidates always returns `resolved: null` plus the ranked `candidates[]`. The human
  chooses; the atom never guesses which brand was meant.
- Every figure and match_basis comes verbatim from `tools/accounts.py`; the model computes no
  similarity score itself.
- Contact data is PII; when a resolver result leaves the machine, mask it (`--redacted`).

## Known failure modes
- Two brands sharing a prefix (Hearthline vs Hearthstone): both are substring candidates, resolved
  is null, the human disambiguates.
- A category-only phrase ("the lightbulb company"): the brand-category term map surfaces every
  brand in that category as a 0.5 candidate; it never auto-resolves.

## Fragile fallbacks that must not become defaults
- Picking the top candidate when `resolved` is null "to be helpful".
- Adding a nickname dictionary or phonetic matching; v1 is deliberately exact/alias/substring/
  difflib/category only, and every widening of that ladder is an approval-gated change.

## Regression cases to preserve
1. Alias hit resolves to a single account.
2. Shared-prefix phrase resolves to null with two candidates.
3. Category phrase resolves to null, resolution "category", the category brand in candidates.
4. Unknown phrase yields no candidates and a gap.
Mapped to evals/evals.json; the resolver math is pinned by `python3 tools/accounts.py --selftest`.

## Approval-gated changes
The tier ladder and its confidence floors, the never-auto-pick rule, the brand-category term map,
and the output schema.

## Update checklist
1. Edit SKILL.md / this file.
2. `python3 tools/accounts.py --selftest` passes.
3. `python3 tools/sync_check.py` exits 0; `python3 tools/scenario_check.py` stays green.
Verify all backticked path references in this file and SKILL.md resolve to real files on disk.
