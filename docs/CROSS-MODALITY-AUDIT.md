# Cross-Modality Correctness Audit (P39)

Audit of the `## Cross-modality` declarations added in P38-7 (assigned by heuristic), corrected in two
passes: a deterministic evidence pass, then the full adversarial multi-agent audit. See
`shared/cross-modality-engine.md` for the class model and `docs/CROSS-MODALITY.md` for the surface
matrix.

## Method (final)
Two rounds. Round 1 (deterministic): evidence read of every spoke's SKILL.md + workflow.json +
composed atoms + tools/mcp_server.py, incorporating 4 early agent classifications; produced 2 class
fixes and specific mechanism text. Round 2 (adversarial, resumed after a session-limit interruption):
23 independent classifier agents (file:line-cited evidence) + skeptic agents challenging each
classification, completed across three resumed runs (session limits interrupted twice). Final
coverage: **23 of 23 classifiers and 23 of 23 skeptics.**

## Adversarial results
- **22 of 23 skeptics upheld** the classification they challenged (including every class change and
  jurisdiction-desk C, partnership-mediakit B, project-builder A, quality-review C at high confidence).
- **1 skeptic overturned a classifier over-call**: audience-research had been derived C (its
  ingest-route atom can run docintel parsing), but ingest is conditional (paste-source flows skip it)
  and the core is persona reasoning over data -> stays **B**. This is the distinction the audit
  settled: MANDATORY local compute makes a spoke C (document-studio); OPTIONAL/conditional compute
  does not (audience-research).
- **4 class corrections from the adversarial round** (all evidence-cited, all 4 skeptic-confirmed):

| Spoke | Was | Now | Why |
|---|---|---|---|
| content-strategy | A | **B** | trend-check is mandatory for any trend/seasonal claim: a web-intel data lookup (offloadable), not pure reasoning |
| deal-pipeline | C | **B** | its only tool (deal_status) is a read-only data lookup; stage transitions are rule reasoning per pipeline-engine.md |
| document-studio | A | **C** | mandatory local docintel ingest (classify.py/parse_text.py/transcripts.py) before any reasoning |
| jurisdiction-desk | B | **C** | the default path is deterministic local compute (geo_overlay point-in-polygon + the conflict cascade); the public-endpoint universal path is its Class-B rung. Skeptic-confirmed (high confidence) |

- Plus the 2 class fixes from Round 1 (analytics-insights B->C, partnership-mediakit A->B) and
  mechanism-text corrections across 16 spokes naming the real modules.

Final distribution: **A = 2 (creator-core, project-builder), B = 7, C = 14.**

## Skeptic coverage: COMPLETE (23/23)
All skeptics have run. The final five (seasonal-trends B, seo-keywords B, shortform-repurposing C,
task-desk C, video-development C) each upheld their classification. Every class in the repo matches
the audit's final verdicts; no unverified declaration remains.

## Doc-claim accuracy
The load-bearing claims in `docs/CROSS-MODALITY.md` (GPT Actions call public keyless REST; one
remote-MCP endpoint can serve Claude web/mobile + ChatGPT + Gemini; consumer Gemini Gems has no
custom-tool surface; claude.ai sandbox egress may be restricted; browser CORS varies) come from the
P38-6 cited research and remain hedged in that doc's Caveats. No overstatement found.

## Packaging candidates (flagged, NOT built)
- **One remote-MCP deployment** (`tools/mcp_server.py --serve-remote`) surfaces all 14 Class-C skills
  to claude.ai web/mobile, Custom GPT, and Gemini at once -- the single biggest gap-closer.
- **Class-B skills are knowledge-pack candidates**: ship the relevant canonical snapshot (with as_of)
  into GPT/Gemini knowledge rather than building live Actions. jurisdiction-desk's geometry rung is
  the exception (public GIS endpoints -> it has a real GPT Action).
- **Class-A skills need no packaging.**

## Guard
Invariant 28: a spoke declaration must carry `Class:` (A/B/C) + `Runs on:` + `Mechanism:` +
`Fallback:`; every atom carries an inherited one-line declaration (regenerated when a parent class
changes).
