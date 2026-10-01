# Cross-surface workflows: web chat to desktop app (Claude, ChatGPT, Gemini)

Creator OS does its real work on the computer where it is installed. Every other app (claude.ai,
ChatGPT, Gemini, on the web or as a desktop app) hands work to that computer through the shared
"Creator OS" folder in Google Drive, the hub described in `docs/DRIVE-HUB.md`. This suite checks
that a request can start in one vendor's web chat, continue in a desktop app, and still leave the
right things behind: preference files, run logs and stamps, feature flags that hold where they can
hold, minority reports (the record of what two sources disagreed on), and a note of where each file
came from.

It is 10 workflows: each vendor's web chat into each vendor's desktop app (a 3 by 3 grid), plus
one round trip through all of them on the same day.

```bash
python3 tools/surface_workflow_check.py              # run them all (exit 0 = the contract holds)
python3 tools/surface_workflow_check.py --list       # the workflows and the open gaps
python3 tools/surface_workflow_check.py --runbook W2 # the steps to try on your own devices
python3 tools/surface_workflow_check.py --json       # a machine-readable report
python3 tools/surface_workflow_check.py --selftest   # the runner's own checks and mutation cases
```

The contract is `skills/creator-core/evals/surface-workflows.json`; the runner is
`tools/surface_workflow_check.py`. The battery runs it on every change and CI runs it as a
blocking step. The contract sits in the creator-core skill's `evals/` folder, so it ships inside
that skill's package; its data is fictional.

## How it works (and what it cannot do)

The web chats and desktop apps cannot be driven from here, so each step an app takes is
**simulated**: the step writes only what that app is declared able to write. The declaration is
its `drive_write` mode in the contract (create; create and update; create, move and trash; and so
on), taken from the vendor help pages listed at the end. The app's row in
`shared/cross-modality/transitions.json` bounds it: the runner refuses a contract that gives a
write mode to an app whose row reaches no store, and refuses a write into a hub area or a local
folder the row cannot reach, judged by where the file actually is (or, for a new file, would land)
rather than where the step says it is; a file name holding a path is refused (selftest checks
`write-outside-target-refused` and `write-create-path-name-refused`). For example, Gemini on the web can only create a new file, so a Gemini step that tries to
edit or delete one is refused, and a step whose refusal the contract did not expect fails the
workflow. Every step on the computer runs
the **real** repo code: the profile mirror (`tools/profile_mirror.py`), the job runner
(`tools/handoff/runner.py`), the inbox scan (`tools/handoff/inbox.py`), the task register merge
(`tools/tasks.py`), the agent-output validator (`tools/validate_agent_output.py`), the coverage
reconciler (`tools/coverage_verify.py`), the connector resolver, and the publishing gate.

Each workflow runs in its own throwaway folder: a hub with the Drive hub layout, a context folder,
a log folder and a Drive API stand-in. The runner points the code at that folder (module paths,
`HOME`, and the default ledger argument of the inbox functions), checks before each computer step
that those still point inside it and refuses the step if one does not (checks
`run-preflight-before-each-real-step`, `preflight-refuses-HOME`, `preflight-refuses-CONTEXT_DIR`
and `preflight-refuses-ledger-default`), and deletes the folder afterwards.

The workflows and probes run inside a **write guard**, a Python audit hook that judges the writes
this process makes through `open` for writing and through the `os` and `shutil` calls that remove,
rename, move, copy or create a file or folder. It refuses and records such a write when it lands
outside the system temporary folder (selftest checks `guard-refuses-open-write`,
`guard-refuses-rename-out`, `guard-refuses-mkdir-outside`, `guard-refuses-rmtree-outside` and
`suite-reports-blocked-write`). It lets through the interpreter's own bytecode cache and nothing
else of that kind: creating a folder named `__pycache__`, and inside one writing a `.pyc` file
named with this interpreter's cache tag or its temporary twin; with a bytecode prefix set
(`PYTHONPYCACHEPREFIX`), creating a folder or writing such a file under that prefix (checks
`guard-exempts-only-bytecode-cache`, `guard-exempts-cache-folder-creation`,
`guard-allows-real-bytecode-write`, `guard-exempts-bytecode-prefix` and the `guard-refuses-*`
checks beside them). The run fails if the guard refused a write or judged none (a guard that saw
nothing proved nothing; checks `suite-fails-on-blocked-write` and
`suite-fails-when-guard-judged-nothing`); the judged count counts write events, so one file
written twice counts two (`suite-judged-counts-each-event`). Outside its view: a write by another
process; a write made inside a C library (SQLite creating its database file, for example); a
write through a file handle opened earlier; `os.mkfifo` and `os.mknod`, which raise no audit
event; an `os` call given a folder handle (`dir_fd`), which the guard skips because its path is
relative to a folder it cannot see; and a file opened relative to a folder handle, which the
guard judges as if it were relative to the current folder.

At the end the runner also compares the files on this computer it could have reached (the repo's
`.local` files, the Creator OS log folder, and the configured hub mirror) with a snapshot taken
before the run. That comparison is advice: it is printed but does not decide the result (check
`suite-ok-ignores-snapshot-advice`), because the real profile mirror agent or a sync client may
change those files during the run. A hub that is not configured or cannot be read is reported as
SKIP.

What it does not do: it does not run the AI models, sign in to any app, or call any vendor. The
model's own judgment (writing the script, choosing which conflict wins) is checked by people and
by the Quality Gates, not here. The "live steps" below are the part only your own devices can
confirm.

## The 10 workflows

| ID | From, to | What it proves |
|---|---|---|
| W1 | claude.ai, then Claude Desktop | A voice change saved on the web as a new dated file is content-checked (a copy holding a credential is refused); claude.ai cannot edit the file in place; once saved at home the mirror copies it, rewrites the "About me and my voice" Doc, logs one summary line and stamps the run `ok`; a second run reports the Doc unchanged |
| W2 | claude.ai, then the ChatGPT desktop app (Codex view) | A job ticket from the web waits while `compute_handoff_enabled` is off, runs once it is on (a result with `human_review_required` and an Outbox report), a Drive conflict copy is skipped, a ticket for a job type that is not allowed is refused, and a ticket trashed from the web before the run leaves nothing behind (gap SW-G10) |
| W3 | claude.ai, then the Gemini desktop app | A low-confidence research result with no minority report fails the validator; a second opinion written through Gemini Spark into the hub Inbox disagrees, and the reconciler keeps the disagreement as a minority report instead of picking a winner; a second opinion that agrees yields no conflict and no review flag |
| W4 | ChatGPT on the web, then the ChatGPT desktop app | A profile export saved through ChatGPT's Google Drive app passes the content check; the contact profile reaches Drive only with the opt-in |
| W5 | ChatGPT on the web, then Claude Desktop | The same task edited on the web and at home, plus a Drive conflict copy that adds one more event, merges with each change once, and each of three re-reads holds the same events in the same order |
| W6 | ChatGPT on the web, then the Gemini desktop app | "Post it now" goes nowhere: the Gemini desktop app has no Creator OS tools; on the computer the publishing gate refuses with live publishing off and makes no network call, while with it on the network spy records the attempt (so the spy is shown to see one); the schedule tool returns a plan for human review with the flag off or on, and calls neither the config loader nor the credentials loader |
| W7 | Gemini on the web, then the Gemini desktop app | Gemini Spark editing the content calendar in a connected folder: a valid edit is mirrored and the Doc updated; a broken edit is refused, stamped `error`, and the Drive copy and Doc keep the last good version; a deleted file keeps its Drive copy |
| W8 | Gemini on the web, then Claude Desktop | Notes in the Inbox: a text note with injected instructions is sealed in Quarantine and recorded; a Word export waits for a Claude session (gap SW-G11); a transcript is proposed, and an in-session escalation to REVIEW is recorded when it is approved; the same transcript saved again is recognized as already handled |
| W9 | Gemini on the web, then the ChatGPT desktop app | "Is my Drive hub on?" is answered by the computer's connector plan, not by pasted text; the export templates carry the Packaging version stamp that tells you how old a pasted pack is |
| W10 | All three web chats and desktop apps, one day | Everything above at once: one engine pass folds it in, and a second pass changes nothing (no new copies, no re-run job, no new ledger rows, no new task events) |

## Live steps (only your devices can do these)

`python3 tools/surface_workflow_check.py --runbook <ID>` prints these for one workflow.

- **W1:** In claude.ai, with the Google Drive connector on, ask Claude to save your voice change as
  a NEW dated file in Creator OS/Profile. In Claude Desktop, ask Creator OS to apply it to
  `voice-profile.local.json` and read the change before it is saved. After the next run, check
  `python3 tools/profile_mirror.py status`; run the sync again and it reports the Doc unchanged.
- **W2:** In claude.ai, ask for a `library_analyze` job ticket in Creator OS/Jobs/queue. In the
  ChatGPT desktop app, open Codex on your Creator OS folder and run
  `python3 tools/handoff/runner.py --hub "<your hub folder>" --once`: gated while the flag is off,
  a result and an Outbox report once it is on. Whether Codex may write to a Drive folder outside
  the folder it opened is not documented; if it is refused, run the same command in Terminal.
- **W3:** In claude.ai, ask for the research as a dated JSON export into Creator OS/Store. On the
  Mac, connect ONLY the hub's Inbox folder to Gemini Spark and ask Gemini for a second opinion
  saved there. In Claude Desktop, ask Creator OS to check both.
- **W4:** In ChatGPT on the web, run `implementation/gpt/profile-import/PROMPT.md` and ask
  ChatGPT to save the JSON as a NEW file in Creator OS/Profile. Continue the Work chat in the
  desktop app; in Codex run `python3 tools/profile_mirror.py check-file "<the file>"`. Claude
  Desktop then proposes `creator-profile.local.json` for you to save by hand.
- **W5:** Save your task list from ChatGPT on the web into Creator OS/Store, change the same task
  in Claude Desktop the same day, then ask Creator OS for the list: each change appears once.
- **W6:** Ask ChatGPT on the web for a posting package, then tell the Gemini desktop app to post
  it: nothing is posted. Posting happens only from the Scheduling Dashboard after you confirm.
- **W7:** Add the "About me and my voice" Doc to a Gem. If you use Gemini Spark, connect only the
  hub's Inbox folder; check `python3 tools/profile_mirror.py status` after any edit.
- **W8:** Use Export to Docs in Gemini on the web, move the Doc into Creator OS/Inbox, and ask
  Claude Desktop to sort the Inbox.
- **W9:** Ask your Gem whether the hub is on (it can only repeat its pasted text), then in Codex
  run `python3 shared/connectors/connectors.py --plan` for the computer's answer.
- **W10:** Do W1, W2, W5 and W8 on one day, let the computer run twice, and check the mirror
  status, Jobs/results, Inbox/Quarantine and the task list.

## Gap ledger

Each open gap has a probe in the contract that confirms the gap is still there. When a gap is
fixed, its probe stops confirming it and the suite fails until the contract and this ledger are
updated together, so closing a gap is always a deliberate change.

| ID | Open gap |
|---|---|
| SW-G1 | No validated field records which vendor's app made a hub file or job. The probe holds while the queue accepts a well-formed ticket with a generic origin, its origins are exactly the generic ones (web, desktop, cowork, mac, other) and its ticket keys exactly the known ones, it refuses each vendor and surface name the probe tries as an origin (every surface id and vendor in the matrix, checked by `origin-candidates-cover-matrix`) and a `surface` key, and the remote MCP connector records `other`; files from ChatGPT and Gemini carry `other` (the free-text `requested_by` field can carry a name, unvalidated) |
| SW-G2 | Job results do not carry the ticket's origin |
| SW-G3 | The job runner and watcher write no log file and no last-run stamp; a run log exists only if the scheduler line captures their output |
| SW-G4 | Minority reports are checked but never saved: job results have no field for one and the validator has no record option |
| SW-G5 | The `google_workspace` setting turns on only Gmail in the connector plan; Calendar, Drive and Docs stay off |
| SW-G6 | Eight capability flags are named by no runtime Python, so they act only through instructions the model reads. The probe's rule: a flag counts as named when any tracked `tools/` or `shared/` Python file (in a copy without git, any such file outside `__pycache__`; check `python-sources-fallback-runs`) quotes it, leaving out the files that only declare or cross-check flags (the setup writer, the drift guard, the count checker and this suite's runner); the expected list is in the contract |
| SW-G7 | Profile import reads ChatGPT exports only; there is no Gemini or claude.ai export prompt |
| SW-G8 | Dated exports of the voice profile, channel context, setup context and content calendar have no merge or proposal path. The probe reads skill descriptions, so a fix worded differently may not trip it |
| SW-G10 | Some Drive connectors can now move and trash files; a queued ticket trashed before the computer runs leaves no result and no record that it existed |
| SW-G11 | Doc exports (a Word file, or a Google Doc stub on a Drive for desktop mirror) skip the offline injection screen and wait for a Claude session; only text files are screened offline |
| SW-G12 | An in-session escalation that refuses a route (QUARANTINE or BLOCK) writes no ledger row |

Closed in this change: **SW-G9**, the task register merge. When the same task had been edited on
both sides, every later read of the unchanged web copy added another copy of the same event,
because events were matched by a sequence number the merge itself renumbers. `merge_tasks` in
`tools/tasks.py` now matches events across copies by every field except that number, as a
multiset (an event repeated inside one log is kept), and leaves its inputs unchanged. One
consequence: the same event recorded with identical fields on two devices is kept once. The tasks
selftest and workflows W5 and W10 pin it. Registers that already hold duplicated events keep them;
new merges no longer add any.

## Mutation cases

The runner's selftest carries a table of mutation cases: each is a one-line change to the runner
(a check switched off, a count replaced by a constant, an argument dropped) and the group of
checks that must fail when it is applied. The tasks selftest carries the same kind of table for
the event merge. The cases were chosen by a reviewer who did not write the code. A case whose
change no longer applies, or that its checks no longer catch, fails the selftest (checks
`mutant-runner-reports-survivor` and `mutant-runner-reports-missing-anchor`). Before the cases, an
unmutated copy must pass every group they name, so a crash the copy itself causes cannot pass for
a caught case (check `selftest-fails-when-control-copy-fails`); a case that leaves the copy unable
to load counts as caught (`mutant-runner-unloadable-copy-is-caught`). The runner applies the cases
only after the write guard has passed its own checks, because some cases try a write outside the
sandbox that only the guard refuses (check `selftest-skips-mutants-when-guard-fails`). After each
case it restores the module settings the sandbox repoints, the loader stand-ins, network spies
and job-runner function a step or check replaces for a while (`mutant-runner-restores-patchables`),
and the import path, and it empties the copy's write-guard stack
(`mutant-runner-clears-every-copy-stack`); the selftest fails if any of those is left changed at
the end (`selftest-reports-leaked-state`). Each copy's audit hook stays installed, inert with an
empty stack, until the process exits. Each case's checks read the copy's own source text
(`mutant-runner-judges-mutated-source`).

## Where the facts come from

The app capabilities the simulated steps rely on were checked against the vendors' own help pages
on 2026-10-01 and are registered in the source registry, so the currency checks re-read them.

```sources
[
  {"id": "claude-google-workspace-connectors", "url": "https://support.claude.com/en/articles/10166901-use-google-workspace-connectors"},
  {"id": "openai-google-drive-app", "url": "https://help.openai.com/en/articles/10929079-google-drive-app-and-setup-in-chatgpt"},
  {"id": "openai-chatgpt-desktop-move", "url": "https://help.openai.com/en/articles/20001276-moving-to-the-new-chatgpt-desktop-app"},
  {"id": "openai-chatgpt-developer-mode-help", "url": "https://help.openai.com/en/articles/12584461-developer-mode-and-mcp-apps-in-chatgpt"},
  {"id": "gemini-export-responses", "url": "https://support.google.com/gemini/answer/14184041"},
  {"id": "gemini-spark-mac", "url": "https://support.google.com/gemini/answer/17208717"},
  {"id": "gemini-custom-mcp-apps", "url": "https://support.google.com/gemini/answer/17209137"},
  {"id": "gemini-mac-app", "url": "https://support.google.com/gemini/answer/17011627"},
  {"id": "gemini-gems-use", "url": "https://support.google.com/gemini/answer/15146780"}
]
```
