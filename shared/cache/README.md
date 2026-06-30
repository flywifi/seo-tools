---
file: shared/cache/README.md
role: the scoop tier. Local-first, offline, low-token retrieval over canonical-sources, plus a
  portable hash-verified bucket manifest for distribution.
load: when a spoke needs fast offline lookup of keywords, platform specs, personas, or benchmarks
---

# cache: Creator OS scoop tier

Deterministic, offline, low-token retrieval over the enumerated reference data in
`canonical-sources/`. Instead of loading the full reference files into context, a spoke gets a handful
of ranked snippets plus provenance (source file and record id). The index is regenerable and
gitignored.

## L1 (cache.py): local-first keyword index
Pure stdlib `sqlite3` plus FTS5. Zero token cost at query time. If the host SQLite lacks FTS5, a LIKE
fallback is built and reported honestly. Every result carries its source file, so claims stay
traceable. Never fabricates a match.

```bash
python3 shared/cache/cache.py --build
python3 shared/cache/cache.py --query "moody fall" --limit 5
python3 shared/cache/cache.py --query "renter" --json
python3 shared/cache/cache.py --stats
python3 shared/cache/cache.py --verify
```

## L2 (semantic.py): optional offline semantic recall
Off by default. Activates only when a local vector backend is installed and the user has granted
consent. Absent or declined, it falls back to L1 and says so. No data leaves the machine.

```bash
python3 shared/cache/semantic.py --status
python3 shared/cache/semantic.py --search "adding character to a rental" --k 5
```

## L3 (tools/sync_cache.py): manifest-driven sync and portable buckets
Reuses the L1 sha256 baseline for local drift and produces a Scoop-style bucket manifest, sha256
verified, for portable distribution. Human-approved by default: `--sync` is a dry-run, rebuilding the
index needs `--apply`.

```bash
python3 tools/sync_cache.py --status
python3 tools/sync_cache.py --manifest --write bucket.manifest.json
python3 tools/sync_cache.py --sync
python3 tools/sync_cache.py --apply
```

## How it fits
This tier complements `shared/web-intel-engine.md` (live acquisition) and
`shared/injection-guard-engine.md` (scan). Live retrieval handles fresh external data; the scoop tier
handles the stable canonical reference data offline, and packages analytics or CRM snapshots into a
portable, hash-verified bucket so Creator OS works without constant API polling.
