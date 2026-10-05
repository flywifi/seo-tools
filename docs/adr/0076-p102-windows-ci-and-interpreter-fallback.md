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

No CI job ran on Windows. On GitHub's `windows-latest` image the temp folder is an 8.3 short path,
which three selftest checks compared with realpath'd values and failed on, and one selftest's
mutant pass ran close to the selftest sweep's 300 s cap on a Windows computer.

## Decision 1: the hooks try python3, python and py -3, and fail closed where it matters

`tools/install_hooks.py` writes hooks that run the Python that installed them, then try
`python3`, `python` and `py -3`, and refuse the commit when none works, naming the remedy. The
auditor's hook command (`sync_check.GUARD_HOOK_COMMAND`, matched on `Bash|PowerShell`) tries the
same three names; with none working it refuses a call whose hook input names a guarded agent and
lets the main loop and the product agents through, as before.

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
- The Windows job adds a CI leg per interpreter; its first run on a push is the check for runner
  differences the Windows test computer did not cover (the workspace on another drive than the
  temp folder, the runner's speed, Python 3.12 and 3.14 on Windows).

```sources
[
  {"id": "claude-code-hooks-docs", "name": "Claude Code hooks reference", "url": "https://code.claude.com/docs/en/hooks", "category": "ai-surface-spec", "tier": "T1"},
  {"id": "claude-code-tools-reference", "name": "Claude Code tools reference", "url": "https://code.claude.com/docs/en/tools-reference", "category": "ai-surface-spec", "tier": "T1"}
]
```
