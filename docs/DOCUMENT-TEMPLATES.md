# Document templates: the creator template runbook (P42)

How a creator turns their own documents into reusable, block-structured templates and assembles
future documents from them: contracts, rate-card display docs, analytics overviews, and
terms/conditions. Contracts support swappable clause blocks, so individual pieces swap in or out
per deal without touching the attorney's wording.

## The boundary, first

The system never authors document text. Assembly is mechanical (`tools/doctemplates.py`):
concatenate the selected blocks' stored bodies and substitute `[BRACKETED_FIELDS]`. Attorney-vetted
language enters the system only via creator upload and leaves it only verbatim (a byte-equality
selftest proves it). Swapping means whole blocks in or out; there is no partial rewrite, no
redline into vetted text, no improving wording. Assembled contracts and terms open with the
RESEARCH NOTES banner, carry `ready_to_sign: false` and `recommend_counsel: true`, and pass the
consequential-action gate before anything is sent or signed. Details:
`shared/doc-template-engine.md`.

## The walkthrough

1. **Upload an example.** "Turn this old contract into my template" routes as `template_manage`.
   `template-ingest` parses the upload (docintel + injection scan), extracts contract clauses via
   `usage-rights-check`, and returns a PROPOSED template: one block per clause with the exact
   quote, its clause family, provenance, and a confidence label; detected placeholders become
   bracketed `fill_fields`; alternative clauses for the same family become a `variant_group`.
   Spans that map nowhere land in `unmapped_text`, never dropped.
2. **You save it by hand.** Nothing is written automatically. Review the proposal, edit it, and
   save `pipeline/templates/<template-id>.local.json` (gitignored; the committed
   `*.template.json` starters are all-null shapes you can also copy). Mark `vetted: true` only
   when a licensed attorney has reviewed every `vetted_text` body. Use
   `python3 tools/doctemplates.py validate <id>` to check the structure and `diff` to compare a
   new proposal against what you saved.
3. **Assemble per situation.** "Draft the agreement from my template, paid usage this time, no
   exclusivity" produces a selections object (which blocks apply, which variant of each group,
   with a stated reason per swap), and `tools/doctemplates.py assemble` fills the brackets from
   your local data: profile (legal name, governing-law state), the deal record, the rate card, or
   a supplied analytics export. A value that does not resolve stays bracketed in the text and
   lands in `gaps[]` with the exact fix; nothing is ever estimated. Contracts route through
   contract-desk (flag-gated); rate cards, analytics overviews, and terms ride document-studio.
4. **The gate rules the release.** Every assembled artifact lists `blocks_used` with a provenance
   tag per block (`creator_vetted_text` | `plain_language_summary` | `data_fill`), carries
   `human_review_required: true`, and passes govern-artifact before it reaches you.

## Swappable clause blocks

Each contract block carries its clause family (usage rights, exclusivity, deliverables and
revisions, payment and kill fee, FTC disclosure, approval and veto, whitelisting, morality,
territory, and the finance families), advisory `conditions` describing when it applies, and
structural rules the code enforces: `variant_group` (exactly one alternative included, for
example organic-only vs organic-plus-paid usage), `never_with`, and `requires`. A selection that
breaks the structure aborts with named `selection_errors`; nothing is silently dropped.

## What unlocks what

| Switch or file | Effect |
|---|---|
| `document_templates` flag | persist assembled documents to disk (`--write`); read-only assembly, validate, list, and diff always work |
| `contract_management` + `contract_drafting` | additionally required to assemble contract and terms/conditions documents |
| `pipeline/templates/*.local.json` | your saved templates (gitignored; attorney text never enters git) |
| wizard `/brand-deals` | one-click flag enable + a saved-templates presence row |

## Privacy

`pipeline/templates/` is allowlist-inverted in `.gitignore`: everything is ignored except the four
committed all-null starters. Drift invariant 31 fails the build if a committed starter ever
carries a block body, a body_ref, real provenance, or `vetted: true`. Written documents must use
`.local.` paths. The same layered guarantees as the rest of the pipeline store apply (pre-commit
secret scan, invariants 19 to 21, CI fail-closed).

## ChatGPT and templates (read before pasting)

The template guarantees in this doc are CODE-enforced on your computer: byte-for-byte pass-through
of vetted text, structural selection rules, null-and-flag fills. On ChatGPT (or any paste surface)
none of that holds: the model there can rephrase, drop, or invent text, and nothing enforces the
authorship boundary. Two consequences:

- Pasting attorney-provided template text into ChatGPT means the P42 guarantees no longer apply to
  whatever comes back, and your contract's confidentiality terms may forbid the paste at all. Read
  `docs/PASTE-SAFETY.md` first.
- The supported pattern away from home is export-and-review: assemble the document ON your
  computer (or via a deployed remote MCP connector, which runs the tools at home), then carry the
  finished draft with you. Do not rebuild templates inside a chat.

## Verification

```bash
python3 tools/doctemplates.py --selftest     # 26 checks incl. vetted-body byte-equality
python3 tools/scenario_check.py              # S8 regression-locks swap/exclude assembly
python3 tools/sync_check.py                  # 50 invariants incl. starter purity
```
