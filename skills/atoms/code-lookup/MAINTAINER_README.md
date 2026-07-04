---
file: skills/atoms/code-lookup/MAINTAINER_README.md
purpose: preserve the non-negotiable operating rules for code-lookup so it stays stable under iteration.
---

# code-lookup: Maintainer README

## Purpose
Resolves a residential requirement by topic and jurisdiction to the governing code section, the adopted
edition, and a free-viewer link. Its job ends at citation and edition status; it does not explain
technique (`construction-lookup`) or compute values (`build-calc`).

## Non-negotiable invariants
- Shared: references the pipeline (`shared/method.md`); self-checks against
  `protocols/quality-gates.md`; obeys `protocols/no-fabrication.md` and
  `protocols/formatting-metadata.md`.
- Skill-specific: edition status comes from `canonical-sources/construction/edition-status.json`, not
  memory; copyrighted code text and tables are never reproduced, only cited by section with a link to
  the free viewer (`shared/construction-engine.md`); Florida (2023 FBC 8th Edition) and North Carolina
  (2018 NC RC on the 2015 IRC, 2024 pending) are stated distinctly; every output carries the
  construction boundary (`protocols/safety.md`).

## Known failure modes
Stating the pending NC 2024 code as if enforced; guessing the adopted edition instead of citing
edition-status and deferring to the AHJ; pasting code text.

## Fragile fallbacks that must not become defaults
When a topic has no mapped section, pointing to the code landing page is acceptable; inventing a section
number is never acceptable.

## Regression cases to preserve
1. jurisdiction "fl" returns the 2023 FBC 8th Edition (2021 I-Codes) edition status.
2. jurisdiction "nc" returns the enforced 2018 code on the 2015 IRC and flags the pending 2024 code.
3. "egress" returns IRC R310 with the free-viewer link.
4. "deck ledger" returns IRC R507.9 (and DCA6 reference).
5. A request to quote code text is refused with a citation and viewer link instead.

## Approval-gated changes
Output schema, the edition-status source, engine loading, or atom wiring.

## Minority-report policy
For NC during the 2018-to-2024 transition, record both editions, state which is currently enforced, and
that the effective date is set by OSFM and the Residential Code Council.

## Update checklist
1. Confirm `edition-status.json` is current for FL and NC.
2. Spot-check the regression queries.
3. Run `python3 tools/sync_check.py`. Verify all backticked paths resolve.
