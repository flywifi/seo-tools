# Creator OS — Claude Desktop Setup (Full Capability)

Claude Desktop + the Creator OS MCP server gives you capabilities that no
knowledge-only setup can match:

| What you get | How it works |
|---|---|
| Competitor video tag extraction | `competitor_scan` tool fetches ytInitialPlayerResponse hidden metadata |
| Offline FTS5 keyword cache | `cache_query` tool hits the local SQLite index without API calls |
| Source staleness detection | `source_staleness` tool reads source-registry.json intervals |
| Deterministic quality scoring | `quality_score` tool runs score.py with your dimension ratings |
| Drift guard on demand | `drift_check` tool runs sync_check.py live |
| Add competitors to tracker | `add_competitor` tool upserts into source-registry.json |

---

## Prerequisites

Python 3.11 or later.

Recommended (installs every dependency into a private `.venv` toolbox, so a Homebrew Python's
install lock never blocks it):

```bash
# From the seo-tools repo root:
python3 tools/setup.py --install-deps
```

This creates `.venv/` (gitignored) and installs the fetch, scraper, MCP, and Playwright sets into
it. Advanced: to install by hand, create a venv first so PEP 668 does not block a Homebrew Python
(`python3 -m venv .venv && ./.venv/bin/python -m pip install -r requirements-mcp.txt …`).

Build the keyword cache:

```bash
python3 shared/cache/cache.py --build
python3 shared/cache/cache.py --stats     # confirm index built
```

---

## Install the MCP server

1. Find your absolute path to the `seo-tools` directory:
   ```bash
   cd seo-tools && pwd
   # e.g. /Users/matt/projects/seo-tools
   ```

2. Open `claude_desktop_config_snippet.json` in this folder. Replace every
   `REPLACE_WITH_ABSOLUTE_PATH` placeholder with the path from step 1. The `creator-os` `command`
   must be an **absolute** interpreter path — use `.venv/bin/python3` inside the repo (created by
   the install above), e.g. `/Users/matt/projects/seo-tools/.venv/bin/python3`. A bare `python3`
   can fail because Claude Desktop launches servers with its own narrow PATH.

3. Open your Claude Desktop config file:
   - macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
   - Windows: `%APPDATA%\Claude\claude_desktop_config.json`

4. If the file already has an `mcpServers` key, add the `"creator-os"` block
   inside it. If it does not exist, create the file with the full snippet.

5. **Completely quit Claude Desktop (Cmd-Q on macOS) and reopen it** — closing the window is not
   enough; the config is only read at launch. If the Creator OS tools do not appear, check
   `~/Library/Logs/Claude/mcp-server-creator-os.log` for a startup error (a wrong or non-absolute
   interpreter path is the usual cause).

---

## Verify

After restart, open any conversation and ask:

> Run a drift check on Creator OS.

Claude will call the `drift_check` MCP tool and return "DRIFT GUARD: clean"
if everything is wired up correctly.

Then ask:

> Query the cache for "moody fall decor".

You should see ranked keyword snippets from `canonical-sources/`.

---

## First run — competitor intelligence

Add a competitor channel:

```bash
python3 tools/competitor_snapshot.py --add-competitor https://www.youtube.com/@ChannelName --platform youtube
```

Then fetch the snapshot (run outside Claude — this hits the network):

```bash
python3 tools/competitor_snapshot.py --fetch
python3 tools/competitor_snapshot.py --parse
```

Now ask Claude:

> Show me the competitor tags and chapter markers for yt-channelname.

Claude calls `competitor_scan` and returns the hidden video tag list extracted
from `ytInitialPlayerResponse` — data not visible in the YouTube UI and not
returned by the YouTube Data API for competitor videos.

---

## Capability notes

- `competitor_scan` is read-only from the MCP side. The `--fetch` step must be
  run manually or via the weekly GitHub Actions cron. This is intentional: live
  fetches use rate governor politeness delays that would block a conversation.
- `add_competitor` writes to `source-registry.json` only via `source_currency.py`,
  preserving the write-isolation guarantee in CLAUDE.md.
- `quality_score` accepts the 9 dimension scores you supply; it does not judge
  the artifact itself. Run it after a quality-review spoke output to get the
  deterministic release verdict.
