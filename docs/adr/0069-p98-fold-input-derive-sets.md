# ADR 0069 — Guards read normalised input, and pinned sets derive from the code that serves them

- Status: accepted
- Date: 2026-09-27
- Phase: P98 (remediation pass)

## Context

Guards that matched raw text could be steered around with an equivalent spelling: a brace
expansion or ANSI-C quoted option, a zero-width character inside a keyword, a URL-encoded host,
an Arabic digit in a proof label. Pins that covered hand-listed sets (dashboard endpoints, sed
write forms, shell step rules) stayed green when the set grew. P98 normalises input before every
match and derives pinned sets from the code that serves them, or pins an exact byte constant
where the surface is fixed.

## Decision 1: fold before matching

`tools/secret_scan.py` matches content against a folded copy of the text (NFKC, format
characters dropped, Unicode dash look-alikes and decimal digits read as ASCII) and a
percent-decoded copy; the audit-record name rule, the invariant 60 corpus unit splitter, the hub
heading reader, `commit_claims`' letter-folding and the proof resolver's digit reading use the
same fold. Session links match case-insensitively and through JSON-escaped slashes.
Authorization schemes beyond Bearer, PGP private-key armor, further well-known key-id formats
and pipeline dollar amounts with k/M suffixes or a USD prefix join the patterns; each rule
states its unread forms with a pinned case, and the widened patterns report zero new findings
on the tracked tree.

## Decision 2: pinned sets derive from the serving code, or are exact bytes

- The CI commit-hygiene step's run block must equal `_COMMIT_HYGIENE_RUN` byte-for-byte
  (invariant 61); the enumerated refusal list of shell forms is removed, and an edit to that
  step changes the constant in the same commit. Runtime env gating in parity moves to an
  allow-list.
- The dashboard and wizard endpoint pins derive their route sets from the handlers' own
  dispatch tables, with a self-check that the derived set matches what the server registers;
  a route added later is covered without editing the pin.
- Invariants 6 and 7 compare the hub's fenced spoke list with the route step's list in
  `workflow.json` and read workflow keys against a registry that refuses unknown atom-kind keys.
- A Claim-Proof trailer counts only inside git's trailer block; a boundaries record must name a
  resolvable symbol whether or not a gap is recorded.

## Decision 3: pins run the dispatch a person reaches

`setup.py`'s selftest runs the file as `__main__` for `--install-deps` (terminal and `--json`
stream shapes) under the process recorder, for the no-`.venv` and `.venv`-present paths; both
install helpers take the interpreter as a required argument and refuse a non-`.venv`
interpreter. The pip census keys sites by qualified name and reads keyword arguments, annotated
and chained assignments, dict values, bytes and walrus forms, with the remainder stated. The
`schedule_post` wrapper check compares the parsed call shape and the module's `json` binding;
the publishing default is pinned across scheduler passes; `dependency_currency`'s spawn refusal
derives from a documented set and its selftest-name skip binds to module level.

## Decision 4: the Bash guard reads a command as Bash builds it

Brace expansion, `$'..'` and `$".."` decoding, getopt-style `env` option parsing (`-S`
refused), Python on standard input (here-strings and piped `echo`/`printf` text checked, other
stdin sources refused), `set` with command arguments, expansion carriers, arithmetic and array
assignments, a sed program parser for `s///e` and `w`/`e` forms, hostname file options, and the
archive, xattr and 3.14 pathlib write names. The misses that remain are listed in
`KNOWN_MISSES`, each with a selftest line; `tools/tree_pin.py` stays the backstop.

## Consequences

- An equivalent spelling of a refused form now hits the same rule as the plain spelling, and a
  set that grows with the code is covered without editing its pin.
- The guard selftests grow to 315 checks (bash guard), 111 (secret scan) and 62
  (commit_claims); every widened rule carries its open set at the rule with a pinned case.
- The exact-byte CI step constant trades flexibility for closure: editing that step is a
  same-commit constant change by design.
- The source-shape pins read committed text: a later commit can rebind the checked symbols at
  runtime, and code review, the drift guard on the diff and `tools/tree_pin.py` govern that
  class, not the pins. Each pin states this limit at its site.
