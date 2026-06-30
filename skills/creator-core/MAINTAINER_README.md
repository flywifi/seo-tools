---
file: skills/creator-core/MAINTAINER_README.md
purpose: preserve the non-negotiable operating rules for creator-core so the hub does not drift into a content generator, a CRM writer, or a generic request handler.
---

# Creator OS Hub: Maintainer README

`SKILL.md` is the runtime control plane. This file is for anyone editing the hub so its behavior stays stable under iteration.

## Non-negotiable invariants

### 1. The hub classifies and routes; it does not generate
The hub's job ends at the routing object and human summary. It does not write content, fill deal records, or produce documents unless the user explicitly collapses classification and generation into one request. Any edit that makes the hub do spoke work by default breaks the architecture.

### 2. Three lanes stay separate
Content, Document, and Pipeline/CRM are distinct lanes with distinct engines and spokes. A request can span two lanes, but the routing object must identify them separately. Never collapse all three into "general request."

### 3. Pipeline-engine is the source of truth for all CRM data
No spoke, ingest connector, or user description may silently overwrite a record in `pipeline/`. The stage-transition rules in `pipeline-engine.md` govern all record changes. The hub enforces this before routing any Pipeline/CRM request.

### 4. Confidence and minority report are never optional on ambiguous requests
If the routing classification is not clearly supported, confidence must be `medium` or `low` and the reason must appear in the routing object. If an alternative routing is plausible and would lead to meaningfully different work, it belongs in `minority_report`, not a prose caveat.

### 5. Adaptation axes are inferred, not invented
The hub may infer skill level, tenure, budget tier, persona, and platform from context. If they cannot be inferred, they stay `unspecified`. The hub never assigns a persona the user has not signaled.

### 6. File-type confirmation is required before Document lane work begins
The hub must confirm the output file type with the user before routing to document-studio. This is a protocol requirement from `protocols/formatting-metadata.md`, not a suggestion.

### 7. Safe defaults list is enforced
See the safe-defaults section of SKILL.md. "Never default to a confirmed deal field value" and the other hard negatives are the most failure-prone lines in the hub. Do not remove or soften them.

### 8. Engine loading is scoped
Do not load `pipeline-engine.md` for a Content request that has no deal or account context. Do not load `platform-engine.md` for a document creation request. Unnecessary engine loading wastes context and introduces irrelevant constraints.

## Known failure modes
- Hub generates content instead of routing to the content spoke.
- Hub infers a persona when the user has not signaled one, leading to mismatched output.
- Hub treats an ingest connector signal (email, calendar mention) as a confirmed pipeline record.
- Hub collapses deal fields into prose descriptions rather than requiring structured input.
- Hub routes a Document request without confirming the file type, leading to a format mismatch.
- Hub hides routing uncertainty in hedged prose rather than recording it in the routing object.
- Hub routes a Content + Document multi-lane request to only one spoke without noting the secondary lane.
- Minority report is suppressed because "it would make the response longer."

## Regression cases to preserve
1. User asks for a content idea with no persona signal; hub routes to content-strategy with all persona_targets unspecified.
2. User says "add this brand to my deals"; hub routes to account-manager with pipeline_action set, not directly to deal-pipeline.
3. User asks for a media kit PDF; hub confirms file type before routing to document-studio.
4. User asks for a production plan on a deal that has not reached Signed stage; hub routes to deal-pipeline with a conflict noting the stage violation rather than proceeding.
5. User asks for a YouTube script and a Pinterest pin in the same message; hub routes to video-development as primary and notes shortform-repurposing (for the pin) as secondary.
6. Request is `unclear`; hub returns low-confidence routing with one targeted clarifying question, not a list of questions.
7. User provides analytics data; hub routes to analytics-insights and sets persona_targets based only on what the data supports, not on niche-typical defaults.
8. Ingest connector surfaces a new brand mention; hub routes to account-manager with confidence `low` and flags the field values as pending confirmation, not as confirmed record writes.
9. User asks "does this deal still have exclusivity active?"; hub routes to deal-pipeline (radar view) rather than guessing from deal notes.
10. A Content request has a budget constraint mentioned in passing; hub sets budget_tier in adaptation_axes rather than ignoring it.

## Approval-gated changes
Do not change these without explicit review:

- Request classification enum (adding or removing values breaks downstream skill routing).
- Lane definitions and which spokes belong to each lane.
- Source authority hierarchy.
- JSON routing object field names or types (downstream skills parse this).
- Safe defaults list.
- Engine loading rules (scoping decisions).
- Stage-transition enforcement rule for Pipeline/CRM routing.

## Validation checklist (run before any hub change ships)
- `SKILL.md` description still matches actual routing behavior.
- All spokes in the downstream list are real files in `skills/`.
- All engine references point to real files in `shared/`.
- All protocol references point to real files in `protocols/`.
- JSON routing object schema matches any downstream skill that consumes it.
- At least three regression cases above still pass against the updated hub.
- Drift guard (`tools/sync_check.py`) confirms no orphaned spokes.
