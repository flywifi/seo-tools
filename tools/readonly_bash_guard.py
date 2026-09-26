#!/usr/bin/env python3
"""Refuse write-capable shell commands from the read-only auditor agent (PreToolUse hook).

Wired in `.claude/settings.json` as a PreToolUse hook on the Bash tool. Claude Code sends the hook
a JSON object on stdin; inside a subagent that object carries `agent_type` (the agent's frontmatter
`name`). The guard acts only when `agent_type` is in GUARDED_AGENT_TYPES and otherwise exits 0 at
once, so the main loop and the product agents are unaffected.

For a guarded agent it parses the command and refuses (exit 2, reason on stderr) when it finds:
  - output redirection to anything but /dev/null or another file descriptor;
  - an environment assignment (VAR=..., env VAR=..., export VAR=...) outside SAFE_ENV_VARS:
    GIT_EXTERNAL_DIFF, GIT_CONFIG_*, LESSOPEN and similar variables make a read command run a
    program;
  - command substitution, process substitution, or backquotes (the inner command is not visible);
  - a command that is not on the read-only list (rm, mv, cp, tee, pip, curl, sh -c, xargs ...);
  - a git subcommand outside the read-only set, or a read-only one with a write option;
  - sed -i or a sed w/e command, find -delete/-exec, sort -o/--compress-program, awk with
    system() or redirection, and the write options of listed read commands (tree -o,
    xxd OUTFILE, file -C, rg --pre, less -o, date -s, hostname NAME);
  - python -m with a module outside PY_READ_MODULES, unless it is one of this repo's tools;
  - Python code (python -c or a heredoc body) that calls a direct file-write API;
  - a repo script invoked with a known write verb (reconcile, --apply, --write ...), or a script
    whose run creates files (setup, wizard, battery, the temp-directory selftests).

This is pattern matching, so it cannot make Bash read-only: a script that writes as a side effect
of an ordinary-looking invocation, an import with side effects, or open() with the mode held in a
variable all pass. The selftest pins those misses as ALLOWED on purpose, so the limit is tested
rather than assumed: Bash stays write-capable for the guarded agent, and the guard only narrows it.

  python3 tools/readonly_bash_guard.py                 # hook mode: JSON on stdin
  python3 tools/readonly_bash_guard.py --check "CMD"   # print the verdict for one command
  python3 tools/readonly_bash_guard.py --selftest      # table-driven selftest; writes nothing
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import sys

GUARDED_AGENT_TYPES = ("auditor",)

READ_COMMANDS = frozenset({
    "cat", "head", "tail", "ls", "wc", "grep", "egrep", "fgrep", "rg", "cut", "tr", "diff", "cmp",
    "comm", "file", "stat", "du", "df", "pwd", "echo", "printf", "true", "false", "test", "[",
    "which", "type", "basename", "dirname", "realpath", "readlink", "date", "printenv", "id",
    "whoami", "uname", "hostname", "jq", "nl", "column", "tac", "rev", "seq", "sleep", "uniq",
    "od", "xxd", "hexdump", "sha256sum", "sha1sum", "md5sum", "shasum", "cksum", "tree", "cd",
    "pushd", "popd", "export", "unset", "set", "shopt", ":", "fold", "expand", "paste", "join",
    "strings", "less", "more", "look", "wait",
})
REFUSED_INTERPRETERS = frozenset({
    "sh", "bash", "zsh", "dash", "ksh", "fish", "perl", "ruby", "node", "deno", "php", "lua",
    "osascript", "eval", "exec", "source", ".", "xargs", "parallel", "sudo", "su", "nohup",
    "watch", "script", "expect", "make", "ninja", "cmake",
})
GIT_READ = frozenset({
    "log", "show", "diff", "status", "rev-parse", "ls-files", "ls-tree", "grep", "blame",
    "cat-file", "describe", "shortlog", "check-ignore", "check-attr", "merge-base", "name-rev",
    "for-each-ref", "rev-list", "show-ref", "count-objects", "whatchanged", "cherry", "var",
    "version", "help", "diff-tree", "diff-index", "diff-files", "annotate", "range-diff",
    "show-branch", "verify-commit", "verify-tag",
})
# Subcommands that read in some forms and write in others: allowed with no arguments (the listing
# form) or when the first argument is a read form and no argument is a write form.
GIT_CONDITIONAL = {
    "branch": ({"-a", "-r", "--all", "--remotes", "--list", "-l", "-v", "-vv", "--contains",
                "--no-contains", "--show-current", "--merged", "--no-merged", "--points-at"},
               {"-d", "-D", "-m", "-M", "-c", "-C", "--delete", "--move", "--copy", "-f",
                "--force", "-u", "--set-upstream-to", "--unset-upstream", "--edit-description"}),
    "tag": ({"-l", "--list", "--contains", "--no-contains", "--points-at", "--merged",
             "--no-merged", "-n"}, {"-d", "--delete", "-a", "-s", "-f", "-m", "-F", "--force"}),
    "stash": ({"list", "show"}, set()),
    "worktree": ({"list"}, set()),
    "remote": ({"-v", "--verbose", "show", "get-url"}, set()),
    "reflog": ({"show"}, set()),
    "config": ({"--get", "--get-all", "--get-regexp", "--list", "-l", "--show-origin"}, set()),
    "notes": ({"list", "show"}, set()),
}
GIT_WRITE_OPTIONS = ("--output", "-O", "--open-files-in-pager", "--ext-diff")
PY_REFUSED_MODULES = frozenset({"pip", "pip3", "venv", "ensurepip", "compileall", "py_compile",
                                "http.server", "zipapp", "virtualenv"})
# python -m modules that only read. Any other module is refused (zipfile, tarfile, gzip, sqlite3,
# cProfile -o and pydoc -w all write), except this repo's own tools.<name>, checked as scripts.
PY_READ_MODULES = frozenset({"json.tool", "tokenize", "ast", "dis", "platform", "sysconfig",
                             "site", "timeit", "base64", "calendar"})
# Environment variables a command may set. Any other can point git, a pager or an interpreter at a
# program, for example GIT_EXTERNAL_DIFF, GIT_CONFIG_COUNT/KEY/VALUE, LESSOPEN or PAGER.
SAFE_ENV_VARS = frozenset({"PYTHONDONTWRITEBYTECODE", "GIT_OPTIONAL_LOCKS", "LC_ALL", "LANG", "TZ",
                           "NO_COLOR", "PYTHONIOENCODING", "PYTHONUTF8", "COLUMNS"})
# Options that make a listed read command write a file, run a program or change the system.
READ_COMMAND_WRITE_OPTIONS = {
    "tree": ("-o",), "file": ("-C", "--compile"), "rg": ("--pre",),
    "less": ("-o", "-O", "--log-file", "--LOG-FILE"), "date": ("-s", "--set"),
}
XXD_VALUE_OPTIONS = frozenset({"-s", "-l", "-c", "-g", "-o", "-n", "-seek", "-len", "-cols",
                               "-groupsize", "-offset", "-name"})
# Write verbs of this repo's own CLIs, and scripts whose run (or --selftest) creates files.
REPO_WRITE_ARGS = frozenset({"reconcile", "--apply", "--write", "--force", "--accept-new", "accept",
                             "update-source", "remove-source", "seed-sources", "seed-partners",
                             "prune-orphans", "mark-checked", "set-interval"})
REPO_WRITING_SCRIPTS = frozenset({"setup.py", "wizard.py", "install_hooks.py", "release.py",
                                  "new_skill.py", "migrate_local.py", "update.py", "sync_cache.py",
                                  "package_skill.py", "battery.py", "selftest_sweep.py"})
REPO_TEMPDIR_SELFTESTS = frozenset({"mac_surface_manifest.py", "doc_freshness.py",
                                    "projection_manifest.py"})
PY_WRITE_RE = re.compile(
    r"\.write_(?:text|bytes)\s*\("
    r"|\bopen\s*\([^)]*?,\s*(?:mode\s*=\s*)?[rbt]?['\"][^'\"]*[wax+]"
    r"|\bos\.(?:remove|unlink|rmdir|removedirs|rename|renames|replace|makedirs|mkdir|mkfifo"
    r"|chmod|chown|symlink|link|truncate|system|popen|exec\w*|spawn\w*|utime)\s*\("
    r"|\bshutil\.\w+\s*\("
    r"|\.(?:unlink|mkdir|rmdir|touch|symlink_to|hardlink_to|chmod)\s*\("
    r"|\btempfile\.\w+"
    r"|\bsqlite3\.connect\s*\("
    r"|\b__import__\s*\("
    r"|\bfrom\s+(?:os|shutil|tempfile)\s+import\b"
)
_SEP_CHARS = set(";&|()")


def _split_lines(cmd):
    """Split at newlines that are outside quotes. Returns (lines, error)."""
    lines, cur, quote, i = [], [], None, 0
    while i < len(cmd):
        c = cmd[i]
        if quote:
            if c == "\\" and quote == '"' and i + 1 < len(cmd):
                cur.append(cmd[i:i + 2])
                i += 2
                continue
            if c == quote:
                quote = None
        elif c == "\\" and i + 1 < len(cmd):
            if cmd[i + 1] != "\n":
                cur.append(cmd[i:i + 2])
            i += 2
            continue
        elif c in "'\"":
            quote = c
        elif c == "\n":
            lines.append("".join(cur))
            cur = []
            i += 1
            continue
        cur.append(c)
        i += 1
    lines.append("".join(cur))
    return lines, ("unbalanced quotes" if quote else None)


def _expansion_outside_single_quotes(line):
    """True if $(, a backquote, <( or >( occurs where the shell would expand it."""
    quote, i = None, 0
    while i < len(line):
        c = line[i]
        if quote == "'":
            if c == "'":
                quote = None
        else:
            if c == "\\":
                i += 2
                continue
            if c == "`" or line.startswith("$(", i):
                return True
            if quote is None and (line.startswith("<(", i) or line.startswith(">(", i)):
                return True
            if c == '"':
                quote = None if quote == '"' else '"'
            elif c == "'" and quote is None:
                quote = "'"
        i += 1
    return False


_HEREDOC_RE = re.compile(r"<<(-?)\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\2")


def _take_heredocs(cmd):
    """Remove heredoc bodies; return (shell_text, [bodies])."""
    out, bodies, pending, body = [], [], [], []
    for line in cmd.split("\n"):
        if pending:
            dash, delim = pending[0]
            if (line.lstrip("\t") if dash else line) == delim:
                bodies.append("\n".join(body))
                body = []
                pending.pop(0)
            else:
                body.append(line)
            continue
        out.append(line)
        pending.extend((m.group(1) == "-", m.group(3)) for m in _HEREDOC_RE.finditer(line))
    if pending:
        bodies.append("\n".join(body))
    return "\n".join(out), bodies


def _segments(line):
    """Tokenize one line into simple commands; returns (list of argv lists, refusal or None)."""
    lex = shlex.shlex(line, posix=True, punctuation_chars=True)
    lex.whitespace_split = True
    lex.commenters = ""
    try:
        toks = list(lex)
    except ValueError as exc:
        return [], f"cannot parse the command ({exc})"
    segs, cur, i = [], [], 0
    while i < len(toks):
        t = toks[i]
        is_punct = bool(t) and set(t) <= (_SEP_CHARS | {"<", ">"})
        if is_punct and (">" in t or "<" in t):
            if cur and cur[-1].isdigit():
                cur.pop()                       # the fd number of `2>...`
            if "<>" in t:
                return segs, "read-write redirection (<>) opens a file for writing"
            if ">" in t:
                target = toks[i + 1] if i + 1 < len(toks) else ""
                if not ((t.endswith("&") and (target.isdigit() or target == "-"))
                        or target == "/dev/null"):
                    return segs, f"output redirection to {target or '(nothing)'}"
            i += 2
            continue
        if is_punct:
            if cur:
                segs.append(cur)
            cur = []
        else:
            cur.append(t)
        i += 1
    if cur:
        segs.append(cur)
    return segs, None


def _check_git(args):
    i = 0
    while i < len(args) and args[i].startswith("-"):
        a = args[i]
        if a == "-c" or a.startswith("--config-env") or a.startswith("--exec-path"):
            return "git -c / --config-env / --exec-path can make git run a command"
        i += 2 if a == "-C" else 1
    if i >= len(args):
        return None
    sub, rest = args[i], args[i + 1:]
    for a in rest:
        if a.startswith(GIT_WRITE_OPTIONS):
            return f"git {sub} {a} writes a file or runs an external program"
    if sub in GIT_READ:
        return None
    if sub in GIT_CONDITIONAL:
        reads, writes = GIT_CONDITIONAL[sub]
        if not rest:
            return None if sub != "stash" else "git stash with no arguments stashes changes"
        if rest[0] in reads and not any(a in writes for a in rest):
            return None
        return f"git {sub} {' '.join(rest[:2])} is not a read-only form"
    return f"git {sub} can change the repository"


def _check_repo_args(rest):
    for a in rest:
        if a in REPO_WRITE_ARGS or a.split("=", 1)[0] in REPO_WRITE_ARGS:
            return f"'{a}' is a write verb of this repo's tools"
    return None


def _check_python_code(code):
    m = PY_WRITE_RE.search(code or "")
    return f"Python code calls a file-write API ({m.group(0).strip()})" if m else None


def _check_script(name, rest):
    if name in REPO_WRITING_SCRIPTS:
        return f"{name} creates or changes files when it runs"
    if name in REPO_TEMPDIR_SELFTESTS and "--selftest" in rest:
        return f"{name} --selftest creates temporary directories"
    return _check_repo_args(rest)


def _check_env(assignment):
    var = assignment.split("=", 1)[0]
    if var in SAFE_ENV_VARS:
        return None
    return (f"setting {var} can make a read command run a program; only "
            f"{', '.join(sorted(SAFE_ENV_VARS))} may be set")


def _check_python(args):
    i, script = 0, None
    while i < len(args):
        a = args[i]
        if a == "-c":
            return _check_python_code(args[i + 1] if i + 1 < len(args) else "")
        if a == "-m":
            mod = args[i + 1] if i + 1 < len(args) else ""
            rest = args[i + 2:]
            if mod in PY_REFUSED_MODULES:
                return f"python -m {mod} installs or writes files"
            if mod.startswith("tools."):
                return _check_script(mod.rsplit(".", 1)[1] + ".py", rest)
            if mod not in PY_READ_MODULES:
                return f"python -m {mod} is not on the read-only module list"
            if mod == "json.tool" and len([a for a in rest if not a.startswith("-")]) > 1:
                return "python -m json.tool with an output file writes it"
            return _check_repo_args(rest)
        if a in ("-X", "-W"):
            i += 2
            continue
        if a == "-":
            return None
        if a.startswith("-"):
            i += 1
            continue
        script = a
        break
    if script is None:
        return None
    return _check_script(os.path.basename(script), args[i + 1:])


def _check_argv(argv):
    i = 0
    while i < len(argv) and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", argv[i]):
        why = _check_env(argv[i])
        if why:
            return why
        i += 1
    argv = argv[i:]
    while argv:
        name = os.path.basename(argv[0])
        if name in ("time", "builtin") or (name == "command" and argv[1:2] not in (["-v"], ["-V"])):
            argv = argv[1:]
        elif name == "env":
            argv = argv[1:]
            while argv and (argv[0].startswith("-") or "=" in argv[0]):
                why = None if argv[0].startswith("-") else _check_env(argv[0])
                if why:
                    return why
                argv = argv[1:]
        elif name in ("timeout", "nice"):
            argv = argv[1:]
            while argv and (argv[0].startswith("-") or re.match(r"^\d", argv[0])):
                argv = argv[1:]
        else:
            break
    if not argv:
        return None
    name, args = os.path.basename(argv[0]), argv[1:]
    if name in REFUSED_INTERPRETERS:
        return f"{name} runs commands the guard cannot see"
    if name == "git":
        return _check_git(args)
    if re.match(r"^python(\d+(\.\d+)?)?$", name):
        return _check_python(args)
    if name == "find":
        bad = [a for a in args if a in ("-delete", "-exec", "-execdir", "-ok", "-okdir", "-fprint",
                                         "-fprint0", "-fprintf", "-fls")]
        return f"find {bad[0]} can change files" if bad else None
    if name in ("sed", "gsed"):
        if any(a.startswith("-i") or a.startswith("--in-place") for a in args):
            return "sed -i edits files in place"
        if any(re.search(r"(^|[;}\s])[wWe]\s|/[wWe]\s*\S", a) for a in args if not a.startswith("-")):
            return "a sed w/W/e command writes a file or runs a command"
        return None
    if name in ("awk", "gawk", "mawk", "nawk"):
        if any(("system(" in a or ">" in a or "|" in a or "inplace" in a) for a in args):
            return "the awk program redirects output or runs a command"
        return None
    if name == "sort":
        if any(a.startswith(("-o", "--output", "--compress-program")) for a in args):
            return "sort -o or --compress-program writes a file or runs a program"
        return None
    if name == "uniq":
        positional = [a for a in args if not a.startswith("-")]
        return "uniq with an output file writes it" if len(positional) > 1 else None
    bad = READ_COMMAND_WRITE_OPTIONS.get(name, ())
    hit = next((a for a in args if bad and a.startswith(bad)), None)
    if hit:
        return f"{name} {hit} writes a file, runs a program or changes the system"
    if name == "xxd":
        positional, skip = [], False
        for a in args:
            if skip:
                skip = False
            elif a in XXD_VALUE_OPTIONS:
                skip = True
            elif a == "-" or not a.startswith("-"):
                positional.append(a)
        if len(positional) > 1:
            return "xxd with an output file writes it"
    if name == "hostname" and any(not a.startswith("-") for a in args):
        return "hostname NAME changes the system name"
    if name == "export":
        for a in args:
            why = _check_env(a) if "=" in a else None
            if why:
                return why
    if name in READ_COMMANDS:
        return None
    return f"{name} is not on the read-only command list"


def guard(cmd):
    """(allowed, reason) for one Bash command string."""
    if not isinstance(cmd, str):
        return False, "no command string"
    shell, bodies = _take_heredocs(cmd)
    for body in bodies:
        why = _check_python_code(body)
        if why:
            return False, f"heredoc body: {why}"
    lines, err = _split_lines(shell)
    if err:
        return False, err
    for line in lines:
        if not line.strip():
            continue
        if _expansion_outside_single_quotes(line):
            return False, "command or process substitution hides the inner command; run it separately"
        segs, why = _segments(line)
        if why:
            return False, why
        for argv in segs:
            why = _check_argv(argv)
            if why:
                return False, why
    return True, "read-only"


def decide(payload):
    """(exit_code, message) for one hook payload. Exit 2 blocks the tool call."""
    if not isinstance(payload, dict) or payload.get("tool_name") != "Bash":
        return 0, ""
    if payload.get("agent_type") not in GUARDED_AGENT_TYPES:
        return 0, ""
    cmd = (payload.get("tool_input") or {}).get("command")
    try:
        ok, why = guard(cmd)
    except Exception as exc:  # fail closed for the guarded agent
        ok, why = False, f"guard error: {exc!r}"
    if ok:
        return 0, ""
    return 2, (f"readonly_bash_guard: refused for the {payload.get('agent_type')} agent: {why}. "
               f"This agent is read-only; use a read-only form of the command.")


ALLOW_CASES = [
    "git log --oneline -5",
    "git -C /repo show HEAD:CLAUDE.md | head -40",
    "git diff HEAD~1 -- tools/sync_check.py 2>/dev/null",
    "git status --porcelain",
    "git branch -a",
    "git branch --contains 9d4148c",
    "git worktree list",
    "cd /repo && grep -n 'def main' tools/*.py | head",
    "ls -la .claude/agents >/dev/null 2>&1",
    "find . -name '*.md' -newer CLAUDE.md",
    "sed -n '1,40p' CLAUDE.md",
    "awk '{print $1}' file.txt | sort | uniq -c",
    "python3 tools/count_truth.py",
    "PYTHONDONTWRITEBYTECODE=1 python3 tools/sync_check.py",
    "python3 -c 'import json; print(json.load(open(\"a.json\"))[\"x\"])'",
    "python3 - <<'EOF'\nimport pathlib\nprint(pathlib.Path('CLAUDE.md').read_text()[:10])\nif 2 > 1: print('ok')\nEOF",
    "grep -c '$(' notes.txt",
    "echo 'a > b' | wc -c",
    "python3 -m json.tool data.json",
    "env GIT_OPTIONAL_LOCKS=0 git status --porcelain",
    "timeout 30 git log -1",
    "xxd -l 64 CLAUDE.md",
    "LC_ALL=C sort notes.txt",
    "export LC_ALL=C; git log -1",
    "python3 -m tokenize tools/tree_pin.py",
]
REFUSE_CASES = [
    "echo x > notes.md",
    "echo x >> notes.md",
    "cat a 2> err.log",
    "rm -rf build",
    "mv a b",
    "cp a b",
    "mkdir out",
    "touch x",
    "tee out.txt < in",
    "ls | xargs rm",
    "bash -c 'rm x'",
    "sh script.sh",
    "sed -i 's/a/b/' f",
    "sed 's/a/b/w out' f",
    "find . -name '*.pyc' -delete",
    "find . -exec rm {} ;",
    "sort -o out.txt in.txt",
    "awk '{print > \"o\"}' f",
    "git add -A",
    "git commit -m x",
    "git push origin HEAD",
    "git checkout -- CLAUDE.md",
    "git reset --hard",
    "git stash",
    "git branch -D old",
    "git tag -a v1 -m x",
    "git -c core.pager=sh log",
    "git diff --output=patch.diff",
    "pip download requests",
    "python3 -m pip download x",
    "curl -o page.html example.invalid",
    "python3 -c 'open(\"x\",\"w\").write(\"1\")'",
    "python3 - <<'EOF'\nfrom pathlib import Path\nPath('x').write_text('1')\nEOF",
    "python3 - <<EOF\nimport shutil\nshutil.rmtree('build')\nEOF",
    "python3 tools/doc_freshness.py reconcile",
    "python3 tools/build_freshness_bundle.py --apply",
    "python3 tools/setup.py --selftest",
    "python3 tools/battery.py",
    "cat $(git ls-files) | wc -l",
    "echo `id`",
    "diff <(git show HEAD:a) a",
    "cat a 1<> b",
    "sudo ls",
    "npm install",
    "GIT_EXTERNAL_DIFF=./x.sh git diff",
    "export GIT_EXTERNAL_DIFF=./x.sh; git diff",
    "env GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=core.fsmonitor GIT_CONFIG_VALUE_0=./x.sh git status",
    "LESSOPEN='|./x.sh %s' less CLAUDE.md",
    "tree -o out.txt",
    "xxd CLAUDE.md out.hex",
    "file -C -m magic",
    "rg --pre ./x.sh foo",
    "sort --compress-program=./x.sh notes.txt",
    "less -o log.txt CLAUDE.md",
    "date -s 2020-01-01",
    "hostname other",
    "python3 -m json.tool a.json b.json",
    "python3 -m zipfile -c out.zip tools",
    "python3 -m sqlite3 new.db",
    "python3 -m tools.battery",
    "python3 -c \"__import__('os').remove('x')\"",
    "python3 -c 'from os import remove; remove(\"x\")'",
]
# Known misses: writes the patterns cannot see. They are ALLOWED here on purpose, so the selftest
# fails if the guard's documented limit ever changes without the docs changing with it.
KNOWN_MISSES = [
    "python3 tools/some_new_writer.py",
    "python3 -c 'import m'",
    "python3 -c 'm=\"w\"; f=open(\"x\", m)'",
    "python3 -c 'import subprocess; subprocess.run([\"git\",\"commit\"])'",
]


def selftest():
    fails = []
    for c in ALLOW_CASES + KNOWN_MISSES:
        ok, why = guard(c)
        if not ok:
            fails.append(f"should allow: {c!r} ({why})")
    for c in REFUSE_CASES:
        ok, why = guard(c)
        if ok:
            fails.append(f"should refuse: {c!r}")
    hook = [
        ({"tool_name": "Bash", "agent_type": "auditor", "tool_input": {"command": "rm x"}}, 2),
        ({"tool_name": "Bash", "agent_type": "auditor", "tool_input": {"command": "git log"}}, 0),
        ({"tool_name": "Bash", "tool_input": {"command": "rm x"}}, 0),
        ({"tool_name": "Bash", "agent_type": "seo-researcher", "tool_input": {"command": "rm x"}}, 0),
        ({"tool_name": "Read", "agent_type": "auditor", "tool_input": {"file_path": "x"}}, 0),
        ({"tool_name": "Bash", "agent_type": "auditor", "tool_input": {}}, 2),
    ]
    for payload, want in hook:
        got = decide(payload)[0]
        if got != want:
            fails.append(f"decide({payload}) exit {got}, want {want}")
    n = len(ALLOW_CASES) + len(KNOWN_MISSES) + len(REFUSE_CASES) + len(hook)
    for f in fails:
        print(f"FAIL {f}")
    print(f"readonly_bash_guard selftest: {n - len(fails)}/{n} passed "
          f"({len(REFUSE_CASES)} refusals, {len(ALLOW_CASES)} reads, {len(KNOWN_MISSES)} known misses)")
    return 1 if fails else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="PreToolUse Bash guard for the read-only auditor agent.")
    ap.add_argument("--selftest", action="store_true", help="run the table-driven selftest")
    ap.add_argument("--check", metavar="CMD", help="print the verdict for one command")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    if a.check is not None:
        ok, why = guard(a.check)
        print(("ALLOW " if ok else "REFUSE ") + why)
        return 0 if ok else 2
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except ValueError:
        print("readonly_bash_guard: hook input is not JSON; no decision", file=sys.stderr)
        return 1
    code, msg = decide(payload)
    if msg:
        print(msg, file=sys.stderr)
    return code


if __name__ == "__main__":
    sys.exit(main())
