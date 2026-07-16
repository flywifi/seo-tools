# 39. P55 Doc Source Trigger

- Date: 2026-07-16
- Status: Accepted

## Context

The P53/P54 macOS work cited roughly two dozen authoritative sources (Apple security/OS pages,
python.org, PEP 668, Homebrew docs and formulae, MCP and Claude-surface docs) in maintainer prose, but
none were in `canonical-sources/source-registry.json`, so the currency system never freshness-checked
the facts the fixes rest on. Structurally, invariant 46 enforces URL provenance for code
(`tools/**/*.py`) only — a citation in a doc triggered nothing, so any future maintainer note could
cite a source that silently rots.

## Decision

Adopt a declare → generate → enforce loop, fail-closed like invariant 23 (the
requirements-to-registry precedent). A doc declares the external authorities its claims rest on in a
fenced `sources` block (JSON array; a registered id needs `id` + `url`, a new source the full seed
shape) or an inline `<!-- source: an-example-id -->` marker (that placeholder id is the allowlisted
illustration). `tools/source_sync.py` (read-only; never touches the
registry, so the sanctioned five-writer set of invariant 42 is unchanged) reconciles declarations
against the registry and generates a ready seed file for anything unregistered; the human registers it
via `source_currency.py seed-sources`. New drift invariant 52 (`check_doc_source_registry`) fails the
build when a declared id is missing from the registry, a declared URL disagrees, or a block is
unparseable; illustrative ids are exempted in `tools/doc-source-allowlist.json` with written reasons.
Enforcement is opt-in per doc. The 23 macOS/AI-surface sources were seeded first (new `os-platform`
category; registry 218 to 241; freshness bundle restamped), each URL fetch-verified before seeding —
two content mismatches were fixed at the entry level (TN3179 implies rather than states the loopback
exemption, so the explicit Apple DTS FAQ became a companion source; the Claude Desktop local-MCP
article now covers .mcpb extensions, so its entry was re-pointed).

## Consequences

A maintainer citation is no longer inert prose: declaring it forces a tracked registry entry, which
puts the fact on the freshness cadence. Docs that declare nothing are unaffected. The seed generator
never invents fields (incomplete declarations are reported back, not guessed) and writes only a
`.local.` file that cannot be committed. Count-truth ripple handled: the five live-doc invariant
counts moved 51 to 52 in the same change. seo-tools only.

**Verified by:**
- tools/source_sync.py --selftest (13/13); live `check` clean over the 336-file corpus (24 declarations)
- Five inject-and-revert negative tests: unregistered id, URL mismatch, unparseable block, and
  unregistered marker each fail the guard; an exempt id passes
- sync_check.py clean at 52 invariants (catalog integrity green); count_truth.py reports 52;
  build_freshness_bundle.py --check digest matches after the restamp

Ledger status at record time: `shipped`. Source: `ledger/ledger.json` id `P55-doc-source-trigger`.
