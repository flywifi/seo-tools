# Mac validation runbook (local-only, two-phase)

The committed, ordered checklist for validating Creator OS on a real Mac **without touching any
external account**, then handing a clean install to a second user. It reconstructs into one place
the local-only tier of the Mac hands-on checks that previously lived only in session scratchpad
(the P53/P54 sweeps named in `docs/AUDIT-PROTOCOL.md` §6, now gone). Install mechanics live in
`docs/SETUP_MAC.md`; the maintainer "why" behind the launcher/Gatekeeper behavior lives in
`docs/MACOS-MAINTENANCE.md`; dependency posture in `docs/DEPENDENCIES.md`. This file is the
run-it-and-record-it companion.

## Who this is for and what it covers

Two-phase use: **Phase 1**, a technical operator validates the on-device surfaces on the target Mac
under their own Claude account; **Phase 2**, the machine is reset to a clean slate so the real
end user starts from zero. Everything here is local — nothing authenticates to a platform, posts,
or reads a credential.

**In scope (Phase 1):** the launcher/Gatekeeper path, `tools/setup.py` + the private `.venv`, the
transcription doctor + model fetch, the read-only import preview, the Claude Desktop MCP surface,
and the offline engine CLIs.

**Deferred (NOT covered here — each needs a real account and its own prepped session):** all OAuth
and publishing (`tools/wizard.py` `/publishing-setup`, `live_publishing_enabled`, the scheduling
dashboard `tools/dashboard/server.py`), the Google Drive compute hub (`/compute`, `/drive-hub`), and
the remote-MCP connector (`implementation/gpt/mcp-connector/README.md`). The per-platform developer
credentials and the live posting checklist for those live in `docs/PUBLISHING.md`.

## Phase 1 — validate on the target Mac (local-only)

### Prerequisites (once)

- **Python >= 3.11.** The built-in `/usr/bin/python3` is a non-working stub; install the notarized
  python.org universal2 `.pkg` (no Gatekeeper prompt) or `brew install python@3.13`.
- **The repo folder.** Prefer `git clone https://github.com/flywifi/seo-tools.git` — a clone is not
  Gatekeeper-quarantined, unlike a downloaded `.zip`.
- Optional, transcription only: `brew install whisper-cpp ffmpeg` (Apple Silicon, Metal) — or skip
  it and let the doctor install `faster-whisper` via pip, which needs no ffmpeg.

### Install

```
python3 tools/setup.py            # null-starter local files + FTS5 cache + drift guard
python3 tools/setup.py --install-deps   # private .venv toolbox (a few minutes first time)
```

Then either double-click `Start Creator OS Setup.command` or run `python3 tools/wizard.py`; the
wizard opens at `http://localhost:8765`. Pick your AI -> Claude Desktop -> sign in with **your** (the
operator's) Claude account -> finish at `/done` -> **Cmd-Q and reopen Claude Desktop** so it re-reads
the MCP config.

### Validation steps

Run each, compare against "expected", and record the outcome in the results log at the bottom.

- **V1 — Launcher / Gatekeeper.** Double-click `Start Creator OS Setup.command`.
  - Expected: the wizard opens in the browser; Homebrew tools resolve even though a double-clicked
    (non-login) shell omits `/opt/homebrew/bin` (the launcher and `tools/env_paths.py::augmented_path`
    prepend the brew prefixes). If you also test a downloaded `.zip` copy, confirm the first launch is
    blocked and clears via System Settings -> Privacy & Security -> "Open Anyway".
- **V2 — Setup, doctor, and STT model.** `python3 tools/transcribe.py doctor`, then
  `python3 tools/transcribe.py doctor --fetch-model base.en`.
  - Expected: `tools/setup.py` reported the local files created and the drift guard clean; the doctor
    prints a green ("Ready") / amber / red verdict with a per-machine next command; the model download
    is SHA256-verified against `canonical-sources/whisper-models.json` and a corrupt file is deleted,
    never used. Note whether the engine is whisper.cpp+Metal (Apple Silicon) or faster-whisper (Intel).
- **V3 — Import preview (read-only).** In the wizard, open `/import`, pick a folder holding one of the
  operator's own platform exports (Google Takeout / Studio, etc.), and view the scan preview.
  - Expected: a preview of what would be imported, with **nothing written** — `content_import` stays
    off for store-write, so no test data lands in the pipeline store.
- **V4 — Claude Desktop MCP surface.**
  `echo '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | python3 tools/mcp_server.py`
  - Expected: a JSON-RPC response listing the tool definitions (58 at the time of writing; the exact
    figure is whatever `python3 tools/mcp_server.py --selftest` reports for this checkout). Then in
    Claude Desktop, confirm the server spawns and one read-only tool (for example a task scan) returns.
- **V5 — Offline engines (optional, high value).** Run a couple of the pure-offline CLIs the way the
  MCP tools do under the hood, to confirm the on-device engines work on real hardware:
  `python3 tools/tasks.py scan --help`, `python3 tools/coverage_verify.py --help`,
  `python3 tools/finance.py --help` (or a real subcommand against a fixture).
  - Expected: each runs and returns structured output with no network access.

## Phase 2 — reset to a clean slate, then hand off

Phase 1 leaves operator-specific local state. Before the real user starts, reset so their voice
profile and config begin at null. There is no committed teardown tool (verified), so this is a
manual delete plus a re-run of setup.

**System prereqs vs the app (who needs admin):** install Python (the python.org `.pkg`) and any
optional Homebrew/ffmpeg **once from an admin account** — they are system-wide and every login on the
Mac can then use them. The app itself — the git clone, `.venv`, `pipeline/**/*.local.*`, and
`~/.creator-os/` — lives inside one user's home folder, is **per-user, and needs no admin**. On a
personal single-owner laptop the owner's account is usually the admin, so you install Python from it
and run everything there.

**Recommended (cleanest): a separate _Standard_ macOS user account for the real user** (System
Settings -> Users & Groups -> Add Account -> "Standard"). Their own login gives a fresh home
directory, a fresh clone, and a separate `~/.creator-os/`, so there is zero cross-contamination and
the operator's Phase-1 install stays intact for re-testing. **Do NOT use the Guest account** — its
home folder is erased on every logout (the clone, `.venv`, and downloaded model would vanish) and it
cannot install software. On a single-owner laptop you can skip a second account entirely and just use
the "same folder reset" below after the Phase-1 pass.

**Or, same folder reset (delete the gitignored local state, then rebuild the null starters):**

```
rm -f creator-os-config.local.json
rm -f pipeline/user-context/voice-profile.local.json \
      pipeline/user-context/content-calendar.local.json \
      pipeline/user-context/channel-context.local.json \
      pipeline/user-context/setup-context.local.json
# optional, fully regenerable:
rm -rf .venv shared/cache/index.local.db ~/.creator-os/whisper-models
python3 tools/setup.py            # recreates the null starters (it never overwrites, so the delete is required)
```

The delete is required because `tools/setup.py` skips any local file that already exists. After the
reset, the real user signs into **their** Claude account and runs the wizard to build their own voice
profile. If they do not need the local tools on day one, the zero-install path is Claude Projects:
paste `implementation/claude/project/system-prompt.md` into a new claude.ai Project and upload the
files in `implementation/claude/project/knowledge/` (see `docs/SETUP_MAC.md`).

## Safety

Local-only means no external account is touched in Phase 1. Every capability ships default-off in
`creator-os-config.json`; all real data stays in gitignored `pipeline/**/*.local.*`, enforced by
drift invariants 19 to 21 and the pre-commit secret scan. The Phase-2 reset guarantees the
operator's test data does not bleed into the real user's setup.

## Results log (copy per run; fill in on the Mac)

The `docs/AUDIT-PROTOCOL.md` §5/§6 shape: record outcome, then a closing "not exercised" list so a
green result is a coverage statement, not a bare pass.

```
Mac validation run — date: ____  operator: ____  machine (chip/macOS): ____

V1 launcher/Gatekeeper : PASS / BLOCKED / NOT-RUN   notes: ____
V2 setup+doctor+model  : PASS / BLOCKED / NOT-RUN   verdict: green/amber/red  engine: ____  notes: ____
V3 import preview       : PASS / BLOCKED / NOT-RUN   notes: ____
V4 MCP surface          : PASS / BLOCKED / NOT-RUN   tool count: ____  notes: ____
V5 offline engines      : PASS / BLOCKED / NOT-RUN   notes: ____

Not exercised (deferred, real-account tiers): OAuth/publishing, Drive hub, remote-MCP connector.
```
