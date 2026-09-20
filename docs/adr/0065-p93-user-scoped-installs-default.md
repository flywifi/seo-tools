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

1. **Refusal over fallback.** On a PEP 668 externally-managed interpreter with no `.venv`,
   the installer refuses with the exact remedy ("run `python3 tools/setup.py --install-deps`
   to create the repo's private `.venv`") instead of overriding into the shared
   site-packages. Proven fail-then-pass: a fake PEP 668 interpreter fixture in the setup
   selftest, plus a source pin asserting the override flag string is gone from both modules.
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
5. **Drift invariant 59 locks the words.** `check_install_scope()` scans the live guidance
   set for sudo package commands, `brew install`, `npm install -g`, the pip override flag,
   and command-anchored pip installs, and fails the build on any hit without the label
   within two lines. The detector self-proves on embedded fail-then-pass fixtures (including
   the two anchored-pip edge cases) before every scan, so a detector that cannot fail
   reports a problem instead of a verdict.

## Consequences

- A fresh setup on a multi-user or admin-restricted machine touches nothing outside the
  user's home folder; a second account on the same computer sees none of it.
- A future unlabeled `brew install` in guidance is a build failure, not a review nit.
- Machines that genuinely cannot create a `.venv` get an honest refusal with the remedy
  instead of a silent global write.
- Dated records (ADRs, CHANGELOG, audit records, the video-tooling evaluations) keep their
  historical third-party install facts; the invariant scans only the live guidance.
