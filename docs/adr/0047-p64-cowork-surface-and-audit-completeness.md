# 47. P64 Cowork as a first-class surface, whole-path input hardening, and audit-completeness machinery

- Date: 2026-07-19
- Status: Accepted

## Context

The 2026-07-18 final audit left two open findings, and the user asked the harder question behind
them: why did multiple otherwise-thorough audits miss both, and what makes the next pass more
complete?

1. **AUDIT-F1 — Cowork absent from the surface model.** The cross-modality model
   (`shared/cross-modality/transitions.json`) held nine surfaces and no Cowork row, while an
   independent artifact built by a different phase for a different purpose —
   `tools/handoff/queue.py::ALLOWED_ORIGINS` and the byte-identical `compute-job.json` origin
   enum — had named `cowork` a first-class origin of work since P60. Nothing reconciled the two
   vocabularies. Cowork is Anthropic's own product, a common way people run Creator OS, and the
   class of runtime the auditor itself executes in; treating it as a footnote inverted the real
   usage distribution.
2. **AUDIT-F2 — the ENAMETOOLONG class.** `pathlib.Path.exists()` suppresses
   ENOENT/ENOTDIR/EBADF/ELOOP but not errno 36, so a >255-byte path component makes `exists()`
   itself raise where a short bad path returns False. A 322-byte argument to
   `obligations.py --scan` produced a raw OSError traceback one line ABOVE the P63 loader guard;
   the same shape existed at five more confirmed sites across finance/obligations plus soft sites
   in accounts/tasks/doctemplates. Every selftest input was sub-boundary, so the class was
   structurally invisible.

Root-cause analysis identified six audit-methodology failures (recorded in full in the P64 plan
and `docs/AUDIT-PROTOCOL.md`): RC1 circular oracle (audits enumerated coverage from the artifact
under test), RC2 vocabulary fragmentation (four uncoordinated surface vocabularies), RC3
own-runtime blindness, RC4 test-input realism (nothing forced boundary inputs), RC5 narrow
fix/narrow guard (invariant 54 certified two function bodies while the crash lived in the
dispatch above them), RC6 no completeness critic (checks-passed with no denominator, no
"not exercised" step).

## Decision

Fix both findings AND close each root-cause mode with a machine-enforced mechanism:

- **Two Cowork surfaces, not one.** `cowork_local` (hypervisor-isolated VM on the user's
  machine: Class A/B/C native, flags enforced, `local_fs` available, local machine required) and
  `cowork_remote` (per-session ephemeral Anthropic-hosted sandbox destroyed at session end:
  Class B/C only via remote MCP connectors, flags not enforced, no `local_fs` store, no local
  machine). Every field value traces to the vendor documentation already registered in the source
  registry; facts the docs do not state (the remote-MCP attach transport, repo-clone semantics)
  carry `needs_verification` entries rather than claims. All five mirror sites (the json,
  `TRANSITION_SURFACE_KEYS`, `docs/TRANSITIONS.md`, the wizard `_SURFACES`, the engine matrix)
  moved in one commit; `render_pair` derives the desktop-to-remote transition losses with no
  authored pair. `docs/INJECTION-TWO-PASS.md` split its merged Cowork row; `docs/DEPLOYMENT.md`
  gained a Cowork (remote) capability column.
- **Origin coverage via an `origins` field + invariant 55.** Every surface row claims the queue
  origins it serves (`_residual_origin_note` claims the deliberate `other` residual), and NEW
  invariant 55 (`check_surface_origin_completeness`, fail-closed) asserts the queue.py enum and
  the schema enum are identical AND every enum value is claimed. The AST extraction reads
  `ALLOWED_ORIGINS` via `ast.literal_eval` without importing the module. Negative tests fired
  verbatim: removing the `cowork` claims produced "origin 'cowork' is in ALLOWED_ORIGINS but no
  transitions surface claims it"; a fake `tablet` origin failed on the enum mismatch.
- **Whole-path hardening + invariant 54 widened in place.** Every filesystem touch reachable
  from a CLI argument in finance/obligations routes through the existing PayloadError machinery
  (the three soft-candidate tools keep their own established error idioms); the taint scan also
  surfaced and guarded a payload-derived invoice-filename write. Invariant 54 keeps its number
  and widens to two layers: named loader bodies (now including tasks/doctemplates plus an
  accounts call-site rule) and an AST taint layer over finance/obligations `main`/`_main`
  flagging any argparse-derived value reaching `exists`/`read_text`/`write_text`/`open` outside
  a try. Tuned against both trees: it failed on the pre-fix tree naming the exact defect sites
  and passes clean on the fixed tree. Every path-taking CLI selftest gained a >NAME_MAX boundary
  case, and selftest summary counts are now derived from a counter, never literals (two lying
  literals found and fixed: obligations "16 of 16" over 18 real checks, tasks "46" over 45).
- **A written audit protocol + an executed model pin.** `docs/AUDIT-PROTOCOL.md` derives its
  coverage sets from the machine-checked model (backed by invariant 55), enumerates the four
  input-boundary classes, requires per-surface empathy legs including both Cowork rows, codifies
  harness honesty, and makes the closing "Not exercised" list mandatory. Scenario S10 gained the
  `cowork-surface-model` leg (seven asserts over the committed json) so the battery executes the
  load-bearing Cowork facts on every run.

## Alternatives rejected

- **Full capability rows for the `mac`/`other` origins:** fabrication. `mac` is the local runner
  already served by the claude_desktop/claude_code toolchains; `other` is a forward-compatibility
  residual by design. Both are claimed via the `origins` field and the residual note instead.
- **A new invariant number for the widened payload check:** widening 54 in place keeps
  one-invariant-one-guarantee; a separate number would imply the old narrow guarantee still
  stands on its own.
- **One merged Cowork row:** the local and remote modes genuinely diverge on every field the
  model exists to capture (flag enforcement, `local_fs`, stdio MCP, machine requirement); a
  merged row would have to hedge exactly where a user needs the answer.

## Consequences

The surface model is complete against an independent oracle and stays that way by build
(invariant count moves 54 to 55, the only count change); a future origin added to the queue
without a surface claim fails the build the day it lands. Every audited CLI returns a clean
envelope on oversize paths, and the widened invariant plus the boundary selftest cases lock the
class. Audit coverage is now derived, not recalled, and an audit without its unexercised list is
incomplete by definition. Honest limit, stated here and in the protocol: no live Cowork session
was driven from this sandbox; the rows carry `needs_verification` entries exactly where the
vendor docs are silent, and those items land on the hands-on checklist rather than being claimed
as exercised. ADRs 0043/0045/0046 keep their historical Cowork wording; this ADR supersedes them
on the surface model. Selftests: finance 105/105, obligations 20/20, accounts 28/28,
tasks 46/46, doctemplates 27/27; scenarios 10/10; drift clean at 55.
