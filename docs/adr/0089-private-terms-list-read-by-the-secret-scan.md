# 0089. The secret scan reads a private list of the person's own terms, kept on their computer

- Date: 2026-11-21
- Status: Accepted

## Context

`tools/secret_scan.py` looks for secret formats, email addresses, phone numbers and amounts. It
has no way to know a person's name, their street or a handle, and `CLAUDE.md` says so. Those are
the words a creator most wants kept out of a public repository.

## Decision

1. The person lists their terms in `creator-os-private-terms.local.json` at the repo root, as
   `{"terms": ["...", ...]}`. The name ends `.local.json`, so git ignores it and drift
   invariant 19 refuses it as a tracked file. `tools/setup.py` creates it with an empty list.
2. `secret_scan.scan_text` looks for each term in every reading it already scans (tracked text
   through drift invariant 21, staged lines through the battery's staged scan and the pre-commit
   hook, commit messages through the commit-msg hook and the range scan). A term matches in any
   letter case, with a run of whitespace between its words, where it is not part of a longer run
   of letters or digits.
3. A finding names the term's position in the list and carries a hash of that position. The
   term, and a hash of the term, are not printed: a name is short enough to be guessed from its
   hash.
4. The allowlist does not exempt a private-term finding. The list is where a term is added or
   removed.
5. A list that does not parse, holds another shape, or holds a term under three characters is a
   finding, so a broken list fails the scan.
6. With no list, or an empty one, the scan prints `private terms: DID NOT RUN`, and the drift
   guard repeats it as an advisory.

## Consequences

- The check runs where the list is: on the person's computers. CI has no list and prints the
  DID NOT RUN line. Committing the terms, or hashes of them, to make CI check would publish what
  the list protects.
- The selftest uses invented terms in a temporary folder and runs with the list on the computer
  set aside, so its result does not depend on that list.
- Pull request titles, descriptions and comments are written on GitHub and do not pass through
  the scan.
- A term inside a longer word is not found, and a term is found only as its listed words in
  order: a name split across other words, or a nickname not on the list, is not found.
