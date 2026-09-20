# ADR 0063 — The wizard DOES the web setup: guided lanes that copy, stage, and verify

- Status: accepted
- Date: 2026-09-20
- Phase: P90 (web-surface doing pass)

## Context

The owner's verdict on the P89 documentation work: the wizard "does not need more words, it
needs more DOING especially for chat gpt... actual walkthrough menus and actual help and
things that it sets up for the user." ChatGPT exposes no local config surface the wizard can
write, so the automatable maximum is: prepare every artifact, validate it against the real
caps, stage the exact files, and verify the outcome from pasted evidence. An inventory pass
established the reusable rails (the first-run lane pattern, worker jobs, the token-gated
confirms, the `surface_budgets` box parser, the pack-file stager, the CSRF gate, the
auto-enrolling screen sweep) and three absences: no JavaScript anywhere in the wizard, no
text-level voice checker anywhere in the repo, and zero of the 128 skills self-contained
(every SKILL.md references repo-root `shared/`/`protocols/` files, so the claude.ai
skill-upload door shipped empty).

## Decisions

1. **Verdicts live in a module, not a handler.** `tools/paste_check.py` carries the three
   acceptance verdicts (routing and voice, no-fabrication, honest degradation) as pure
   functions with a hermetic fail-then-pass selftest, because POST handlers have no test
   harness and the sweep's enrolment gate is exactly the right forcing function. Verdicts
   advise with a stated reason and the human decides; two failures in a row mean the setup
   did not take.
2. **Guided lanes are parallel, not woven into the first-run chain.** `/chatgpt-setup` (plan
   picker, tailored door, copy blocks, staged bundle, paste-back verify) and
   `/claudeai-setup` (the four doors as actions plus the same verification) live as
   early-return routes with their own state keys, cleared by their own reset and by Start
   over. Lane nav may set benign progress state on GET, the precedent the first-run lane
   established.
3. **The wizard's first JavaScript is one page-authored copy function.** Clipboard copy
   cannot be done server-side; the function is static page code, every piece of rendered
   CONTENT stays `html.escape()`d (pinned), and the no-script-injection selftest guarantee is
   unchanged.
4. **The copied text and the validated budget agree by construction.** The lane splits the
   custom-instructions boxes with `surface_budgets._BOX_SPLIT` itself (import, not copy), and
   a pin asserts byte-for-byte agreement for both artifacts.
5. **Staging is an idempotent full rewrite under gitignored `dist/upload-bundle/`.** The
   bundle holds exactly what the plan fits (five knowledge files on ChatGPT Free, nine
   otherwise; nine plus the combined-file alternative for claude.ai), with a README inside
   and an Open-the-folder button; per-plan contents are pinned exactly.
6. **The skill-ZIP door becomes real via a standalone exporter.**
   `package_skill.py --standalone[-all]` bundles each skill's referenced engine/protocol
   files under `references/upstream/` inside the ZIP and rewrites the references in the
   packaged copy only (a build transform, same class as the combined pack; longest-reference
   first so rewritten paths are never re-hit). A dangling reference refuses rather than
   silently drops; the selftest first proves the plain-zip defect, then the fix. Sub-second
   for the whole roster, so the wizard button is synchronous.

## Consequences

A non-technical ChatGPT or claude.ai user clicks through menus, copies validated pastes,
drags one staged folder, and gets machine-checked pass/fail with fix advice instead of a
wall of steps naming repo paths. The Done page derives the web-surface lines at render time
(never stored prose). The persona audit covers the six new screens; the screen sweep grew
from 31 to 37; the acceptance-verdict corpus cites its voice-engine sections inline.
