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
   letter case, with nothing or a run of whitespace, dots, hyphens and underscores between its
   words, where it is not part of a longer run of letters or digits. The same look is made at
   the paths of tracked and staged files, at `tools/secret_scan.py` itself (whose other patterns
   are not run on it), and at the author's and the committer's name and address (the commit-msg
   hook and the range scan).
3. A finding names the term's position in the list and carries a hash of that position. A
   finding of another pattern whose matched text holds a listed term, and a path that holds one,
   are shown and hashed by that position too. These findings print neither the term nor a hash
   of it: a name is short enough to be guessed from its hash.
4. An allowlist entry does not exempt a private-term finding. The list is where a term is added
   or removed. The allowlist file's `commit_policy_boundary` applies as it does to the other
   patterns: commits at or before it are not scanned.
5. A list that does not parse, holds another shape, holds a term under three characters, is not
   a file, or is a link that leads nowhere is a finding in the scan's own run, in the commit-msg
   hook and in the push preflight, so a broken list fails them.
6. With no list, or an empty one, the scan prints `private terms: DID NOT RUN`, and the drift
   guard repeats it as an advisory. Where a checkout holds a list and the tracked scan does not
   finish, drift invariant 21 fails.
7. A linked git worktree with no list of its own reads the list at the root of the checkout it
   was made from.
8. A term's longest word is looked for first as plain text, and the term's pattern runs on a
   text that holds that word. Measured on this repository on 2026-11-23, the tracked scan took
   8.0 s with an empty list, 10.1 s with 200 terms and 57.7 s with 5000.

## Consequences

- The check runs where the list is: on the person's computers. CI has no list and prints the
  DID NOT RUN line. Committing the terms, or hashes of them, to make CI check would publish what
  the list protects.
- The selftest uses invented terms in a temporary folder and runs with the list on the computer
  set aside, so its result does not depend on that list.
- Pull request titles, descriptions and comments are written on GitHub and do not pass through
  the scan.
- The commit-msg hook's text changed with this decision; `python3 tools/install_hooks.py`
  installs it. A hook installed earlier still scans the message, and does not read the names or
  report a broken list.
- A person whose git `user.name` is on their list is refused at commit until they set a name
  they publish under.
- A term inside a longer word is not found, and a term is found only as its listed words in
  order. Not found: a spelling the list does not hold (an accent dropped or added, a look-alike
  letter from another alphabet, a curly apostrophe for a straight one), another word or a plus
  sign between the term's words, a line wrapped with a comment or quote mark between them, and
  a nickname not on the list.
