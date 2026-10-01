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
python3 tools/surface_workflow_check.py --selftest   # the runner's own checks
```

The contract is `skills/creator-core/evals/surface-workflows.json`; the runner is
`tools/surface_workflow_check.py`. The battery runs it on every change and CI runs it as a
blocking step.

## How it works (and what it cannot do)

The web chats and desktop apps cannot be driven from here, so each step an app takes is
**simulated**: the step writes only what that app is declared able to write (its `drive_write`
mode in the contract, which must agree with the app's row in
`shared/cross-modality/transitions.json`). For example, Gemini on the web can only create a new
file, so a Gemini step that tries to edit or delete one is refused. Every step on the computer runs
the **real** repo code: the profile mirror (`tools/profile_mirror.py`), the job runner
(`tools/handoff/runner.py`), the inbox scan (`tools/handoff/inbox.py`), the task register merge
(`tools/tasks.py`), the agent-output validator (`tools/validate_agent_output.py`), the coverage
reconciler (`tools/coverage_verify.py`), the connector resolver, and the publishing gate.

Each workflow runs in its own throwaway folder: a hub with the Drive hub layout, a context folder,
a log folder and a Drive API stand-in. The runner points the code at that folder, refuses to run a
computer step while anything still points elsewhere, and deletes the folder afterwards. At the end
it compares the files on this computer it could have reached (the repo's `.local` files, the
Creator OS log folder, and the configured hub mirror) with a snapshot taken before the run. A hub
that is not configured or cannot be read is reported as SKIP, not as a pass.

What it does not do: it does not run the AI models, sign in to any app, or call any vendor. The
model's own judgment (writing the script, choosing which conflict wins) is checked by people and
by the Quality Gates, not here. The "live steps" below are the part only your own devices can
confirm.

## The 10 workflows

| ID | From, to | What it proves |
|---|---|---|
| W1 | claude.ai, then Claude Desktop | A voice change saved on the web as a new dated file is content-checked (a copy holding a credential is refused); claude.ai cannot edit the file in place; once saved at home the mirror copies it, rewrites the "About me and my voice" Doc, logs one summary line and stamps the run `ok`; a second run reports the Doc unchanged |
| W2 | claude.ai, then the ChatGPT desktop app (Codex view) | A job ticket from the web waits while `compute_handoff_enabled` is off, runs once it is on (a result with `human_review_required` and an Outbox report), a Drive conflict copy is skipped, a ticket for a job type that is not allowed is refused, and a ticket trashed from the web before the run leaves nothing behind (gap SW-G10) |
| W3 | claude.ai, then the Gemini desktop app | A low-confidence research result with no minority report fails the validator; a second opinion written through Gemini Spark into the hub Inbox disagrees, and the reconciler keeps the disagreement as a minority report instead of picking a winner |
| W4 | ChatGPT on the web, then the ChatGPT desktop app | A profile export saved through ChatGPT's Google Drive app passes the content check; the contact profile reaches Drive only with the opt-in |
| W5 | ChatGPT on the web, then Claude Desktop | The same task edited on the web and at home, plus a Drive conflict copy, merges with each change once, and merging again adds nothing |
| W6 | ChatGPT on the web, then the Gemini desktop app | "Post it now" goes nowhere: the Gemini desktop app has no Creator OS tools; on the computer the publishing gate refuses with live publishing off and makes no network call; the schedule tool returns a plan for human review with the flag off or on |
| W7 | Gemini on the web, then the Gemini desktop app | Gemini Spark editing the content calendar in a connected folder: a valid edit is mirrored and the Doc updated; a broken edit is refused, stamped `error`, and the Drive copy and Doc keep the last good version; a deleted file keeps its Drive copy |
| W8 | Gemini on the web, then Claude Desktop | Notes in the Inbox: a text note with injected instructions is sealed in Quarantine and recorded; a Word export waits for a Claude session (gap SW-G11); a transcript is proposed, and an in-session escalation to REVIEW is recorded when it is approved |
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
| SW-G1 | No validated field records which vendor's app made a hub file or job; files from ChatGPT and Gemini carry the origin `other`, and the remote MCP connector records `other` too (the free-text `requested_by` field can carry a name, unvalidated) |
| SW-G2 | Job results do not carry the ticket's origin |
| SW-G3 | The job runner and watcher write no log file and no last-run stamp; a run log exists only if the scheduler line captures their output |
| SW-G4 | Minority reports are checked but never saved: job results have no field for one and the validator has no record option |
| SW-G5 | The `google_workspace` setting turns on only Gmail in the connector plan; Calendar, Drive and Docs stay off |
| SW-G6 | Eight capability flags are named by no runtime Python, so they act only through instructions the model reads. The probe's rule: a flag counts as named when any tracked `tools/` or `shared/` Python file other than the setup writer and the drift guard quotes it; the expected list is in the contract |
| SW-G7 | Profile import reads ChatGPT exports only; there is no Gemini or claude.ai export prompt |
| SW-G8 | Dated exports of the voice profile, channel context, setup context and content calendar have no merge or proposal path. The probe reads skill descriptions, so a fix worded differently may not trip it |
| SW-G10 | Some Drive connectors can now move and trash files; a queued ticket trashed before the computer runs leaves no result and no record that it existed |
| SW-G11 | Doc exports (a Word file, or a Google Doc stub on a Drive for desktop mirror) skip the offline injection screen and wait for a Claude session; only text files are screened offline |
| SW-G12 | An in-session escalation that refuses a route (QUARANTINE or BLOCK) writes no ledger row |

Closed in this change: **SW-G9**, the task register merge. When the same task had been edited on
both sides, every later read of the unchanged web copy added another copy of the same event,
because events were matched by a sequence number the merge itself renumbers. `merge_tasks` in
`tools/tasks.py` now matches events across copies by every field except that number, as a
multiset (an event repeated inside one log is kept), and leaves its inputs unchanged; the tasks
selftest and workflows W5 and W10 pin it. Registers that already hold duplicated events keep them;
new merges no longer add any.

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
