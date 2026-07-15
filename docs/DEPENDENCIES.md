# Creator OS — Dependency Inventory

Single source of truth for every external dependency Creator OS can use: pip packages, MCP servers,
system binaries, runtimes, model weights, and API-key connectors. Built from an `ast`-parsed import
scan of every `.py`, all `requirements-*.txt`, `shared/connectors/connectors.json`,
`canonical-sources/dependency-sources-seed.json`, `docs/STATISTICS.md`, and every `SKILL.md`.

**Golden rule:** every third-party import in the codebase is `try/except`-guarded. Base function
(routing, protocols, the CRM/pipeline stores, the drift guard's core, all offline math) runs on the
Python standard library alone. Everything below is an accelerator that degrades honestly when absent.

**Default install:** `tools/setup.py` installs the free, cross-platform, no-key pip set plus the
uvx/Node/ffmpeg toolchain (see "Default-installable vs opt-in" at the end). Keyed, paid, macOS-only,
and heavy native runtimes are opt-in and cannot be installed-and-working by default.

---

## A. Python packages (pip)

| Package | requirements file | Imported by | Purpose | Degrades to |
|---|---|---|---|---|
| `mcp` | requirements-mcp.txt | tools/mcp_server.py | Claude Desktop tool surface | no MCP tools (CLI still works) |
| `requests` | requirements-crawl.txt | tools/fetch_resilient.py | resilient fetch prong | stdlib urllib |
| `charset-normalizer` | requirements-crawl.txt | via requests | encoding detect | best-effort decode |
| `beautifulsoup4` | requirements-scraper.txt | tools/parse_competitor_meta.py | competitor HTML parse | regex/JSON-LD parse |
| `playwright` | requirements-render.txt | tools/acquire.py, fetch_resilient.py | headless Chromium render | static fetch only |
| `faster-whisper` | requirements-transcribe.txt | tools/transcribe.py | local STT (Win/Linux/Intel Mac) | run_local_stt gap |
| `jiwer` | requirements-transcribe.txt | accuracy | WER/MER/WIL | shared/docintel/wer.py |
| `scenedetect` | requirements-videoedit.txt | tools/videoedit/mediaprobe.py | scene/chapter cuts | ffmpeg scdet / none |
| `opencv-python-headless` | requirements-videoedit.txt | scenedetect dep | frame analysis | none |
| `av` (PyAV) | requirements-videoedit.txt | tools/videoedit/mediaprobe.py | in-process silence detect | ffmpeg binary |
| `numpy` | requirements-videoedit.txt | tools/videoedit/mediaprobe.py | frame-array math | stdlib path |
| `moviepy` | requirements-videoedit.txt | tools/videoedit/reframe.py | Shorts reframe render | geometry-only |
| `opentimelineio` + adapters | requirements-videoedit.txt | otio_core.py, preflight.py | timeline interchange | native writers |
| `python-dateutil` | requirements-tools.txt | tools/tasks.py | recurrence / date math | stdlib approximation |
| `sqlite-vec` | requirements-tools.txt | shared/cache/semantic.py | semantic-cache vector search | lexical match |
| `PyYAML` | requirements-tools.txt | tools/sync_check.py | SKILL.md frontmatter parse | regex parse |

Every package above has a `software-dependency` entry in `source-registry.json` (via
`dependency-sources-seed.json`), enforced by **drift invariant 23**. `tools/dependency_currency.py`
checks version drift against PyPI token-free.

---

## B. External MCP servers (launched by Claude Desktop) — all optional

Canonical transports per `shared/connectors/connectors.json`, `docs/STATISTICS.md`, and
`implementation/claude/desktop/claude_desktop_config_snippet.json` (these agree; the
`configure-stats-tool` atom was reconciled to them in P50).

| Server | Runtime | Command | Key / extra |
|---|---|---|---|
| creator-os (first-party) | **python3** | `tools/mcp_server.py` | `mcp` pip pkg |
| google-workspace | **uv** (uvx) | `uvx workspace-mcp --tool-tier core` | Google OAuth OR claude.ai native |
| microsoft-365 | **Node 20+** (npx) | `npx -y @softeria/ms-365-mcp-server` | device-code login |
| wolfram-alpha | **uv** (uvx) | `uvx mcp-wolfram-alpha` | `WOLFRAM_APP_ID` (free tier) |
| e2b-code-interpreter | **Node** (npx) | `npx -y @e2b/mcp-server` | `E2B_API_KEY` |
| stats-compass | **python3** | `python3 -m stats_compass_mcp` | none |
| duckdb-analytics | **Node** (npx) | `npx -y @motherduckdb/mcp-server-motherduck` | none (local) |
| jupyter-notebook | **python3** | `python3 -m jupyter_mcp_server` | none |
| r-statistics | **pip + R** | `rmcp` (`pip install rmcp`) | R language installed |
| monte-carlo | `[NEEDS VERIFICATION]` | `MCS-MCP` | runtime unconfirmed upstream |
| scikit-learn | `[NEEDS VERIFICATION]` | `mcp-server-scikit-learn` | runtime unconfirmed upstream |

**Node.js is required by exactly: microsoft-365, e2b, duckdb.** NOT Google, NOT Wolfram (both uvx/Python).

---

## C. System binaries / runtimes (OS package manager or static build) — all optional

| Binary | Needed by | Install | Platform |
|---|---|---|---|
| `uv` | uvx MCP servers (google, wolfram) | `pip install uv` (auto by wizard) | all |
| `Node.js 20+` | npx MCP servers (ms365, e2b, duckdb) | brew / nodejs.org / apt | all |
| `ffmpeg` | videoedit silence/encode, transcribe | brew / apt or static build | all |
| `mlt` / `melt` | videoedit MLT writer/render | Shotcut/Kdenlive bundle | all |
| `whisper.cpp` (`whisper-cli`) | STT on Apple Silicon (Metal) | `brew install whisper-cpp` | Apple Silicon |
| `R` language | r-statistics MCP (rmcp) | brew / apt / CRAN | all |
| DaVinci Resolve **Studio** (paid) | resolve_scripting | vendor install | mac/win/linux |
| Apple Compressor (paid) | compressor_presets | Mac App Store | macOS only |
| CommandPost | commandpost_macros | vendor install | macOS only |
| whisper GGML model weights | whisper.cpp | download once (148 to 488 MB per tier) | data, not a pkg |

macOS notes: no user-usable stock `python3` (install via `brew install python` or the notarized
python.org universal2 `.pkg`); Homebrew bottles and the python.org pkg are notarized so Gatekeeper
does not prompt; a downloaded static ffmpeg carries `com.apple.quarantine` (remedy
`xattr -dr com.apple.quarantine <path>` or System Settings to Privacy & Security to Open Anyway).
`faster-whisper` needs no system ffmpeg (bundles PyAV) — the escape hatch when ffmpeg is hard to
install.

---

## D. Capability to dependency map (which atoms/skills light up)

- **video-development / footage_breakdown** to ffmpeg, av (PyAV), scenedetect, numpy
- **shorts-reframe** to moviepy, ffmpeg
- **content-library / library-complete / transcript-import** to faster-whisper OR whisper.cpp, jiwer, ffmpeg
- **deep-competitor-scan** to playwright (Pinterest full), requests, beautifulsoup4
- **analytics-compute + configure-stats-tool** to at least one stats MCP (see section B). This spoke is
  the ONLY place a stats MCP is required; it refuses/gaps when none is connected. Every other
  media/STT/stats dependency degrades honestly.
- **task-plan / scheduling** to python-dateutil
- **web-intel semantic cache** to sqlite-vec
- **creator-core + all MCP tool use** to the `mcp` pip package + python3

---

## E. Runtime shell-outs / env-var gates (non-import deps)

System binaries probed via `shutil.which` / `subprocess` (all degrade unless noted): ffmpeg, ffprobe,
melt, whisper.cpp CLI, nvidia-smi (CUDA proxy), xmllint (falls back to ElementTree), auto-editor
(probe only), Chromium (Playwright's browser), brew, node, uv/uvx, npx. `git` is hard-required for the
update/hook/secret-scan/sync flows; `gh` is optional (release).

Env-var gates (absent to a gap, never a fabricated result): `WHISPER_CPP_MODEL`, `WHISPER_MODEL_DIR`,
`GOOGLE_OAUTH_CLIENT_ID`/`_SECRET`, `E2B_API_KEY`, `WOLFRAM_APP_ID`, `EASYPOST_API_KEY`/`SHIP24_API_KEY`,
`GITHUB_TOKEN`/`GH_TOKEN` (rate-limit lift only), `CREATOR_OS_UPDATE_REPO`/`_CHANNEL`/`_BRANCH`,
`REQUESTS_CA_BUNDLE` (proxy CA bundle).

Model weights fetched at runtime (not packaged): whisper.cpp GGML (`ggml-*.bin`, streamed from Hugging
Face and sha256-verified against `canonical-sources/whisper-models.json`); faster-whisper models
(auto-download to the Hugging Face cache on first run).

macOS-app / stub-gated (raise until flag + app present, then degrade to file interchange): DaVinci
Resolve Studio + fusionscript, Apple Compressor, Final Cut Pro (DTD/version probe), CommandPost.

---

## F. API-key-only connectors (no installable package)

All optional, gated by a capability flag; runtime is either the host AI's native integration or stdlib
`urllib`: YouTube (Data/Analytics/Publishing), Instagram Graph, TikTok (Content/Research/Display),
Pinterest v5, EasyPost / Ship24 shipment tracking, Google Workspace (native or uvx), Microsoft 365
(via ms-365-mcp). Optional ML tiers named in config with no package pinned: sentence-transformers/NLI,
pyproj.

---

## G. Default-installable vs opt-in

**Default-installable** (free, cross-platform, no key — `tools/setup.py` installs these):
- All pip sets: requirements-crawl, -scraper, -render (+ `playwright install chromium`), -mcp,
  -videoedit, -transcribe, -tools.
- Toolchain from the launcher/bootstrap (needs the user's shell, not a browser POST): `uv`, Node 20+,
  ffmpeg — via brew / winget / apt.
- One default whisper GGML model (RAM-based tier).

**Opt-in only** (a key, a paid/macOS-only app, or a heavy native runtime — cannot be
installed-and-working by default): E2B (`E2B_API_KEY`), Wolfram (`WOLFRAM_APP_ID`), all platform APIs
(YouTube/IG/TikTok/Pinterest OAuth), R language + rmcp, DaVinci Resolve Studio, Apple Compressor,
CommandPost, mlt/melt, the jurisdiction GIS stack (GDAL/GEOS/PROJ, shapely, fiona, pyproj).

---

## H. Historical drift, now resolved (P50)

- `configure-stats-tool` SKILL.md + evals previously used different server names and runtimes than the
  canonical registry (e.g. `@anthropic/wolfram-alpha-mcp` via npx instead of `uvx mcp-wolfram-alpha`).
  Reconciled to `docs/STATISTICS.md` + the config snippet.
- `python-dateutil`, `numpy`, `sqlite-vec`, and `PyYAML` were imported but undeclared in any
  requirements file. Now declared (numpy in -videoedit; the other three in -tools) and seeded as
  `software-dependency` sources so drift invariant 23 tracks them.

Remaining `[NEEDS VERIFICATION]`: the Monte-Carlo (`MCS-MCP`) and scikit-learn
(`mcp-server-scikit-learn`) server runtimes are unstated upstream — confirm pip vs npm before writing a
launch command. Jupyter and stats-compass PyPI package names (`jupyter-mcp-server`,
`stats-compass-mcp`) differ from their launch modules (`jupyter_mcp_server`, `stats_compass_mcp`);
both are recorded above.
