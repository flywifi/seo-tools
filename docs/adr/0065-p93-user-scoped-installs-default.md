# ADR 0065 — Installs are user-scoped by default; machine-wide is a labeled choice

- Status: accepted
- Date: 2026-09-20
- Phase: P93 (install-scope pass)

## Context

The owner directed that anything Creator OS downloads or installs affects only the current
user, never the whole computer, as the default style for the entire repository. An audit
found the runtime already mostly user-scoped (the repo `.venv`, `~/.local/bin`, `~/Library`
config, whisper models under `~/.creator-os`), but two code paths wrote machine-wide when no
`.venv` existed (a pip system-override retry into Homebrew's shared site-packages, in
`setup.py`'s dependency installer and the wizard's uv step), 52 live-guidance lines
instructed machine-wide installs with no alternative or label, and nothing enforced the
policy, so it would have drifted back.

## Decisions

1. **Refusal over fallback, on ANY machine-wide interpreter.** With no `.venv` to install
   into, the installer refuses with the exact remedy ("run `python3 tools/setup.py
   --install-deps` to create the repo's private `.venv`") and never invokes pip at all. The
   first cut of this decision keyed the refusal on the PEP 668 "externally-managed-environment"
   string, which the adversarial pass proved insufficient: `install_dependencies` still fell
   back to `target = venv_py or PYTHON`, and a machine-wide interpreter that carries no PEP 668
   marker (a python.org framework build, `/usr/local`) accepted the write silently. Executed
   proof: under that code all seven requirements sets installed into `/usr/local/bin/python3`
   and reported success. Pinned fail-then-pass in the setup selftest (pip is never invoked; every
   set is refused), plus the PEP 668 fixture and a source pin over both modules.
2. **The label convention.** Machine-wide routes are kept, not deleted -- some users want
   Homebrew -- but every one sits under the literal label "machine-wide alternative (affects
   the whole computer)" within two lines, and the user-scoped route leads. The owner's
   directive governs defaults, not capabilities.
3. **User-scoped defaults.** Python: the interpreter already present, else the uv standalone
   installer into `~/.local` (no sudo, per its docs). Node (Microsoft 365 lane only): nvm
   into `~/.nvm` (per-user by design, per its README). Speech-to-text: `faster-whisper`
   inside the repo `.venv` via `--install-deps`; whisper.cpp stays as the labeled
   machine-wide alternative for Metal performance. GitHub CLI: not needed, the repo is
   public. The policy page is `docs/INSTALL-SCOPE.md`.
4. **The one exception, stated.** Apple Command Line Tools git is machine-level with no
   user-scoped equivalent and is usually preinstalled; it is registered as the exception
   rather than hidden. USING existing machine binaries (`env_paths.which` reading the
   Homebrew prefixes) remains allowed; ADDING to machine locations is what the policy
   forbids.
5. **Drift invariant 59 locks the words, over a DERIVED denominator.** `check_install_scope()`
   scans every tracked text file, minus an exemption map whose every entry carries a written
   reason (decision records, the changelog, the phase log, the ledger, dated audits,
   third-party evaluations, registry data, CI workflows, and the two files that hold detector
   vocabularies). The first cut scanned a hardcoded 16-file allowlist; the adversarial pass
   found live machine-wide instructions in six files outside it, including the repo-root
   double-click launcher. A closed list can only shrink silently. Labels govern downward
   only (a heading introduces its block, so it cannot bless the command above it), fenced
   `sources` blocks are citation data and are skipped, and every regex branch carries its own
   fail-then-pass fixture so deleting one fails the build rather than narrowing coverage.

6. **A route we recommend must be a route we can find.** Recommending user-scoped installs
   obliges the code to look where they land: `env_paths.augmented_path()` prepends
   `~/.local/bin` and each `$NVM_DIR/versions/node/<version>/bin` ahead of the Homebrew
   prefixes, and the launcher probes the versioned `~/.local/bin/python3.X` names uv writes.
   Without this the advice dead-ends: the wizard reported "Node.js not detected" after giving
   the user its own nvm command.

## Consequences

- A fresh setup on a multi-user or admin-restricted machine touches nothing outside the
  user's home folder; a second account on the same computer sees none of it.
- A future unlabeled `brew install` in guidance is a build failure, not a review nit.
- Machines that genuinely cannot create a `.venv` get an honest refusal with the remedy
  instead of a silent global write.
- Dated records (ADRs, CHANGELOG, audit records, the video-tooling evaluations) keep their
  historical third-party install facts; the invariant scans only the live guidance.
