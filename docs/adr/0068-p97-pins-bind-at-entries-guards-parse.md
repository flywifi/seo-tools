# ADR 0068 — Pins bind at the entry a person runs, and guards parse before they match

- Status: accepted
- Date: 2026-09-27
- Phase: P97 (remediation pass)

## Context

Several claim pins attached to the helper nearest the code they proved rather than the entry a
person reaches, so a wrapper above the pinned function could change behaviour while the pin
stayed green. Several small checkers read their sources with string shortcuts (a last-occurrence
split, a first-token option match, a first-line subject) where the consumer they mirror uses a
real parse. Pattern guards were proven only against fixtures their own author enumerated. Trust
boundaries keyed on signals their subject controls (committer dates, self-declared registry
states). One scan-set carve-out (heading lines) made a promise written as a heading invisible.
P97 addresses these classes and encodes the rules that keep them from recurring silently.

## Decision 1: a claim pin binds at the outermost property boundary

Every `::selftest::` proof in `tools/claim-proof-manifest.json` carries a `boundaries` record
naming the CLI entry, tool or runtime default its claim describes. Invariant 60 fails when the
record is missing, when it names a symbol its module does not define, and when no live code in
the pin's function calls that entry while the record states no gap naming it
(`docs/AUDIT-PROTOCOL.md` section 7.3). The install, publishing-default, human-confirmation,
schedule_post and dependency-currency pins now execute their entries: setup's selftest drives
`main()` with `--install-deps` under each `.venv` failure mode and records every process start;
the publishing default is resolved where the dashboard starts with the local override absent;
the five mutating dashboard endpoints and `schedule_post` run over filled and fuzzed bodies.

## Decision 2: checkers parse their sources the way their consumers do

Invariant 7 takes atom-name keys from the workflow JSON at any depth and requires each atom's
SKILL.md; invariant 6 reads the hub's single downstream heading and fence as the router does and
refuses a duplicate or shadow list; invariant 60 scans ATX heading text as its own unit and
re-validates exemption reasons that assert checkable repo facts, failing closed when the fact
source is unreadable. `commit_claims` checks git's real subject (the first paragraph as
`--format=%s` prints it), bounds its range by ancestry of `CLAIM_SUBJECT_BOUNDARY` with no date
cutoff and fails closed when the boundary commit is absent, skips only generated merge and
revert forms, and folds Unicode before detection. `battery` cuts shell comments where bash does,
matches gate commands as whole-step token lists with an exact interpreter word, and gates
BASH*/LD_* env names, case-variant checkout inputs, non-ubuntu runners and unmodelled strategy
shapes. `readonly_bash_guard` parses options as getopt does, git per subcommand grammar,
variable setters beyond NAME=, Python writes with an ast pass and heredocs with quote and
here-string awareness; what it still cannot see is listed in `KNOWN_MISSES` with selftest lines.

## Decision 3: pattern guards carry adversarial cases beside their fixtures

A new pin or detector branch lands with at least three falsifying mutations, chosen and run by a
reviewer who did not write it, committed as cases beside it; pins bound before this rule are
listed in the manifest's shrink-only `premutation_proofs`. Every change that removes text or
files from a guard's scan set ships a committed case for the removed set. An invariant that
enumerates a JSON file's keys takes them from its schema when one exists. The audit-record name
rule reads the path as git prints it (NFKC-folded, unquoted, keyword and date anywhere in the
path, widened date forms), and the finding-id, severity-tally, report-pointer and
discovery-narration vocabularies are committed patterns with their limits stated at each rule.

## Consequences

- A wrapper added above a pinned function, a second heading, a backdated commit, an
  option-cluster write form or a promise written as a heading now fails a committed check
  instead of passing silently.
- The stated limits (trailer relevance is reviewer judgment; earlier CI run-steps changing the
  checkout; the guard's ten known misses; word-pattern detection) are recorded next to the rules
  that carry them, each with a pinned case.
- The manifest grows `boundaries` and `premutation_proofs`; eleven pre-P97 pins carry written
  gaps their owning surfaces can close over time.
