#!/usr/bin/env python3
"""Refuse write-capable shell commands from the read-only auditor agent (PreToolUse hook).

Wired in `.claude/settings.json` as a PreToolUse hook on the Bash tool. Claude Code sends the hook
a JSON object on stdin; inside a subagent that object carries `agent_type` (the agent's frontmatter
`name`). The guard acts only when `agent_type` is in GUARDED_AGENT_TYPES and otherwise exits 0 at
once, so the main loop and the product agents are unaffected.

For a guarded agent it parses the command, reading a $'..' or $".." string as Bash decodes it,
and refuses (exit 2, reason on stderr) when it finds:
  - output redirection to anything but /dev/null or another file descriptor;
  - a variable set outside SAFE_ENV_VARS (VAR=..., env VAR=..., export VAR[=...], printf -v VAR,
    ${VAR:=...} or ${VAR=...}, and an arithmetic assignment such as $[VAR=1], ${a[VAR=1]} or
    ${a:VAR=1}, outside single quotes): GIT_EXTERNAL_DIFF, GIT_CONFIG_*,
    LESSOPEN and similar variables make a read command run a program;
  - an expansion outside single quotes of a value the command line can set out of the guard's
    sight: a positional parameter ($1, $@, $*; set -- sets them), $_ (the previous command's last
    argument) and a SAFE_ENV_VARS variable, except one ${NAME:=word} of a variable nothing else
    in the command sets;
  - command substitution, process substitution, or backquotes (the inner command is not visible),
    also in the body of a heredoc whose delimiter is unquoted, and a heredoc operator it cannot
    read. A << inside quotes or a comment, and the <<< here-string, start no heredoc, so the
    lines after them are checked as commands;
  - a command that is not on the read-only list (rm, mv, cp, tee, pip, curl, sh -c, xargs ...);
  - env -S or --split-string, which splits its string into a command line; env's other options
    are read as getopt reads them, so the command after -u NAME or -C DIR is checked;
  - a git subcommand outside the read-only set, or a read-only one with a write option. Global
    options that take a value (-C, --git-dir, --namespace ...) are skipped with their value;
    after git remote, stash, worktree, reflog or notes the next word must be a read word; git
    branch and tag refuse a write option in any spelling (-vD, --del, --set-upstream-to=X) and
    a name without a listing option, which creates it; git config needs --get, --get-all,
    --get-regexp or --list;
  - sed -i, a sed w, W or e command or s///w or s///e flag in any -e, --expression or operand
    program (read as sed parses a program), find -delete/-exec, sort -o/--compress-program, awk with
    system() or redirection, and the write options of listed read commands (tree -o,
    xxd OUTFILE, file -C, rg --pre or --hostname-bin, less -o, date -s,
    hostname with anything but a display option), read as getopt reads
    them: a short option inside a cluster (sed -Ei, sort -ro, python -Sc) or with its value
    attached, and a long option with =value or cut to a prefix (sed --in-pl, sort --outp); a sed
    or awk program read from a file (-f) is not seen;
  - python -m with a module outside PY_READ_MODULES (timeit is not on it: it runs its
    statement arguments), unless it is one of this repo's tools, and python -m sysconfig
    --generate-posix-vars;
  - Python code (python -c, or a heredoc body unless a listed read command reads it and its
    output is not piped on) that calls a direct file-write API: a regex, and
    when the code parses an ast pass (open(), Path.open, io.FileIO, ZipFile and any call
    whose name ends in open or File (GzipFile, BZ2File, LZMAFile, PyZipFile) with a literal
    write mode whatever the first argument is, a literal write mode= keyword on any call, os.open with a write flag, shelve.open, and
    getattr(obj, 'write_text') with a literal name; names are read through import aliases,
    name = X bindings, importlib.import_module('m') and sys.modules['m'], exec, eval or compile
    of literal text is read as code, and so are the arguments after python -c CODE);
  - python reading its code from standard input (python3 -, /dev/stdin or no script): a
    here-string and echo or printf text piped in are checked as Python code, and code from a file
    or from other command output is refused, the guard cannot read it;
  - a repo script invoked with a known write verb (reconcile, --apply, --write ...), or a script
    whose run creates files (setup, wizard, battery, the temp-directory selftests).

Braces outside quotes are expanded before these checks as Bash expands them ({a,b} and
{1..3}), so {-delete,-print} is read as -delete -print.

This is pattern matching, so it cannot make Bash read-only: a script that writes as a side effect
of an ordinary-looking invocation, an import with side effects, open() or os.open with the mode
or flags held in a variable, getattr with the method name held in a variable, exec or eval of text
built at run time (exec(codecs.decode(...))), Path.replace (str.replace has the same name) and a library
that opens its own file (logging.FileHandler, mailbox.mbox) all pass. The selftest pins those misses as
ALLOWED on purpose, so the limit is tested
rather than assumed: Bash stays write-capable for the guarded agent, and the guard only narrows it.

  python3 tools/readonly_bash_guard.py                 # hook mode: JSON on stdin
  python3 tools/readonly_bash_guard.py --check "CMD"   # print the verdict for one command
  python3 tools/readonly_bash_guard.py --selftest      # table-driven selftest; writes nothing
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import re
import shlex
import sys
import warnings

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
# Global options whose value is the next argument. The value is skipped with the option, so
# `git --namespace log commit` is read as commit, the subcommand git runs.
GIT_VALUE_GLOBALS = frozenset({"-C", "--git-dir", "--work-tree", "--namespace", "--super-prefix",
                               "--attr-source"})
# Subcommands with a subcommand word of their own: (options allowed before the word, read words,
# whether the bare form only lists). Any other word or leading option is refused.
GIT_SUBCOMMAND_READS = {
    "remote": ({"-v", "--verbose"}, {"show", "get-url"}, True),
    "stash": (set(), {"list", "show"}, False),
    "worktree": (set(), {"list"}, False),
    "reflog": (set(), {"show"}, True),
    "notes": (set(), {"list", "show"}, True),
}
# Option-driven subcommands: (options that select the listing form, write options, short options
# that take a value). A write option is refused however it is spelled (see _selects). A branch
# or tag name with no listing option creates that branch or tag, so it is refused too.
GIT_OPTION_MODES = {
    "branch": ({"-l", "--list", "--contains", "--no-contains", "--merged", "--no-merged",
                "--points-at"},
               {"-d", "-D", "-m", "-M", "-c", "-C", "-f", "-u", "--delete", "--move", "--copy",
                "--force", "--set-upstream-to", "--unset-upstream", "--edit-description"}, "u"),
    "tag": ({"-l", "--list", "--contains", "--no-contains", "--points-at", "--merged",
             "--no-merged", "-n"},
            {"-d", "-a", "-s", "-f", "-m", "-F", "-u", "-e", "--delete", "--annotate", "--sign",
             "--force", "--message", "--file", "--local-user", "--edit"}, "mFun"),
    "config": ({"-l", "--list", "--get", "--get-all", "--get-regexp", "--get-urlmatch",
                "--get-color", "--get-colorbool"},
               {"-e", "--edit", "--add", "--unset", "--unset-all", "--replace-all",
                "--rename-section", "--remove-section"}, "ft"),
}
GIT_WRITE_OPTIONS = ("--output", "-O", "--open-files-in-pager", "--ext-diff")
PY_REFUSED_MODULES = frozenset({"pip", "pip3", "venv", "ensurepip", "compileall", "py_compile",
                                "http.server", "zipapp", "virtualenv"})
# python -m modules that only read. Any other module is refused (zipfile, tarfile, gzip, sqlite3,
# cProfile -o and pydoc -w all write, and timeit runs its statement arguments as Python), except
# this repo's own tools.<name>, checked as scripts.
PY_READ_MODULES = frozenset({"json.tool", "tokenize", "ast", "dis", "platform", "sysconfig",
                             "site", "base64", "calendar"})
# Environment variables a command may set. Any other can point git, a pager or an interpreter at a
# program, for example GIT_EXTERNAL_DIFF, GIT_CONFIG_COUNT/KEY/VALUE, LESSOPEN or PAGER.
SAFE_ENV_VARS = frozenset({"PYTHONDONTWRITEBYTECODE", "GIT_OPTIONAL_LOCKS", "LC_ALL", "LANG", "TZ",
                           "NO_COLOR", "PYTHONIOENCODING", "PYTHONUTF8", "COLUMNS"})
# Options that make a listed read command write a file, run a program or change the system.
READ_COMMAND_WRITE_OPTIONS = {
    "tree": ("-o",), "file": ("-C", "--compile"), "rg": ("--pre", "--hostname-bin"),
    "less": ("-o", "-O", "--log-file", "--LOG-FILE"), "date": ("-s", "--set"),
}
XXD_VALUE_OPTIONS = frozenset({"-s", "-l", "-c", "-g", "-o", "-n", "-seek", "-len", "-cols",
                               "-groupsize", "-offset", "-name"})
# hostname's display options; any other argument (a name, -F/--file, -b/--boot) sets the name.
HOSTNAME_READ_SHORT = "aAdfiIsyVhv"
HOSTNAME_READ_LONG = ("--alias", "--all-fqdns", "--domain", "--fqdn", "--long", "--ip-address",
                      "--all-ip-addresses", "--short", "--yp", "--nis", "--version", "--help",
                      "--verbose")
# Write verbs of this repo's own CLIs, and scripts whose run (or --selftest) creates files.
REPO_WRITE_ARGS = frozenset({"reconcile", "--apply", "--write", "--force", "--accept-new", "accept",
                             "update-source", "remove-source", "seed-sources", "seed-partners",
                             "prune-orphans", "mark-checked", "set-interval"})
REPO_WRITING_SCRIPTS = frozenset({"setup.py", "wizard.py", "install_hooks.py", "release.py",
                                  "new_skill.py", "migrate_local.py", "update.py", "sync_cache.py",
                                  "package_skill.py", "battery.py", "selftest_sweep.py"})
REPO_TEMPDIR_SELFTESTS = frozenset({"mac_surface_manifest.py", "doc_freshness.py",
                                    "projection_manifest.py"})
# Path.copy, copy_into, move and move_into (Python 3.14) are writes. A .copy( call with an
# argument is refused whatever its object, so dict.copy() passes and x.copy(deep=True) does not.
PY_WRITE_RE = re.compile(
    r"\.write_(?:text|bytes)\s*\("
    r"|\bopen\s*\([^)]*?,\s*(?:mode\s*=\s*)?[rbt]?['\"][^'\"]*[wax+]"
    r"|\bos\.(?:remove|unlink|rmdir|removedirs|rename|renames|replace|makedirs|mkdir|mkfifo"
    r"|chmod|chown|lchown|lchmod|mknod|symlink|link|truncate|system|popen|exec\w*|spawn\w*"
    r"|posix_spawn\w*|utime|setxattr|removexattr|chflags|lchflags)\s*\("
    r"|\bshutil\.\w+\s*\("
    r"|\.(?:unlink|mkdir|rmdir|touch|symlink_to|hardlink_to|chmod|lchmod|rename|move|move_into"
    r"|copy_into)\s*\("
    r"|(?<!\bcopy)\.copy\s*\(\s*[^)\s]"
    r"|\burlretrieve\s*\("
    r"|\btempfile\.\w+"
    r"|\bsqlite3\.connect\s*\("
    r"|\b__import__\s*\("
    r"|\bfrom\s+(?:os|shutil|tempfile)\s+import\b"
)
# An awk print or printf sent to a file (print > "f", printf ... >> "f"); a > anywhere else in
# an awk program is a comparison.
_AWK_PRINT_TO_RE = re.compile(r"\bprintf?\b[^;{}\n]*>")
_SEP_CHARS = set(";&|()")
# Short options that take a value, per command: in a cluster such as -Ei or -ro, getopt reads
# option letters up to the first of these, and the rest of the token is that option's value.
SHORT_VALUE_LETTERS = {"sed": "efl", "sort": "kotST", "date": "dfrI", "less": "bhjkoOpPtTxyz#D",
                       "tree": "LPIoHT", "file": "efFmP"}
GIT_SHORT_VALUE_LETTERS = {"grep": "efABCm"}
GIT_DEFAULT_SHORT_VALUES = "nSGUMCBlXI"


def _selects(arg, options, values="", abbrev=True):
    """True when one argument selects one of `options` as getopt reads it: a short option alone,
    inside a cluster (-Ei, -ro) or with its value attached (-oout), reading letters up to the
    first one in `values`; a long option in full or with =value; and, when `abbrev`, a long
    option cut to a prefix, which getopt_long and git accept when the prefix is unambiguous."""
    if arg.startswith("--"):
        name = arg.split("=", 1)[0]
        return len(name) > 2 and any(o == name or (abbrev and o.startswith(name))
                                     for o in options if o.startswith("--"))
    letters = []
    for ch in arg[1:] if arg.startswith("-") else "":
        letters.append(ch)
        if ch in values:
            break
    return any(len(o) == 2 and o[0] == "-" and o[1] in letters for o in options)


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


def _heredoc_ops(line, quote):
    """Scan one physical line that starts in quote state `quote` (None, "'", '"' or "$'").
    Returns (operators, quote state at the end of the line), or None when a delimiter cannot be
    read. An operator is (strip_tabs, delimiter, quoted) for each << the shell reads: outside
    quotes and comments, and not the <<< here-string. The delimiter is the next shell word with
    its quotes removed; quoted is True when any part of it was quoted, which stops the shell
    expanding the body."""
    ops, i, n = [], 0, len(line)
    while i < n:
        c = line[i]
        if quote:
            if c == "\\" and quote != "'":
                i += 2
                continue
            if c == quote[-1]:
                quote = None
        elif c == "\\":
            i += 2
            continue
        elif line.startswith("$'", i):
            quote, i = "$'", i + 2
            continue
        elif c in "'\"":
            quote = c
        elif c == "#" and (i == 0 or line[i - 1] in " \t;&|()<>"):
            break
        elif line.startswith("<<<", i):
            i += 3
            continue
        elif line.startswith("<<", i):
            i += 2
            dash = line.startswith("-", i)
            i += 1 if dash else 0
            while i < n and line[i] in " \t":
                i += 1
            word, quoted = [], False
            while i < n and line[i] not in " \t;&|<>()":
                ch = line[i]
                if ch in "'\"":
                    end = line.find(ch, i + 1)
                    if end < 0:
                        return None
                    word.append(line[i + 1:end])
                    quoted, i = True, end + 1
                elif ch == "\\" and i + 1 < n:
                    word.append(line[i + 1])
                    quoted, i = True, i + 2
                else:
                    word.append(ch)
                    i += 1
            if not word:
                return None
            ops.append((dash, "".join(word), quoted))
            continue
        i += 1
    return ops, quote


def _ansi_c(text):
    """`text` with the backslash escapes of a $'..' string decoded (newline, tab, hex, octal,
    unicode, quote and backslash escapes); text that does not decode is returned as it is."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            return text.encode("latin-1", "backslashreplace").decode("unicode_escape")
    except (UnicodeDecodeError, ValueError):
        return text


def _ansi_c_quotes(line):
    """`line` with each $'..' string decoded and quoted again and each $".." read as "..", as
    Bash reads them outside other quotes, so an option or Python code written with escapes
    (sed $'-i', python3 -c with a hex-escaped call) is checked as the command receives it."""
    out, quote, i = [], None, 0
    while i < len(line):
        c = line[i]
        if quote:
            if c == "\\" and quote == '"':
                out.append(line[i:i + 2])
                i += 2
                continue
            if c == quote:
                quote = None
        elif c == "\\":
            out.append(line[i:i + 2])
            i += 2
            continue
        elif line.startswith("$'", i):
            j = i + 2
            while j < len(line) and line[j] != "'":
                j += 2 if line[j] == "\\" else 1
            out.append(shlex.quote(_ansi_c(line[i + 2:j])))
            i = j + 1
            continue
        elif line.startswith('$"', i):
            i += 1
            continue
        elif c in "'\"":
            quote = c
        out.append(c)
        i += 1
    return "".join(out)


def _take_heredocs(cmd):
    """Remove heredoc bodies; return (shell_text, [(body, quoted, text_only)], refusal or None),
    where text_only is _heredoc_readers' answer for the body."""
    out, bodies, pending, body, quote = [], [], [], [], None
    for line in cmd.split("\n"):
        if pending:
            dash, delim, quoted, text_only = pending[0]
            if (line.lstrip("\t") if dash else line) == delim:
                bodies.append(("\n".join(body), quoted, text_only))
                body = []
                pending.pop(0)
            else:
                body.append(line)
            continue
        out.append(line)
        scan = _heredoc_ops(line, quote)
        if scan is None or (scan[0] and scan[1]):
            return "\n".join(out), bodies, "a heredoc operator the guard cannot read"
        readers = (_heredoc_readers(line, len(scan[0])) if quote is None
                   else [False] * len(scan[0]))
        ops, quote = scan
        pending.extend(op + (r,) for op, r in zip(ops, readers))
    if pending:
        bodies.append(("\n".join(body), pending[0][2], pending[0][3]))
    return "\n".join(out), bodies, None


def _heredoc_readers(line, count):
    """For each of the `count` heredocs `line` opens, whether its body is only text: True when
    the command reading it is on READ_COMMANDS, its output is not piped on and the line has no
    subshell or group. Any other body, or a line the guard cannot tokenize, is checked as code."""
    lexer = shlex.shlex(line, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    lexer.commenters = ""
    try:
        toks = list(lexer)
    except ValueError:
        return [False] * count
    out, word, docs, after_op = [], None, 0, False
    for t in toks + [";"]:
        punct = bool(t) and set(t) <= (_SEP_CHARS | {"<", ">"})
        if punct and set(t) <= _SEP_CHARS:
            text = (word is not None and os.path.basename(word) in READ_COMMANDS
                    and "|" not in t and not set("(){}") & set(toks))
            out += [text] * docs
            word, docs = None, 0
        elif punct:
            docs += t.startswith("<<") and not t.startswith("<<<")
            after_op = True
        elif after_op:
            after_op = False
        elif word is None:
            word = t
    return out if len(out) == count else [False] * count


def _body_expansion(body):
    """Why the body of a heredoc with an unquoted delimiter is refused: the shell runs its $( )
    and backquotes and performs its ${NAME:=word} assignments."""
    live = re.sub(r"\\.", "", body, flags=re.S)
    if "$(" in live or "`" in live:
        return "the shell runs the command substitutions in an unquoted heredoc; quote the delimiter"
    return next(filter(None, map(_check_env, _expansion_assignments(live))), None)


# ${NAME:=word} and ${NAME=word} assign NAME while the shell expands them, and so does an
# arithmetic assignment (=, +=, ++, -- ...) inside $[..], an array subscript ${a[..]} or a
# substring offset ${a:..}, which the shell evaluates as arithmetic.
_ASSIGN_EXPANSION_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*):?=")
_ARITH_CONTEXT_RE = re.compile(r"\$\[|\$\{[#!]?[A-Za-z_][A-Za-z0-9_]*(?:\[|:(?![-=+?]))")
_ARITH_ASSIGN_RE = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)\s*(?:\[[^\]]*\]\s*)?"
                              r"(?:[-+*/%&|^]|<<|>>)?=(?!=)"
                              r"|([A-Za-z_][A-Za-z0-9_]*)\s*(?:\+\+|--)"
                              r"|(?:\+\+|--)\s*([A-Za-z_][A-Za-z0-9_]*)")


def _expansion_assignments(live):
    """The names the shell assigns while it expands `live` (text outside single quotes)."""
    names = [m.group(1) for m in _ASSIGN_EXPANSION_RE.finditer(live)]
    for m in _ARITH_CONTEXT_RE.finditer(live):
        pair = "[]" if m.group(0).endswith("[") else "{}"
        depth, j = 1, m.end()
        while j < len(live) and depth:
            depth += (live[j] == pair[0]) - (live[j] == pair[1])
            j += 1
        names += [a or b or c for a, b, c in _ARITH_ASSIGN_RE.findall(live[m.end():j])]
    return names


def _live_text(line):
    """`line` with single-quoted text and backslash-escaped characters blanked, leaving the text
    the shell expands."""
    out, quote, i = [], None, 0
    while i < len(line):
        c = line[i]
        if quote == "'":
            quote = None if c == "'" else quote
            c = " "
        elif c == "\\":
            out.append("  ")
            i += 2
            continue
        elif c == '"':
            quote = None if quote == '"' else '"'
        elif c == "'" and quote is None:
            quote, c = "'", " "
        out.append(c)
        i += 1
    return "".join(out)


# Brace expansion runs before the checks read a word: _mark_braces marks the braces and commas
# Bash would expand (outside quotes, not in ${...}) and _brace_words expands a marked token into
# the words Bash makes of it, so {-delete,-print} is read as -delete -print.
_BRACE_MARK = {"{": "", ",": "", "}": ""}
_BRACE_UNMARK = {ord(v): k for k, v in _BRACE_MARK.items()}
_BRACE_LIMIT = 1024
_BRACE_SEQ_RE = re.compile(r"(-?\d+)\.\.(-?\d+)(?:\.\.(-?\d+))?"
                           r"|([A-Za-z])\.\.([A-Za-z])(?:\.\.(-?\d+))?")


def _mark_braces(line):
    out, quote, i = [], None, 0
    while i < len(line):
        c = line[i]
        if quote:
            if c == "\\" and quote != "'":
                out.append(line[i:i + 2])
                i += 2
                continue
            if c == quote[-1]:
                quote = None
        elif c == "\\":
            out.append(line[i:i + 2])
            i += 2
            continue
        elif line.startswith("$'", i):
            quote, c, i = "$'", "$'", i + 1
        elif line.startswith("${", i):
            depth, j = 0, i + 1
            while j < len(line):
                depth += {"{": 1, "}": -1}.get(line[j], 0)
                j += 1
                if depth == 0:
                    break
            out.append(line[i:j])
            i = j
            continue
        elif c in "'\"":
            quote = c
        elif c in _BRACE_MARK:
            c = _BRACE_MARK[c]
        out.append(c)
        i += 1
    return "".join(out)


def _brace_seq(body):
    """The words of a {a..b} or {a..b..step} sequence body, or None when it is not one."""
    m = _BRACE_SEQ_RE.fullmatch(body)
    if not m:
        return None
    a, b, step = m.group(1, 2, 3) if m.group(1) else m.group(4, 5, 6)
    step = abs(int(step or 1)) or 1
    num = m.group(1) is not None
    lo, hi = (int(a), int(b)) if num else (ord(a), ord(b))
    if abs(hi - lo) // step >= _BRACE_LIMIT:
        raise ValueError("brace expansion makes too many words to check")
    seq = range(lo, hi + 1, step) if hi >= lo else range(lo, hi - 1, -step)
    if not num:
        return [chr(n) for n in seq]
    width = max(len(a), len(b)) if re.match(r"-?0\d", a) or re.match(r"-?0\d", b) else 1
    return [f"{n:0{width}d}" for n in seq]


def _brace_once(w):
    """The words one expansion of the first expandable marked brace in `w` makes, or None."""
    op, comma, cl = _BRACE_MARK["{"], _BRACE_MARK[","], _BRACE_MARK["}"]
    for i, ch in enumerate(w):
        if ch != op:
            continue
        depth, cuts = 0, []
        for j in range(i, len(w)):
            depth += (w[j] == op) - (w[j] == cl)
            if depth == 0:
                break
            if w[j] == comma and depth == 1:
                cuts.append(j)
        else:
            continue
        if cuts:
            edges = [i] + cuts + [j]
            return [w[:i] + w[a + 1:b] + w[j + 1:] for a, b in zip(edges, edges[1:])]
        seq = _brace_seq(w[i + 1:j].translate(_BRACE_UNMARK))
        if seq is not None:
            return [w[:i] + s + w[j + 1:] for s in seq]
    return None


def _brace_words(word):
    """The words Bash brace expansion makes of one token marked by _mark_braces."""
    todo, out = [word], []
    while todo:
        w = todo.pop(0)
        parts = _brace_once(w)
        if parts is None:
            out.append(w.translate(_BRACE_UNMARK))
        else:
            todo[:0] = parts
        if len(out) + len(todo) > _BRACE_LIMIT:
            raise ValueError("brace expansion makes too many words to check")
    return out


def _segments(line):
    """Tokenize one line into simple commands; returns (list of argv lists, refusal or None)."""
    lex = shlex.shlex(_mark_braces(line), posix=True, punctuation_chars=True)
    lex.whitespace_split = True
    lex.commenters = ""
    try:
        toks = [w for t in lex for w in _brace_words(t)]
    except ValueError as exc:
        return [], f"cannot parse the command ({exc})"
    segs, cur, i, stdin, piped = [], [], 0, None, None
    while i < len(toks):
        t = toks[i]
        is_punct = bool(t) and set(t) <= (_SEP_CHARS | {"<", ">"})
        if is_punct and (">" in t or "<" in t):
            if cur and cur[-1].isdigit():
                cur.pop()                       # the fd number of `2>...`
            if "<>" in t:
                return segs, "read-write redirection (<>) opens a file for writing"
            if "<" in t:
                word = toks[i + 1] if i + 1 < len(toks) else ""
                stdin = (("text", word) if t.startswith("<<<") else ("heredoc", "")
                         if t.startswith("<<") else ("text", "") if word == "/dev/null"
                         else ("file", word))
            if ">" in t:
                target = toks[i + 1] if i + 1 < len(toks) else ""
                if not ((t.endswith("&") and (target.isdigit() or target == "-"))
                        or target == "/dev/null"):
                    return segs, f"output redirection to {target or '(nothing)'}"
            i += 2
            continue
        if is_punct:
            last = _Argv(cur, stdin or piped) if cur else None
            if last is not None:
                segs.append(last)
            if "|" in t and "||" not in t:
                piped = ("pipe", None if ")" in t else last)
            elif set(t) - {"("}:
                piped = None
            cur, stdin = [], None
        else:
            cur.append(t)
        i += 1
    if cur:
        segs.append(_Argv(cur, stdin or piped))
    return segs, None


# Values a command line can set out of the guard's sight: positional parameters (set -- X),
# $_ (the last argument of the previous command) and the SAFE_ENV_VARS a command may set.
# Expanded outside single quotes, they carry text the checks never read into an argument.
_CARRIER_RE = re.compile(r"\$(\{[!#]?)?([A-Za-z_][A-Za-z0-9_]*|[0-9]+|[@*])(:?=)?")


def _carrier_expansion(live_texts):
    """Why an expansion of a carrier value is refused, or None. One ${NAME:=word} or ${NAME=word}
    of a SAFE_ENV_VARS name that nothing else in the command sets or expands is allowed: its
    value is the word on the line, where the checks read it."""
    live = "\n".join(live_texts)
    for m in _CARRIER_RE.finditer(live):
        brace, name, assign = m.groups()
        if name in SAFE_ENV_VARS:
            uses = re.findall(rf"\$\{{?[!#]?{name}\b", live)
            sets = re.search(rf"(?:^|[\s;&|(]){name}=|-v\s*{name}\b", live)
            if brace == "{" and assign and len(uses) == 1 and not sets:
                continue
        elif not (name.isdigit() or name in ("@", "*", "_")):
            continue
        return (f"${name} carries a value set out of the guard's sight (set --, the last argument "
                f"of the previous command, or an allowed variable); write the value out")
    return None


def _check_git(args):
    i = 0
    while i < len(args) and args[i].startswith("-"):
        a = args[i]
        if a == "-c" or a.startswith("--config-env") or a.startswith("--exec-path"):
            return "git -c / --config-env / --exec-path can make git run a command"
        i += 2 if a in GIT_VALUE_GLOBALS else 1
    if i >= len(args):
        return None
    sub, rest = args[i], args[i + 1:]
    values = GIT_SHORT_VALUE_LETTERS.get(sub, GIT_DEFAULT_SHORT_VALUES)
    for a in rest:
        if _selects(a, GIT_WRITE_OPTIONS, values):
            return f"git {sub} {a} writes a file or runs an external program"
    if sub in GIT_READ:
        return None
    if sub in GIT_SUBCOMMAND_READS:
        lead, reads, bare = GIT_SUBCOMMAND_READS[sub]
        words = list(rest)
        while words and words[0] in lead:
            words.pop(0)
        if not words:
            return None if bare else f"git {sub} with no subcommand word is not a read-only form"
        if (sub == "reflog" and words[0].startswith("-")
                and not {"expire", "delete", "drop"} & set(words)):
            return None                         # git reflog --all is git reflog show --all
        return None if words[0] in reads else f"git {sub} {words[0]} is not a read-only form"
    if sub in GIT_OPTION_MODES:
        listing, writes, values = GIT_OPTION_MODES[sub]
        hit = next((a for a in rest if _selects(a, writes, values)), None)
        if hit:
            return f"git {sub} {hit} is a write form"
        listed = any(_selects(a, listing, values, abbrev=False) for a in rest)
        if sub == "config":
            return None if listed or rest[:1] in (["list"], ["get"]) else (
                "git config without --get, --get-all, --get-regexp or --list can set a value")
        if listed or all(a.startswith("-") for a in rest):
            return None
        return f"git {sub} with a name and no listing option creates a {sub}"
    return f"git {sub} can change the repository"


def _sed_programs(args):
    """The sed programs in `args`, read as GNU sed reads its options: every -e or --expression
    value (attached or the next word), and the first operand only when there is none of those
    and no -f or --file. A program read from a file is not seen."""
    progs, operands, from_option, i = [], [], False, 0
    while i < len(args):
        a, nxt = args[i], (args[i + 1] if i + 1 < len(args) else "")
        if a == "--":
            operands += args[i + 1:]
            break
        if a.startswith("--"):
            name, eq, val = a.partition("=")
            is_e = len(name) > 2 and "--expression".startswith(name)
            is_f = len(name) > 2 and "--file".startswith(name)
            if is_e:
                progs.append(val if eq else nxt)
            from_option |= is_e or is_f
            takes = is_e or is_f or (len(name) > 2 and "--line-length".startswith(name))
            i += 2 if takes and not eq else 1
            continue
        if a.startswith("-") and a != "-":
            for j, ch in enumerate(a[1:], 1):
                if ch in "efl":
                    if ch == "e":
                        progs.append(a[j + 1:] or nxt)
                    from_option |= ch in "ef"
                    i += 0 if a[j + 1:] else 1
                    break
            i += 1
            continue
        operands.append(a)
        i += 1
    return progs if from_option else operands[:1]


def _sed_skip(s, i, delim, brackets):
    """The index just past the `delim` that ends the regex or replacement starting at s[i]; in
    a regex a bracket expression ([/] or [[:alpha:]/]) does not end at `delim`."""
    while i < len(s) and s[i] != delim:
        if s[i] == "\\":
            i += 1
        elif s[i] == "[" and brackets:
            j = i + 1
            j += s[j:j + 1] == "^"
            j += s[j:j + 1] == "]"
            while j < len(s) and s[j] != "]":
                if s[j] == "[" and s[j + 1:j + 2] in (":", ".", "="):
                    end = s.find(s[j + 1] + "]", j + 2)
                    j = end + 1 if end >= 0 else j
                j += 1
            i = j
        i += 1
    return i + 1


_SED_PLAIN_COMMANDS = frozenset("=dDgGhHnNpPxzF")


def _sed_program_writes(s):
    """Why a sed program writes a file or runs a command, or None: a w, W or e command, or an s
    command with the w or e flag, found by reading the program as sed parses it (addresses, !,
    braces, ; and newlines between commands; the text of a, i and c and the argument of r, R,
    b, t, T, :, q, Q, l, L and v skipped). A command letter sed does not have is refused too."""
    n, i = len(s), 0

    def line_end(k, joined=False):
        e = s.find("\n", k)
        while joined and e > 0 and s[e - 1] == "\\":
            e = s.find("\n", e + 1)
        return n if e < 0 else e

    while i < n:
        c = s[i]
        if c in " \t\n;{}!$,~+" or c.isdigit():
            i += 1
        elif c == "#":
            i = line_end(i)
        elif c in "/\\":
            delim = "/" if c == "/" else s[i + 1:i + 2]
            i = _sed_skip(s, i + (1 if c == "/" else 2), delim, True)
            while i < n and s[i] in "IM":
                i += 1
        elif c in "sy":
            delim = s[i + 1:i + 2]
            if not delim or delim in "\\\n":
                return "a sed s or y command the guard cannot read"
            end = _sed_skip(s, _sed_skip(s, i + 2, delim, c == "s"), delim, False)
            i = end
            while i < n and s[i] not in ";\n}":
                i += 1
            if c == "s" and re.search(r"[we]", s[end:i]):
                return "a sed s///w or s///e flag writes a file or runs a command"
        elif c in "wWe":
            return "a sed w, W or e command writes a file or runs a command"
        elif c in "aic":
            i = line_end(i, joined=True)
        elif c in "rR":
            i = line_end(i)
        elif c in ":btTqQlLv":
            while i < n and s[i] not in ";\n":
                i += 1
        elif c in _SED_PLAIN_COMMANDS:
            i += 1
        else:
            return f"a sed program the guard cannot read ({c!r} is not a sed command)"
    return None


def _check_repo_args(rest):
    for a in rest:
        if a in REPO_WRITE_ARGS or a.split("=", 1)[0] in REPO_WRITE_ARGS:
            return f"'{a}' is a write verb of this repo's tools"
    return None


# The ast pass runs when the code parses. It reads open() and its relatives with a literal mode
# ('w', 'a', 'x', 'r+', 'wb' ...) whatever the first argument is, os.open with a write flag,
# shelve/dbm.open unless the flag is 'r', getattr(obj, 'name') when obj.name( is a call the
# regex refuses, and fileinput.input or FileInput with a true literal inplace.
_PY_WRITE_MODE_RE = re.compile(r"[rbtU]*[wax+][rwaxbt+U]*")
# A call is read as a file opener when its name is on _PY_OPENERS or ends in one of
# _PY_OPENER_SUFFIXES (gzip.GzipFile, bz2.BZ2File, lzma.LZMAFile, zipfile.PyZipFile, os.fdopen,
# tarfile.open ...); any call is read by a literal mode= keyword.
_PY_OPENERS = frozenset({"open", "FileIO", "ZipFile", "TarFile"})
_PY_OPENER_SUFFIXES = ("open", "File")
# Modules whose open() takes the path first and the mode second. A method .open on any other
# object (Path(...).open('w'), ZipFile.open(name, 'w')) is read with its first two arguments.
_PY_PATH_FIRST = frozenset({"io", "codecs", "gzip", "bz2", "lzma", "tarfile", "builtins"})
_PY_OS_WRITE_FLAGS = frozenset({"O_WRONLY", "O_RDWR", "O_CREAT", "O_APPEND", "O_TRUNC", "O_EXCL",
                                "O_TMPFILE"})
_PY_OS_WRITE_BITS = os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_APPEND | os.O_TRUNC


def _py_literal(node):
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def _py_write_call(node, aliases=None):
    """The write one ast.Call makes with literal arguments, or None. Names are read through
    `aliases` (_py_aliases), so o.remove() after import os as o is read as os.remove(), and
    exec, eval or compile of literal text is read as code."""
    f, aliases = node.func, aliases or {}
    dotted = _py_dotted(f, aliases)
    name = dotted.rsplit(".", 1)[-1] if dotted else f.attr if isinstance(f, ast.Attribute) else ""
    owner = dotted.rsplit(".", 1)[0] if "." in dotted else ""
    kw = {k.arg: k.value for k in node.keywords if k.arg}
    args = list(node.args)
    m = PY_WRITE_RE.search(f"{dotted}(") if "." in dotted else None
    if m:
        return m.group(0).strip()
    run = name in ("exec", "eval", "compile") and owner in ("", "builtins") and args
    code = _py_fold(args[0]) if run else None
    if code is not None:
        inner = PY_WRITE_RE.search(code)
        what = inner.group(0).strip() if inner else _python_ast_write(code)
        return f"{name}() of code that calls {what}" if what else None
    if name == "getattr" and len(args) > 1 and _py_literal(args[1]):
        base = _py_dotted(args[0], aliases) or ast.unparse(args[0])
        m = PY_WRITE_RE.search(f"{base}.{_py_literal(args[1])}(")
        return m.group(0).strip() if m else None
    if name == "open" and owner == "os":
        flags = args[1] if len(args) > 1 else kw.get("flags")
        for n in ast.walk(flags) if flags is not None else ():
            if (getattr(n, "id", None) in _PY_OS_WRITE_FLAGS
                    or getattr(n, "attr", None) in _PY_OS_WRITE_FLAGS
                    or (isinstance(n, ast.Constant) and type(n.value) is int
                        and n.value & _PY_OS_WRITE_BITS)):
                return "os.open with a write flag"
        return None
    if name in ("input", "FileInput") and owner in ("fileinput", ""):
        flag = kw.get("inplace", args[1] if len(args) > 1 else None)
        if isinstance(flag, ast.Constant) and flag.value:
            return "fileinput with inplace=True rewrites its files"
    if name == "open" and owner in ("shelve", "dbm"):
        flag = args[1] if len(args) > 1 else kw.get("flag")
        return None if _py_literal(flag) == "r" else f"{owner}.open creates or writes a database"
    opener = name in _PY_OPENERS or name.endswith(_PY_OPENER_SUFFIXES)
    if opener or "mode" in kw:
        method = name == "open" and isinstance(f, ast.Attribute) and owner not in _PY_PATH_FIRST
        for c in ((args[:2] if method else args[1:2]) if opener else []) + [kw.get("mode")]:
            s = _py_literal(c)
            if s and _PY_WRITE_MODE_RE.fullmatch(s):
                return f"{name}() with mode {s!r}"
    return None


def _py_dotted(node, aliases):
    """The dotted name an expression stands for, or "": names bound by import ... as, from ...
    import or name = <dotted name> are replaced by what they name, and
    importlib.import_module('m'), __import__('m') and sys.modules['m'] are read as the module m."""
    if isinstance(node, ast.Name):
        return aliases.get(node.id, node.id)
    if isinstance(node, ast.Attribute):
        base = _py_dotted(node.value, aliases)
        return f"{base}.{node.attr}" if base else ""
    if isinstance(node, ast.Call) and node.args and _py_literal(node.args[0]):
        if _py_dotted(node.func, aliases) in ("importlib.import_module", "__import__",
                                              "builtins.__import__"):
            return _py_literal(node.args[0])
    if isinstance(node, ast.Subscript) and _py_dotted(node.value, aliases) == "sys.modules":
        return _py_literal(node.slice) or ""
    return ""


def _py_aliases(tree):
    """{name: dotted name} for import ... as, from ... import and name = <dotted name> bindings."""
    aliases = {}
    for _ in range(2):
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                aliases.update((a.asname, a.name) for a in n.names if a.asname)
            elif isinstance(n, ast.ImportFrom) and n.module and not n.level:
                aliases.update((a.asname or a.name, f"{n.module}.{a.name}") for a in n.names)
            elif (isinstance(n, ast.Assign) and len(n.targets) == 1
                  and isinstance(n.targets[0], ast.Name)):
                d = _py_dotted(n.value, aliases)
                if d and d != n.targets[0].id:
                    aliases[n.targets[0].id] = d
    return aliases


def _py_fold(node):
    """The text of a str expression built only from literals (+ and f-strings without fields)."""
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        a, b = _py_fold(node.left), _py_fold(node.right)
        return None if a is None or b is None else a + b
    if isinstance(node, ast.JoinedStr):
        parts = [_py_fold(v) for v in node.values]
        return None if None in parts else "".join(parts)
    return _py_literal(node)


def _python_ast_write(code):
    """The first write call the ast pass finds, or None. Code that does not parse as Python (a
    heredoc body fed to cat) is left to the regex."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            tree = ast.parse(code)
    except (SyntaxError, ValueError, RecursionError, MemoryError):
        return None
    aliases = _py_aliases(tree)
    for node in ast.walk(tree):
        what = _py_write_call(node, aliases) if isinstance(node, ast.Call) else None
        if what:
            return what
    return None


def _check_python_code(code):
    m = PY_WRITE_RE.search(code or "")
    what = m.group(0).strip() if m else _python_ast_write(code or "")
    return f"Python code calls a file-write API ({what})" if what else None


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


def _python_option(a):
    """(option, value attached in the same token) for a python option cluster: -Sc CODE and
    -cCODE are -c, -Im MOD is -m, -Xutf8 is -X. Any other token is returned as it is."""
    if a.startswith("-") and not a.startswith("--"):
        for j, ch in enumerate(a[1:], 1):
            if ch in "cmXW":
                return "-" + ch, a[j + 1:]
    return a, ""


class _Argv(list):
    """One simple command's words and where its standard input comes from: None, ("text", s),
    ("heredoc", ""), ("file", path) or ("pipe", the upstream command, or None when a subshell
    or group feeds the pipe)."""

    def __init__(self, words, stdin=None):
        super().__init__(words)
        self.stdin = stdin


_STDIN_PATHS = frozenset({"/dev/stdin", "/dev/fd/0", "/proc/self/fd/0"})


def _stdin_text(stdin):
    """The text a command reads on standard input when the guard can read it, else None: a
    here-string's word, the arguments of echo or printf piped in, or what cat with no file
    operand passes on from its own standard input. A heredoc body is checked where it is taken."""
    kind, src = stdin
    if kind == "text":
        return src
    if kind == "heredoc":
        return ""
    if kind == "pipe" and src:
        name = os.path.basename(src[0])
        if name in ("echo", "printf"):
            return " ".join(src[1:])
        if name == "cat" and all(a == "-" for a in src[1:]) and src.stdin:
            return _stdin_text(src.stdin)
    return None


def _stdin_code(stdin):
    """Why Python code read from standard input is refused, or None: a here-string and echo or
    printf text piped in are checked like python -c code, also with their backslash escapes
    decoded; a file or other command output is refused, the guard cannot read it."""
    text = "" if stdin is None else _stdin_text(stdin)
    if text is None:
        return "python reads its code from a file or command output the guard cannot read"
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            decoded = text.encode("latin-1", "backslashreplace").decode("unicode_escape")
    except (UnicodeDecodeError, ValueError):
        decoded = text
    return _check_python_code(text) or _check_python_code(decoded)


def _check_python(args, stdin=None):
    i, script = 0, None
    while i < len(args):
        a, attached = _python_option(args[i])
        following = ([attached] if attached else []) + args[i + 1:]
        if a == "-c":
            return next(filter(None, map(_check_python_code, following or [""])), None)
        if a == "-m":
            mod = following[0] if following else ""
            rest = following[1:]
            if mod in PY_REFUSED_MODULES:
                return f"python -m {mod} installs or writes files"
            if mod.startswith("tools."):
                return _check_script(mod.rsplit(".", 1)[1] + ".py", rest)
            if mod not in PY_READ_MODULES:
                return f"python -m {mod} is not on the read-only module list"
            if mod == "sysconfig" and "--generate-posix-vars" in rest:
                return "python -m sysconfig --generate-posix-vars writes build files"
            if mod == "json.tool" and len([a for a in rest if not a.startswith("-")]) > 1:
                return "python -m json.tool with an output file writes it"
            return _check_repo_args(rest)
        if a in ("-X", "-W", "--check-hash-based-pycs"):
            i += 1 if attached else 2
            continue
        if a == "-":
            return _stdin_code(stdin)
        if a.startswith("-"):
            i += 1
            continue
        script = a
        break
    if script is None or script in _STDIN_PATHS:
        return _stdin_code(stdin)
    return _check_script(os.path.basename(script), args[i + 1:])


def _check_argv(argv, stdin=None):
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
                a, argv = argv[0], argv[1:]
                if not a.startswith("-"):
                    why = _check_env(a)
                    if why:
                        return why
                elif _selects(a, ("-S", "--split-string"), "uCS"):
                    return "env -S runs its string as a command line the guard does not split"
                elif (re.fullmatch(r"-[^-uC]*[uC]", a) or (
                        a.startswith("--") and "=" not in a and len(a) > 2
                        and any(o.startswith(a) for o in ("--unset", "--chdir")))):
                    argv = argv[1:]             # -u NAME, -C DIR: the value is the next word
        elif name in ("timeout", "nice"):
            argv = argv[1:]
            while argv and (argv[0].startswith("-") or re.match(r"^\d", argv[0])):
                a, argv = argv[0], argv[1:]
                if a in ("-s", "-k", "-n") or (a.startswith("--") and "=" not in a and len(a) > 2
                                               and any(o.startswith(a) for o in
                                                       ("--signal", "--kill-after", "--adjustment"))):
                    argv = argv[1:]             # -s SIG, -k DUR, -n N: the next word is the value
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
        return _check_python(args, stdin)
    if name == "find":
        bad = [a for a in args if a in ("-delete", "-exec", "-execdir", "-ok", "-okdir", "-fprint",
                                         "-fprint0", "-fprintf", "-fls")]
        return f"find {bad[0]} can change files" if bad else None
    if name in ("sed", "gsed"):
        if any(_selects(a, ("-i", "--in-place"), SHORT_VALUE_LETTERS["sed"]) for a in args):
            return "sed -i edits files in place"
        return next(filter(None, map(_sed_program_writes, _sed_programs(args))), None)
    if name in ("awk", "gawk", "mawk", "nawk"):
        if any(("system(" in a or _AWK_PRINT_TO_RE.search(a) or "|" in a or "inplace" in a)
               for a in args):
            return "the awk program redirects output or runs a command"
        return None
    if name == "sort":
        if any(_selects(a, ("-o", "--output", "--compress-program"), SHORT_VALUE_LETTERS["sort"])
               for a in args):
            return "sort -o or --compress-program writes a file or runs a program"
        return None
    if name == "uniq":
        positional, i = [], 0
        while i < len(args):
            a = args[i]
            if a == "--":
                positional += args[i + 1:]
                break
            if a == "-" or not a.startswith("-"):
                positional.append(a)
            elif a.startswith("--"):
                i += "=" not in a and len(a) > 2 and any(
                    o.startswith(a) for o in ("--skip-fields", "--skip-chars", "--check-chars"))
            elif re.fullmatch(r"-[^fsw]*[fsw]", a):
                i += 1                          # -f N, -s N, -w N: the next word is the value
            i += 1
        return "uniq with an output file writes it" if len(positional) > 1 else None
    bad = READ_COMMAND_WRITE_OPTIONS.get(name, ())
    hit = next((a for a in args if _selects(a, bad, SHORT_VALUE_LETTERS.get(name, ""))), None)
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
    if name == "hostname":
        hit = next((a for a in args if not (
            re.fullmatch(f"-[{HOSTNAME_READ_SHORT}]+", a)
            or (len(a) > 2 and any(o.startswith(a) for o in HOSTNAME_READ_LONG)))), None)
        if hit:
            return f"hostname {hit} sets the system name; only its display options are read"
    if name == "printf" and args[:1] and args[0].startswith("-v"):
        why = _check_env(args[0][2:] or (args[1] if len(args) > 1 else ""))
        if why:
            return why
    if name == "export":
        for a in args:
            why = None if a.startswith("-") else _check_env(a)
            if why:
                return why
    if name == "command":
        return None                             # command -v / -V print how a name resolves
    if name in READ_COMMANDS:
        return None
    return f"{name} is not on the read-only command list"


def guard(cmd):
    """(allowed, reason) for one Bash command string."""
    if not isinstance(cmd, str):
        return False, "no command string"
    shell, bodies, why = _take_heredocs(cmd)
    if why:
        return False, why
    for body, quoted, text_only in bodies:
        why = ((None if quoted else _body_expansion(body))
               or (None if text_only else _check_python_code(body)))
        if why:
            return False, f"heredoc body: {why}"
    lines, err = _split_lines(shell)
    if err:
        return False, err
    why = _carrier_expansion([_live_text(x) for x in lines]
                             + [re.sub(r"\\.", "", b[0], flags=re.S) for b in bodies if not b[1]])
    if why:
        return False, why
    for line in lines:
        if not line.strip():
            continue
        if _expansion_outside_single_quotes(line):
            return False, "command or process substitution hides the inner command; run it separately"
        why = next(filter(None, map(_check_env, _expansion_assignments(_live_text(line)))), None)
        if why:
            return False, why
        segs, why = _segments(_ansi_c_quotes(line))
        if why:
            return False, why
        for argv in segs:
            why = _check_argv(argv, getattr(argv, "stdin", None))
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
    "git remote -v",
    "git branch -vv",
    "git tag -n5 -l 'v*'",
    "git config --get user.name",
    "git --git-dir .git log -1",
    "cd /repo && grep -n 'def main' tools/*.py | head",
    "ls -la .claude/agents >/dev/null 2>&1",
    "find . -name '*.md' -newer CLAUDE.md",
    "ls tools/{sync_check,tree_pin}.py",
    "find . -name '{a,b}' -print",
    "git log -1 @{u}",
    "sed -n '1,40p' CLAUDE.md",
    "sed -En 's/a/b/p' CLAUDE.md",
    "sed -n '/^w/p' notes.txt",
    "sed -n -e '1,5p' -e '$=' notes.txt",
    "sed '1i # wee' notes.txt",
    "sed 's/[we]/x/g' notes.txt",
    "sed -n '/x/{p;q}' write.txt",
    "sed -n -e p 'w notes.txt'",
    "sort -rn -k2,2 -t, notes.txt",
    "rg --pretty --pre-glob '*.gz' foo",
    "python3 -Bc 'print(1)'",
    "awk '{print $1}' file.txt | sort | uniq -c",
    "python3 tools/count_truth.py",
    "PYTHONDONTWRITEBYTECODE=1 python3 tools/sync_check.py",
    "python3 -c 'import json; print(json.load(open(\"a.json\"))[\"x\"])'",
    "python3 -c \"d = {'a': 1}; print(d.copy())\"",
    "python3 -c \"import copy; print(copy.copy([1]))\"",
    "python3 -c \"import os; print(os.read(os.open('a.json', os.O_RDONLY), 9))\"",
    "python3 -c \"import fileinput; print(sum(1 for _ in fileinput.input('a.txt')))\"",
    "python3 -c \"import fileinput; fileinput.input('a.txt', inplace=False)\"",
    "python3 -c \"import pathlib; print(pathlib.Path('a.json').open().read(9))\"",
    "python3 -c \"import os.path as p; print(p.join('a', 'b'))\"",
    "python3 -c \"import importlib; print(importlib.import_module('json').dumps(1))\"",
    "python3 -c \"exec('print(1)')\"",
    "python3 -c \"import re; print(re.compile('open(x, 1)').pattern)\"",
    "python3 -c 'import sys; print(sys.argv[1])' notes.txt",
    "python3 - <<'EOF'\nimport pathlib\nprint(pathlib.Path('CLAUDE.md').read_text()[:10])\nif 2 > 1: print('ok')\nEOF",
    "grep -c '$(' notes.txt",
    "cat <<'EOF'\n$(this stays text)\nEOF",
    "cat <<< 'a b' | wc -w",
    "echo 'print(1)' | python3 -",
    "python3 - <<< 'print(1)'",
    "python3 -c 'import sys; print(sys.stdin.read())' < notes.txt",
    "cat <<'EOF' | python3 -\nprint(1)\nEOF",
    "echo 'a > b' | wc -c",
    "python3 -m json.tool data.json",
    "python3 -c \"import gzip; print(gzip.GzipFile('x.gz').read(3))\"",
    "python3 -c \"import bz2; print(bz2.BZ2File('x.bz2', mode='rb').read(3))\"",
    "env GIT_OPTIONAL_LOCKS=0 git status --porcelain",
    "env -u HOME git log -1",
    "env -C /tmp git log -1",
    "env --unset HOME -i git status",
    "timeout 30 git log -1",
    "xxd -l 64 CLAUDE.md",
    "hostname",
    "hostname -f",
    "hostname --short",
    "hostname -I",
    "LC_ALL=C sort notes.txt",
    "export LC_ALL=C; git log -1",
    "printf '%s' done",
    "printf $'%s\\n' done",
    "grep -c $'\\t' notes.txt",
    "echo $\"-i\" | wc -c",
    "echo '${PAGER:=x}'",
    "echo \"${HOME:0:3}\" \"${PWD: -4}\"",
    "echo $[1+2] ${x[1]} ${HOME:-a=b} $[1<=2]",
    ": \"${LC_ALL:=C}\"; git log -1",
    "echo \"$HOME\" '$1' \"\\$_\"",
    ": \"${TZ:=UTC}\"; date",
    "python3 -m tokenize tools/tree_pin.py",
    "python3 -c \"import os; print(os.listxattr('.'), os.getxattr('.', 'user.a'))\"",
    "python3 -m sysconfig",
    "uniq -f 1 notes.txt",
    "uniq -s 2 notes.txt",
    "uniq --skip-chars=2 -c notes.txt",
    "awk '$3 > 100' notes.txt",
    "awk '{if ($2 > 1) print $1}' notes.txt",
    "timeout -s KILL 5 git log -1",
    "timeout --kill-after 2 5 git log -1",
    "command -v git",
    "git reflog --all",
    "git reflog -n5 --date=iso",
    "git config --get-urlmatch http.proxy https://example.invalid",
    "cat <<'EOF'\nos.remove('x') is described here\nEOF",
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
    "sed $'-i' 's/a/b/' f",
    "sed $\"-i\" 's/a/b/' f",
    "find . -name x $'-delete'",
    "python3 -c $'import shutil\\x3b shutil.rmtree\\x28\"build\")'",
    "python3 -c $'import pathlib\\x3b pathlib.Path(\"x\").write\\x5ftext(\"y\")'",
    "sort $'-\\x6f' out.txt in.txt",
    "sed 's/a/b/w out' f",
    "sed 's/.*/rm -rf build/e' f",
    "sed 's/a/b/ge' f",
    "sed 's/a/b/gw out.txt' f",
    "sed -n '1w out.txt' f",
    "sed -n '$w out.txt' f",
    "sed '1e rm -rf build' f",
    "sed -e'w out.txt' f",
    "sed --expression='1w out.txt' f",
    "sed -n 's/[/]/x/w out.txt' f",
    "sed -n '/a/,/b/{p;W out.txt\n}' f",
    "sed 's|a|b|;e' f",
    "sed -ne 'p' -e '2!w out.txt' f",
    "sed '2k' f",
    "sed -Ei 's/a/b/' f",
    "sed -ni p f",
    "sort -ro out.txt in.txt",
    "sed --in-pl 's/a/b/' f",
    "sort --outp out.txt in.txt",
    "date --se=2020-01-01",
    "less --log-f=log.txt CLAUDE.md",
    "git grep --open-f=./x.sh main",
    "python3 -Sc 'open(\"x\",\"w\")'",
    "python3 -Im zipfile -c out.zip tools",
    "find . -name '*.pyc' -delete",
    "find . -exec rm {} ;",
    "find . -name '*.pyc' {-delete,-print}",
    "sed {-i,s/a/b/} f",
    "sort {-o,out.txt} in.txt",
    "git grep {-O./x.sh,-e} main",
    "sed -{i..i} 's/a/b/' f",
    "find . -name x -{del,x}ete",
    "sed {{-i,-n},p} f",
    "sort -o out.txt in.txt",
    "awk '{print > \"o\"}' f",
    "uniq -f 1 in.txt out.txt",
    "uniq -s2 in.txt out.txt",
    "uniq --skip-fields 1 in.txt out.txt",
    "uniq -c - out.txt",
    "awk '{print $1 > \"out\"}' f",
    "awk '$3 > 1 {printf \"%s\", $1 >> \"o\"}' f",
    "awk '{printf(\"%s\", $1) > \"o\"}' f",
    "timeout -s KILL 5 rm x",
    "timeout --signal KILL 5 rm x",
    "timeout -k 1 5 rm x",
    "command rm x",
    "command -p rm x",
    "command -- rm x",
    "git reflog --all expire",
    "git reflog -n1 delete HEAD",
    "git reflog --verbose drop",
    "cat <<'EOF' | python3 -\nimport os\nos.remove('x')\nEOF",
    "cat <<'A'; python3 - <<'B'\ntext\nA\nimport os\nos.remove('x')\nB",
    "(cat <<'EOF') | python3 -\nimport os\nos.remove('x')\nEOF",
    "git add -A",
    "git commit -m x",
    "git push origin HEAD",
    "git checkout -- CLAUDE.md",
    "git reset --hard",
    "git stash",
    "git branch -D old",
    "git tag -a v1 -m x",
    "git remote -v add evil https://example.invalid/x.git",
    "git --namespace log commit -m x",
    "git branch -v newbranch",
    "git branch -vv --set-upstream-to=origin/x",
    "git branch -a -vD old",
    "git branch -a --del old",
    "git config --show-origin core.pager cat",
    "git config --get-urlmatch http.proxy https://x --add a.b c",
    "git config --get-color color.x red --replace-all a b",
    "git config --get-colorbool --unset a",
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
    "echo 'import shutil; shutil.rmtree(\"build\")' | python3 -",
    "echo 'import shutil; shutil.rmtree(\"build\")' | python3",
    "python3 <<< 'import shutil; shutil.rmtree(\"build\")'",
    "python3 /dev/stdin <<< 'import shutil; shutil.rmtree(\"build\")'",
    "printf 'import shutil\\x3b shutil.rmtree\\x28\"b\")' | python3 -",
    "cat notes.py | python3 -",
    "python3 - < notes.py",
    "(cat notes.py; echo x) | python3",
    "echo 'import os; os.remove(1)' | (python3)",
    "echo x | env python3 /dev/fd/0 <<< 'import os; os.remove(1)'",
    "cat $(git ls-files) | wc -l",
    "echo `id`",
    "diff <(git show HEAD:a) a",
    "cat <<EOF\n$(rm -rf build)\nEOF",
    "echo '<<EOF'\nrm -rf build\nEOF",
    "cat <<< x\nrm -rf build",
    "cat <<E\"OF\"\nhello\nEOF\nrm -rf build",
    "echo hi # <<EOF\nrm -rf build\nEOF",
    "cat a 1<> b",
    "sudo ls",
    "npm install",
    "GIT_EXTERNAL_DIFF=./x.sh git diff",
    "export GIT_EXTERNAL_DIFF=./x.sh; git diff",
    "printf -v LESSOPEN '|./x.sh %s'; less CLAUDE.md",
    "export GIT_EXTERNAL_DIFF",
    "echo $[GIT_CONFIG_COUNT=1]",
    "echo ${x[GIT_CONFIG_COUNT=1]}",
    "echo ${HOME:GIT_CONFIG_COUNT=1}",
    "echo $[GIT_CONFIG_COUNT++]",
    ": \"${LC_ALL:=C}\" \"${GIT_EXTERNAL_DIFF:=./x.sh}\"; git diff",
    "cat <<EOF\n$[GIT_CONFIG_COUNT+=1]\nEOF",
    ": \"${GIT_EXTERNAL_DIFF:=./x.sh}\"; git diff",
    "set -- 'import shutil; shutil.rmtree(\"build\")'; python3 -c \"$1\"",
    "LANG='import shutil; shutil.rmtree(\"build\")'; python3 -c \"$LANG\"",
    "echo 'import shutil' >/dev/null; python3 -c \"$_\"",
    "echo -delete >/dev/null; find . -name '*.pyc' \"$_\"",
    "set -- tools/setup.py; python3 \"$1\"",
    "set -- -delete; find . $@",
    ": \"${LANG:=import os; os.remove(1)}\"; python3 -c \"${LANG:=x}\"",
    "export LC_ALL=-delete; find . \"${LC_ALL:=x}\"",
    "env GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=core.fsmonitor GIT_CONFIG_VALUE_0=./x.sh git status",
    "env -S'rm -rf build'",
    "env --split-string='rm -rf build'",
    "env -iS'rm -rf build'",
    "env --sp 'rm -rf build'",
    "env -u HOME rm -rf build",
    "env -C /tmp -- rm x",
    "LESSOPEN='|./x.sh %s' less CLAUDE.md",
    "tree -o out.txt",
    "xxd CLAUDE.md out.hex",
    "file -C -m magic",
    "rg --pre ./x.sh foo",
    "rg --hostname-bin=./x.sh --hyperlink-format=default foo",
    "rg --hostname-bin ./x.sh foo",
    "rg -i --hostname-bin=./x.sh foo",
    "sort --compress-program=./x.sh notes.txt",
    "less -o log.txt CLAUDE.md",
    "date -s 2020-01-01",
    "hostname other",
    "hostname --file=/etc/x",
    "hostname -F/etc/x",
    "hostname -F /etc/x",
    "hostname --fi /etc/x",
    "hostname -b other",
    "hostname -s other",
    "python3 -m json.tool a.json b.json",
    "python3 -m zipfile -c out.zip tools",
    "python3 -m sqlite3 new.db",
    "python3 -m timeit -n1 \"import os; os.remove('x')\"",
    "python3 -m sysconfig --generate-posix-vars",
    "python3 -m tools.battery",
    "python3 -c \"__import__('os').remove('x')\"",
    "python3 -c \"import os as o; o.remove('x')\"",
    "python3 -c \"import importlib; importlib.import_module('os').remove('x')\"",
    "python3 -c \"import sys, os; sys.modules['os'].remove('x')\"",
    "python3 -c \"exec('import o'+'s; o'+'s.remove(1)')\"",
    "python3 -c \"o = open; o('x', 'w')\"",
    "python3 -c \"from importlib import import_module as im; getattr(im('shutil'), 'rmtree')('b')\"",
    "python3 -c 'import sys; exec(sys.argv[1])' 'import shutil; shutil.rmtree(\"b\")'",
    "python3 -c 'from os import remove; remove(\"x\")'",
    "python3 -c \"import pathlib; pathlib.Path('x').open('w').write('y')\"",
    "python3 -c \"import pathlib; pathlib.Path('x').open(mode='a')\"",
    "python3 -c \"import os; os.open('out.txt', os.O_CREAT | os.O_WRONLY)\"",
    "python3 -c \"import os; os.setxattr('x', 'user.a', b'1')\"",
    "python3 -c \"import os; os.removexattr('x', 'user.a')\"",
    "python3 -c \"import os; os.chflags('x', 0)\"",
    "python3 -c \"import io; io.FileIO('x', 'w')\"",
    "python3 -c \"import gzip; gzip.GzipFile('x.gz', 'wb')\"",
    "python3 -c \"import bz2; bz2.BZ2File('x.bz2', 'w')\"",
    "python3 -c \"import lzma; lzma.LZMAFile('x.xz', mode='w')\"",
    "python3 -c \"import zipfile; zipfile.PyZipFile('x.zip', 'a')\"",
    "python3 -c \"import h5py; h5py.File('x.h5', mode='w')\"",
    "python3 -c \"open(str('x'), 'w')\"",
    "python3 -c \"import pathlib; getattr(pathlib.Path('x'), 'write_text')('y')\"",
    "python3 -c \"import fileinput; [print(l.upper(), end='') for l in fileinput.input('f', inplace=True)]\"",
    "python3 -c \"import fileinput; fileinput.FileInput('f', True)\"",
    "python3 -c \"from fileinput import input; input(files=('f',), inplace=1)\"",
    "python3 -c \"import pathlib; pathlib.Path('a').rename('b')\"",
    "python3 -c \"import pathlib; pathlib.Path('a').move('b')\"",
    "python3 -c \"import pathlib; pathlib.Path('a').copy('b')\"",
    "python3 -c \"import pathlib; pathlib.Path('a').move_into('d')\"",
    "python3 -c \"import pathlib; pathlib.Path('a').copy_into('d')\"",
]
# Known misses: writes the patterns cannot see. They are ALLOWED here on purpose, so the selftest
# fails if the guard's documented limit ever changes without the docs changing with it.
KNOWN_MISSES = [
    "python3 tools/some_new_writer.py",
    "sed -f edit.sed notes.txt",
    "awk -f prog.awk notes.txt",
    "python3 -c 'import m'",
    "python3 -c \"import pathlib; n = 'write_text'; getattr(pathlib.Path('x'), n)('y')\"",
    "python3 -c \"import pathlib; pathlib.Path('a').replace('b')\"",
    "python3 -c \"import logging; logging.FileHandler('x.log')\"",
    "python3 -c \"import mailbox; mailbox.mbox('x.mbox')\"",
    "python3 -c 'm=\"w\"; f=open(\"x\", m)'",
    "python3 -c \"import codecs; exec(codecs.decode('vzcbeg bf; bf.erzbir(1)', 'rot13'))\"",
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
