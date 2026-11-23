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
   hook and the range scan). Paths are read as git stores them (`-z` listings; a diff header's
   quoting and the tab git puts after a name with a space are undone) and as UTF-8 with a byte
   that is not UTF-8 kept, so a file whose name is outside UTF-8 is scanned under its own name.
   git's output is decoded from its bytes, so a carriage return in a name or a line stays one.
   The patterns then read a carriage return as a line end, so a credential on a line that ends
   in CR LF is found in staged lines, tracked text and commit messages.
   The staged diff is read with fixed options: colour off, git's own diff program, the stored
   text and not a converted one, the `a/` and `b/` prefixes, and a file read as text where an
   attribute marks it `binary` or `-diff`. Run with git on 2026-11-23, the staged findings were
   the same under `color.ui`, `diff.noprefix`, `diff.mnemonicPrefix`, `diff.srcPrefix`,
   `diff.external`, `diff.context`, `diff.renames`, `core.quotePath` and those two attributes;
   other settings were not run. An added line is ended by a line feed alone, so text after a
   form feed, a carriage return or a line separator inside it is read. A term is read in
   composed form (NFKC), as the text is, so a term saved with a separate accent mark and its
   usual spelling are one term.
3. A finding names the term's position in the list and carries a hash of that position. A
   finding of another pattern is shown by that position too when its matched text, or the 40
   characters either side of it, holds a listed term's words; for this the words count
   wherever they stand, also inside a longer run of letters or digits. The report prints no
   hash for such a finding; an allowlist entry for it pins the sha256 of the matched text, as
   for a finding shown in full. The 40 characters are a limit: where a term's other word
   stands further from the match than that, the match is printed. A path that holds a term is
   shown as `(hidden path N, holding term M ...)` in the findings of that file, N counting the
   hidden paths of the run, and a message about an allowlist entry with such a path is shown
   by position. The commit-msg hook veils the lines it prints the same way; a line of the
   claim check, which quotes the subject in its own spelling, is veiled when the message holds
   a term. A name is short enough to be guessed from its hash, so the term is not hashed
   either.
4. An allowlist entry does not exempt a private-term finding. The list is where a term is added
   or removed. The allowlist file's `commit_policy_boundary` applies as it does to the other
   patterns: commits at or before it are not scanned.
5. A list that does not parse, holds another shape, holds a term under three characters
   (counted in composed form), is not
   a file, or is a link that leads nowhere is a finding in the scan's own run, in the commit-msg
   hook and in the push preflight, so a broken list fails them.
6. With no list, or an empty one, the scan prints `private terms: DID NOT RUN`, and the drift
   guard repeats it as an advisory. Where a checkout holds a list and the tracked scan does not
   finish, drift invariant 21 fails.
7. A linked git worktree with no list of its own reads the list at the root of the main
   worktree, the first entry of `git worktree list`, when that entry is a checkout (a folder
   that holds `.git`). A worktree of a bare repository, and one of a clone made with
   `--separate-git-dir` (for which git names its git folder there), read their own root and
   print DID NOT RUN when it holds no list. In those two layouts `tools/install_hooks.py`
   finds no `.git/hooks` folder and installs nothing, so a commit made there runs neither
   hook; `python3 tools/secret_scan.py --staged` is run by hand there.
8. A term's longest word is looked for first as plain text, and the term's pattern runs on a
   text that holds that word. Measured on this repository on 2026-11-23, the tracked scan took
   8.0 s with an empty list, 10.1 s with 200 terms and 57.7 s with 5000, for terms of two
   invented nine-letter words. The longest word of a term decides the cost: 300 terms of two
   common three-letter words took 142.8 s, since nearly every file holds such a word.

## Consequences

- The check runs where the list is: on the person's computers. CI has no list and prints the
  DID NOT RUN line. Committing the terms, or hashes of them, to make CI check would publish what
  the list protects.
- The selftests use invented terms in temporary folders and run with the list on the computer
  set aside (the hook's selftest runs the hooks in a stand-in repository that holds copies of
  the tools), so their results do not depend on that list.
- Pull request titles, descriptions and comments are written on GitHub and do not pass through
  the scan.
- The commit-msg hook's text changed with this decision; `python3 tools/install_hooks.py`
  installs it. A hook installed earlier still scans the message, and does not read the names or
  report a broken list.
- A person whose git `user.name` is on their list is refused at commit until they set a name
  they publish under.
- A term inside a longer word is not found, and a term is found only as its listed words in
  order. Not found: a spelling the list does not hold (a letter that differs by an accent, a
  look-alike letter from another alphabet, a curly apostrophe for a straight one), another word or a plus
  sign between the term's words, a line wrapped with a comment or quote mark between them, and
  a nickname not on the list. Four characters are the exception, since Python reads them as
  the plain letter when letter case is ignored: the dotted capital I (U+0130) and the dotless
  i (U+0131) as i, the long s (U+017F) as s, and the kelvin sign (U+212A) as k.
- The names and addresses a commit is made under are checked with the term's own pattern, so a
  name that runs into digits in an address (a number straight after the name) is not found
  there.
