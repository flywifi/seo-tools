---
name: __SKILL_NAME__
description: "one or two sentences, third person, with the trigger phrases that should invoke this skill and an explicit Do NOT use for clause that points to the right alternative skill."
---

# __SKILL_NAME__

## When to use this skill
Specific trigger phrases and contexts. Include both explicit requests and implicit signals. State
what this skill does NOT do and which skill to use instead.

## Inputs
What the user must provide, what can be inferred, and what is retrieved automatically via engines.

## Core procedure
Follow `shared/method.md`. Compose atoms via `workflow.json` where present.

### Step 1: analyze
What happens, in instruction form.

### Step 2: generate
Pull voice and identity from `shared/brand-engine.md`, audience from `shared/audience-engine.md`,
specs from `shared/platform-engine.md`, and adaptation from `shared/adaptation-engine.md`.

## Output contract
What this skill produces. Always honor `protocols/formatting-metadata.md` (no em dashes, ranges with
"to") and self-check against `protocols/quality-gates.md` before handing to `quality-review`.

## Engines and protocols loaded
List only what this skill needs.

## Atoms used
List the atoms this skill composes, and the ones a user can call directly.

## Standalone usability
One sentence: what this skill produces even with no downstream skill available.

## Failure modes
Known ways this skill can fail or produce degraded output, and how it surfaces them honestly.
