# ADR 0076 — Windows runs the battery in CI; the hooks find a working Python, and the auditor's guard covers PowerShell

- Status: accepted
- Date: 2026-10-05
- Phase: P102

## Context

The git hooks and the auditor's PreToolUse hook ran `python3` by name. On Windows `python3` can be
the Microsoft Store alias, which exits non-zero without running Python. For the git hooks that
refused every commit. For the auditor's hook it meant the guard never ran, and Claude Code treats
a hook exit other than 2 as a non-blocking error, so the auditor's write would go through. The
hook also matched the Bash tool only, while Claude Code's PowerShell tool, on by default on
Windows, takes shell commands there.

No CI job ran on Windows. GitHub's `windows-latest` image gives an 8.3 short temp path; with a
short TEMP on a Windows computer, three selftest checks that compared realpath'd values with the
plain temp path failed, and one selftest's mutant pass ran close to the selftest sweep's 300 s cap.

## Decision 1: the hooks try python3, python and py -3, and fail closed where it matters

`tools/install_hooks.py` writes hooks that run the Python that installed them, then try
`python3`, `python` and `py -3`, and refuse the commit when none works, naming the remedy. The
auditor's hook command (`sync_check.GUARD_HOOK_COMMAND`, matched on `Bash|PowerShell`) tries the
same three names; with none working it refuses a call whose hook input names a guarded agent and
lets the main loop and the product agents through, as before. The command reads the hook input
once into a variable and runs each probe with its stdin closed, so a stand-in that reads stdin
cannot take the input the guard and the fallback read. The git hooks run their pinned Python only
when it starts, and pin the interpreter path as given.

## Decision 2: the auditor does not use PowerShell

The guard reads Bash syntax. `readonly_bash_guard.decide` refuses a PowerShell call from a guarded
agent, and the auditor's frontmatter removes the PowerShell tool. Drift invariant 14 requires the
matcher names, the frontmatter entry and each guarded agent named in the command's fallback.

## Decision 3: a Windows CI job runs the battery

`.github/workflows/ci.yml` runs `tools/battery.py` on `windows-latest` under Git for Windows'
bash, on Python 3.12 and 3.14. The Linux guard job keeps running each gate as its own step. The
selftest sweep reads per-tool caps from `selftest_sweep.TOOL_TIMEOUTS`, each with a reason.

## Consequences

- A clone keeps its old hooks until `tools/install_hooks.py` runs again.
- The no-Python fallback reads the hook input with `grep`, which Git for Windows ships; a shell
  without `grep` lets the call through.
- A probe that does not return lets the call through: a PreToolUse command hook that reaches its
  timeout (600 s by default) does not block the tool call (hooks reference).
- The command is POSIX sh. On Windows without Git Bash, Claude Code runs hooks under PowerShell
  (hooks reference), which does not read sh, so the guard does not run there (not tested on
  Windows); Git for Windows is part of `docs/SETUP_WINDOWS.md`.
- The Windows job adds a CI leg per interpreter; its first run on a push is the check for runner
  differences the Windows test computer did not cover (the workspace on another drive than the
  temp folder, the runner's speed, Python 3.12 and 3.14 on Windows).

```sources
[
  {"id": "claude-code-hooks-docs", "name": "Claude Code hooks reference", "url": "https://code.claude.com/docs/en/hooks", "category": "ai-surface-spec", "tier": "T1"},
  {"id": "claude-code-tools-reference", "name": "Claude Code tools reference", "url": "https://code.claude.com/docs/en/tools-reference", "category": "ai-surface-spec", "tier": "T1"}
]
```
