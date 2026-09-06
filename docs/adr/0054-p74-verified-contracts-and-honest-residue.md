# ADR 0054 — Verified contracts over plausible ones, and an honest residue over a silenced one

- Status: accepted
- Date: 2026-08-16
- Phase: P74 (remediation of the open P73 findings)

## Context

P73 audited the tree across six dimensions and left nine findings open, each with a written
reason. Working through them showed the residue was not one thing:

- **Two were blocked, not deferred.** Re-banding the currency intervals and giving the dependency
  checker a baseline both needed registry fields that no sanctioned CLI could write. Hand-editing
  the registry is forbidden, so the work was *unapplicable*, not merely unstarted. Filing that
  under "deferred" hid a missing tool capability behind an apparent scheduling choice.
- **Two documented controls were fictional.** ADR 0015 states the author-email rule is enforced by
  the commit-msg hook and the CI backstop. The hook half did not exist, and the CI half scanned
  `origin/main..HEAD`, which is empty once a push to main lands — so it reported success having
  examined nothing.
- **One was a decision the maintainer had not made yet**, namely whether to cut a release.

Two discoveries reframed the phase. First, planning it by *executing* its own example assertions
found a live production defect: `_extract_og_tags` built its regex with an unterminated character
class, so the property name was consumed inside the class, the pattern matched a single character,
and every `og_*` field received the first meta tag's content. Those columns are persisted to the
competitor snapshot index and surfaced to the creator, so a competitor's image URL was reported as
their title. Nine function contracts also differed from their obvious reading. Second, the reason
that defect survived: `parse_competitor_meta` had no selftest, and **nothing had ever executed its
logic**. Selftest *discovery* was scripted; *enrolment* was not.

## Decision

1. **"Executed on some path" is not coverage.** The defect lived in a module imported by another
   tool. Import proves a module loads; it does not assert its behaviour. Coverage is therefore
   reported in tiers — no runner at all, executed but unasserted, and itself a battery runner —
   rather than as a single flat number that treats `sync_check.py` as untested debt. Fifteen tools
   gained real selftests, chosen untrusted-input-first rather than by size, because a silent defect
   in a module that parses competitor pages, third-party editor files or remote responses reaches
   the creator as a fact.
2. **A missing writer is a finding, not a chore.** Where a correction cannot be applied through a
   sanctioned path, the missing capability is the defect. The three fields were added to the
   existing `update-source` verb rather than to a new script, because invariant 42 requires exactly
   five `save_registry` writers and a sixth would have traded one violation for another.
3. **Planning depth is a repo convention.** A plan carries who/what/when/where/why/how per work
   package, risks with concrete mitigations, citable evidence, and **code that has been executed
   and seen to pass**. A guessed contract is a defect in the plan. This ADR exists because the
   planning pass that followed that rule is what found the defect the audit had missed.

## What was deliberately left open, and why

Two findings are recorded rather than closed, because closing either meant choosing a policy on
the maintainer's behalf:

- **Selftest enrolment is still unenforced.** A tool can still ship with no selftest and nothing
  notices. Enforcing it means a build-failing gate plus an exemption list of roughly two dozen
  files, which is a standing constraint on every future change, not a repair of a present defect.
  The fifteen tests shipped; the gate did not.
- **The currency intervals are still declared as written.** 66 sources promise a sub-monthly
  cadence and 64 have never been checked once, because P36 retired the weekly job and no committed
  doc installs a replacement. Re-banding 63 of them to 30 days would make the registry honest, but
  it also picks a maintenance cadence. `docs/CURRENCY.md` states the finding and the two honest
  resolutions — install the scheduler, or re-band through the sanctioned writer — and the sanctioned
  writer now exists so either can be done in one command.

The general rule this records: **an advisory that is telling the truth should not be silenced by
changing the data it describes.** Picking a number that makes a warning stop is the same class of
defect as the warning itself.

## Alternatives considered

- **Writing selftests for all remaining files.** Rejected as a rebuild rather than a repair, and
  dishonest for the network-bound group: a selftest that cannot make a request either hits the
  network or asserts nothing. The right close is factoring their pure seams into testable helpers.
- **Blanket-raising every interval to silence the advisory.** Rejected, per the rule above.
- **Shipping the enrolment gate anyway.** Rejected: it fails the build on inattention, which is the
  point, but a guard that constrains every future change is the maintainer's call to accept.
- **A new maintenance script for the registry re-band.** Rejected: it would have become a sixth
  `save_registry` writer and tripped invariant 42.
- **Cutting the v0.2.0 tag.** Rejected: outward-facing and irreversible, and the maintainer's
  decision. The roll-up, the bump and the preconditions are prepared; the tag is not created.
- **Promoting the capability-parity check to blocking.** Deferred: it would turn an advisory into
  a build failure across a config surface this phase did not otherwise touch.
- **Rewriting ADR 0043**, which describes invariant 47 as CI-enforced within a fail-closed framing.
  Rejected: ADRs record what was decided and understood at the time. The live doc was corrected
  instead.

## Consequences

- The sweep went from 70 to 85 selftests, and the modules that read untrusted input now assert
  their contracts. The gap can still regrow by inattention, which is stated as an open finding
  rather than presented as closed.
- The version check now reads all five locations that carry the version. Widening the release
  preconditions is what exposed that it had been reading three and reporting "consistent" while
  the marketplace manifest disagreed — two guards had different definitions of the same word.
- `release.py execute()` can no longer tag an inconsistent tree, and no release after the first
  will be annotated as the baseline.
- The packaging stamp on the pasted ChatGPT pack is compared against the ecosystem version rather
  than merely required to exist. The bump to 0.2.0 would otherwise have left the pack reading
  0.1.0 while the wizard told the reader to re-export it — advice with no terminating state.
- Fixtures must use reserved example hosts and must not embed credential-shaped strings: three of
  the new selftests tripped the repo's own URL-provenance and secret-scan guards while being
  written, and each was fixed at source rather than allowlisted.
- Existing competitor snapshot rows written before the parser fix hold wrong values in `title` and
  the `og_*` columns. Repairing them needed its own change (P75), because a parser fix does not
  reach data a previous parser already wrote.
