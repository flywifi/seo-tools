# Roadmap: gated integrations and deferred work

This file is the single honest inventory of code paths that are **intentionally not fully wired**
in the current build: integrations that require a paid app, external hardware, or a component this
process does not own. None of these is a silent gap. Each raises `NotImplementedError` with a
recipe (or is flagged in prose), is gated behind a default-off capability flag, and degrades to a
file-interchange or manual path. This is a maintainer index, not a promise of dates.

For what IS built and gated (the four publishing clients, video-edit interchange, jurisdiction,
finance, tasks, handoff), see `STATE.md` and `docs/DEPLOYMENT.md`. For the flag-by-flag degraded
behavior, see `creator-os-config.json` `degraded_behavior`.

## Not stubs (built, gated off by default)

Do not confuse these with the roadmap items below. The `tools/publishing/` clients
(`youtube.py`, `instagram.py`, `tiktok.py`, `pinterest.py`) are **complete OAuth + upload REST
clients**, gated behind `live_publishing_enabled` (default off). While off they make no network
call; they are not stubs. The video-edit interchange (FCPXML/OTIO/iTT/SRT generation) is likewise
built and gated, not stubbed.

## Genuine stubs (raise `NotImplementedError` with a recipe)

### DaVinci Resolve live scripting
`tools/videoedit/resolve.py` — `import_edit_package`, `add_markers`, `queue_render`,
`export_timeline` each raise with the setup recipe.
<!-- verify: tools/videoedit/resolve.py::import_edit_package -->
<!-- verify: tools/videoedit/resolve.py::queue_render -->
Requires DaVinci Resolve **Studio** (the paid edition; external scripting is Studio-only) installed
and running, plus `resolve_scripting` enabled. Until then the system emits FCPXML/OTIO for manual
import (`bootstrap_env` reports the environment without driving Resolve).
<!-- verify: tools/videoedit/resolve.py::bootstrap_env -->

### Apple Compressor batch encode
`tools/videoedit/compressor.py` — `run` raises with the recipe; `presets_for` computes the
per-platform preset spec offline.
<!-- verify: tools/videoedit/compressor.py::run -->
<!-- verify: tools/videoedit/compressor.py::presets_for -->
Requires Apple Compressor (macOS, paid) and its `Compressor` CLI. Degrades to emitting the encode
spec for a manual run.

### CommandPost automation
`tools/videoedit/commandpost.py` — `trigger` raises; `emit` returns the action payload the creator
can run by hand.
<!-- verify: tools/videoedit/commandpost.py::trigger -->
<!-- verify: tools/videoedit/commandpost.py::emit -->
Requires CommandPost (macOS Final Cut Pro automation) installed and configured.

### remote_mcp store backend
`tools/tasks.py` `save_register(..., backend="remote_mcp")` and the matching read path, plus
`tools/freshness_overlay.py`, raise `NotImplementedError`: the `remote_mcp` persistence backend is
owned by the remote MCP **server** process, not this local process.
<!-- verify: tools/tasks.py::save_register -->
The `local_fs` backend (default) and the Google Drive/Sheets backend are fully wired; `remote_mcp`
is reachable only from inside a deployed remote MCP endpoint (see
`implementation/gpt/mcp-connector/README.md`).

## Documented deferrals (flagged, not raising)

### CEA-608 (.scc) caption export
`tools/videoedit/captions.py` — CEA-608 `.scc` output is deferred and flagged. iTT and SRT are
produced (iTT is one of the three formats Final Cut Pro imports), which covers the round-trip; the
`.scc` binary byte format is the deferred item.

## Intentional runtime states (NOT roadmap gaps)

Listed here only so a reader does not mistake them for unbuilt features:

- **Inbox two-pass `pass2_pending`** (`tools/handoff/inbox.py`): a routed record is deliberately
  marked `pass2_pending` until the in-session semantic injection guard runs on read. This is the
  designed P62 two-pass model, not an unimplemented pass.
- **Handoff runner "unwired type" refusal** (`tools/handoff/runner.py`): every current schema job
  type has a builder; the unwired-type branch is a kept, honest refusal for a future job type, not
  a missing implementation.
