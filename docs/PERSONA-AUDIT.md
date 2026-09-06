# Persona Audit -- a repeatable check of the non-technical first run

Creator OS is built for creators, not developers. This is the protocol for verifying, on a schedule,
that a non-technical person can actually get through the setup wizard. It has two halves: a
machine-checkable harness (`tools/persona_audit.py`) and a human walkthrough recorded in a dated log.

**Scope, stated honestly:** this protocol covers the wizard's GET screens and the guided setup
journey — nothing else. Auditing everything beyond the wizard (the eleven cross-modality surfaces
including both Cowork modes, the CLI input-boundary classes, the per-surface empathy walkthroughs,
and the mandatory "what was NOT exercised" closing step) is governed by `docs/AUDIT-PROTOCOL.md`.

## The persona

**Alex** -- a YouTube creator. Comfortable in a browser and in creator dashboards; has never opened a
terminal, does not know what a "Python package manager" or an "OAuth client" is, and abandons a setup
the moment a step reads like code with no plain-language explanation or fallback.

Add personas as needed (e.g. a Windows-only creator, a Gemini-only creator), but Alex is the floor: if
Alex cannot finish, the flow fails the audit.

## What the harness checks (`tools/persona_audit.py`)

Read-only; it imports the wizard and renders every GET screen in-process (no server, no network, no
writes). Per screen:

- **Renders + has a heading** -- the screen loads and orients the user.
- **Offers a next action** -- a link to another screen, or a form/button. No dead-ends.
- **No leaked internal tokens** -- visible text never shows store/path identifiers like `local_fs` or
  `google_drive` that read as code.

Across screens it builds the link graph and flags **orphan routes** (reachable only by typing the URL).
`--selftest` exits non-zero on any render error, orphan, or token leak, so CI catches regressions.

## The stumble taxonomy (what the human walkthrough looks for)

The harness cannot judge tone. A human runs the happy path start to finish and records every stumble
against these categories:

1. **Jargon without a gloss** -- a developer term (uv, OAuth client, Business Account ID) with no plain
   explanation.
2. **Required install with no fallback** -- a step that needs software installed and offers no
   "skip / do it later / metadata-only" path.
3. **Dead-end** -- work that cannot be completed in the product (e.g. an auth step that is not wired up).
4. **Leaked internal token** -- a raw flag name or store identifier shown as the primary label.
5. **Decision overload** -- too many branches presented before the user knows enough to choose.
6. **Orphan / lost** -- a useful screen with no way in, or no clear "back".

## The rubric

Per screen and for the run overall: **green** (a non-technical user proceeds unaided), **amber** (they
proceed but meet friction -- jargon, a leaked token, an avoidable extra step), **red** (they are blocked
or lost). A run passes when the harness is green and every human-found stumble is either fixed or
explicitly triaged to the maintainer with a rationale.

## How to run it

```bash
python3 tools/persona_audit.py            # the machine report (green/amber/red per screen, orphans)
python3 tools/persona_audit.py --selftest  # CI gate: fails on render error / orphan / token leak
```

Then walk the happy path as Alex, record findings in a new `docs/persona-audit-<date>.md` (copy the most
recent one as a template), fix the low-risk stumbles, and list the structural ones for the maintainer.
Re-run after any wizard change.
