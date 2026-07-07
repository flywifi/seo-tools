# Cross-Modality Correctness Audit (P39)

Audit of the `## Cross-modality` declarations added in P38-7, which were assigned by heuristic. This
phase re-derived each spoke's class from evidence and corrected the declarations. See
`shared/cross-modality-engine.md` for the class model and `docs/CROSS-MODALITY.md` for the surface
matrix.

## Method
Planned as an adversarial multi-agent audit (a classifier + an independent skeptic per spoke). The
workflow ran but hit an account session limit after 4 of 23 spokes; it was completed as a
**deterministic self-audit** (reading each spoke's `SKILL.md` + `workflow.json` + the composed atoms'
tool references + `tools/mcp_server.py`), **incorporating the 4 agent classifications that did
complete** (account-manager, analytics-compute, analytics-insights, audience-research). The
independent multi-agent skeptic pass is therefore **degraded**; the full adversarial run can be
re-run (`resumeFromRunId`) when budget resets if a second opinion on the borderline cases is wanted.

Class rule applied (from the engine doc): a spoke that runs a deterministic COMPUTE in a tool (or a
composed atom other than the shared `govern-artifact` gate) is **C**; one whose only non-reasoning
step is a DATA lookup (scoop cache / API) is **B**; pure reasoning is **A**. The shared
`govern-artifact` (score.py) gate is orthogonal (it is quality-review's own Class C) and does not make
every caller C.

## Corrections (2 class changes; all others: class kept, mechanism text made specific)

| Spoke | Declared | Final | Change | Why (evidence) |
|---|---|---|---|---|
| analytics-insights | B | **C** | class | composes `roi-metric` (CPM/CPC money math) + `ingest-route` (docintel CSV/screenshot parsing), not just a data lookup |
| partnership-mediakit | A | **B** | class | depends on `canonical-sources/rate-benchmarks/benchmarks.json` for accurate rate ranges; not pure reasoning |
| document-studio | A | A | kept | references `finance.py` only to *restate* a finance-built invoice record; computes no money itself |
| creator-core | A | A | kept, clarified | the router: classification is reasoning; the routed spoke carries its own class |
| account-manager, analytics-compute, construction-desk, content-distributor, contract-desk, deal-pipeline, deal-resourcing, finance-desk, quality-review, shortform-repurposing, task-desk, video-development | C | C | text | mechanism corrected to name the real module (accounts.py, build_calc.py, obligations.py, finance.py, tasks.py, score.py, publishing_compliance.py, ...) |
| audience-research, competitor-analysis, seasonal-trends, seo-keywords | B | B | text | verified: their atoms touch only the shared score.py gate, so genuinely data-backed reasoning |
| jurisdiction-desk | B | B | kept | hand-written exemplar (geometry/geocode/flood offload = B; offline engine = C convenience) |

Final distribution: **A = 4, B = 6, C = 13.**

## Doc-claim accuracy
The load-bearing claims in `docs/CROSS-MODALITY.md` (GPT Actions call public keyless REST; one
remote-MCP endpoint can serve Claude web/mobile + ChatGPT + Gemini; consumer Gemini Gems has no
custom-tool surface; claude.ai sandbox egress may be restricted; browser CORS varies) were sourced
from the P38-6 cited research and are already hedged in that doc's Caveats section. No overstatement
found to correct; the GPT-Action per-operation-`servers` caveat and the CORS/egress caveats remain
documented.

## Packaging candidates (flagged, NOT built this phase)
Per the decision, this phase corrected declarations only. When packaging is opted into later:
- **One remote-MCP deployment is the highest-leverage move:** `tools/mcp_server.py --serve-remote`
  surfaces ALL 13 Class-C skills (finance, tasks, construction, accounts, contracts, deals, video,
  ...) to claude.ai web/mobile, Custom GPT, and Gemini at once. This is the single biggest gap-closer.
- **Class-B skills are knowledge-pack candidates, not Actions:** their "endpoint" is the local scoop
  cache (canonical-sources data), so the natural non-Claude packaging is to ship the relevant
  canonical snapshot into the GPT/Gemini knowledge (with its as_of), not a live Action. jurisdiction
  is the exception (its data is a public GIS endpoint, so it got a real GPT Action).
- **Class-A skills need no packaging** (they run as reasoning on every surface, Gems included).

## Guard
Invariant 28 was hardened: a spoke declaration must carry `Class:` (A/B/C) + `Runs on:` + `Mechanism:`
+ `Fallback:` (a stub can no longer pass); every atom must carry the inherited one-line declaration.
