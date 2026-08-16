# ADR 0053 — Production readiness is a stated yardstick, and guards must catch the next drift

- Status: accepted
- Date: 2026-08-16
- Phase: P73 (production-readiness audit)

## Context

The repo had no definition of "production ready". `protocols/quality-gates.md` defines release for
**artifacts** (nine dimensions, no dimension below 3, Integrity and Safety at 4 or above), but
nothing defined it for the system itself, so "is this ready?" had no checkable answer.

Two further problems shaped the phase. First, prior audits' findings had died with the sessions
that produced them: the phase's own commits shipped with no CHANGELOG, STATE, or ledger entry, and
a code comment referenced a finding id (`P73 D1-3`) with no committed referent. Second, the guard
set was consistently retrospective. Every guard added over the preceding phases detected the drift
that had already happened; the adaptability pass found five that would not catch the next one:
the Mac signal vocabulary was pinned against shrinking but not growing, the count-truth invariant
used a hand-curated enrolment list that had already been forgotten once, the projection manifest
hashed sources but never the projection's own bytes, and the citation guards recognised only full
URLs in specific containers.

Two safety defects were found that were live rather than theoretical. The MCP annotation gate
classified tools by matching their **name** against a mutation-signal list; a tool the list did not
anticipate silently inherited `readOnlyHint: True`, the hint clients use to skip a confirmation
prompt, while complete OAuth upload clients sit behind a flag waiting to be ungated. And
`configure_tool` treated an unparseable local config as an empty file and overwrote it, destroying
the remote token and publishing flags in a gitignored file with no recovery path.

## Decision

1. **State the yardstick in the report, and score against exactly it.** Five criteria derived from
   the repo's own artifact-gate philosophy: enforcement demonstrably enforces, safety boundaries
   hold, no dimension leaves open criticals, coverage is honestly bounded, and release mechanics
   are sound. The verdict separates "ready for use" from "ready to tag", because they turned out to
   be different answers.
2. **Classification is explicit, never defaulted.** Every MCP tool must be enrolled as a write, a
   mutation-sounding non-persisting call, or a verified read. A name that matches no pattern is an
   error, not a read. The signal list survives only to make the error message concrete.
3. **Guards must be shown failing.** Every guard this phase touched was made to fail and then
   restored, and where possible the failure case is a permanent selftest rather than a one-off
   replay — the synthetic unclassified tool now lives in the selftest forever.
4. **Enrolment is swept, not curated.** Any document stating a global count must be enrolled or the
   build fails, because relying on someone to remember had already failed once.
5. **Agent findings are claims until reproduced.** Every finding was re-derived by the main loop
   before it entered the ledger. This changed two conclusions and prevented two false fixes.
6. **The audit records what it did not do.** Open findings carry written reasons; the unexercised
   list states what this sandbox cannot reach; and the release stays the maintainer's decision.

## Alternatives considered

- **Adopting the artifact Quality Gates as the system yardstick.** Rejected: those score a
  deliverable's content (voice, evidence, formatting), not whether a build's guards enforce.
- **Fixing only the HIGH findings and deferring the structural ones.** Considered and explicitly
  overruled by the maintainer in favour of full scope. The four forward-coverage guards were the
  most valuable work in the phase, and three of them would have been deferred.
- **Writing selftests for all 37 uncovered tools.** Rejected as a rebuild rather than a repair.
  Recommended instead as a guard requiring new tools to declare coverage or be exempted with a
  reason.
- **Making the degraded-behavior parity check bidirectional and blocking.** Deferred: it would turn
  an advisory into a build failure across a config surface this audit did not otherwise touch. The
  exact six uncovered capabilities are named in the report so the fix is mechanical.
- **Hand-editing the registry to re-band unmeetable check intervals.** Rejected: it would violate
  the single-writer rule. The absence of a sanctioned verb for `check_interval_days` and
  `validated_version` is recorded as the actual finding.

## Consequences

- Adding an MCP tool now requires classifying it, and forgetting fails the build rather than
  producing a silently read-only annotation.
- A projection can no longer be hand-edited into disagreement with its source undetected, which
  matters immediately: this phase corrected `AGENTS.md`, which had carried a narrowed version of
  the registry single-writer rule for a full phase precisely because nothing watched it.
- Stating a count in a new document now requires enrolling that document.
- Two registry fields have no sanctioned writer, so two currency corrections are genuinely blocked
  rather than merely unstarted. That gap is now written down instead of being worked around.
- The release remains untagged by design. The version and CHANGELOG state would produce a tag
  describing a tree eleven phases out of date; the roll-up is prepared and the decision is the
  maintainer's.
