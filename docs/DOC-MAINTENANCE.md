# Documentation maintenance model

How Creator OS keeps its maintainer notes, SKILL files, and docs true as the code changes,
and the guardrails that fail the build when a claim drifts. This is the reference for the
whole doc-truth system introduced in P52.

## Principle

Documentation is treated as code: it lives in the repo, changes in the same pull request as
the code it describes, and is checked automatically. A doc claim that names a concrete code
symbol, path, or count is verifiable, so it is verified.

- **Docs-as-code / same-PR rule.** Documentation changes travel with the code change, not in a
  later cleanup pass. See the "docs change in the same PR as the code" rule in `CLAUDE.md`.
  Basis: Google developer-documentation style guide, *Documentation best practices*
  (`developers.google.com/style/`, `docguide/best_practices.html`); Write the Docs,
  *Docs as Code* (`www.writethedocs.org/guide/docs-as-code/`). (Page dates not verified;
  guidance is current practice.)
- **Reference material is generated or checked, never hand-maintained in parallel.** Where a
  doc restates a code fact, a check binds the two. Basis: GitLab's documentation testing,
  which verifies docs against the code they describe (`docs/development/documentation/testing`,
  the `graphql-verify` precedent); Diátaxis on reference documentation
  (`diataxis.fr/reference/`).

## The guardrails (all stdlib, all in `tools/sync_check.py` unless noted)

1. **Path resolution** (invariants 5 and 22). Every backticked path in a SKILL, maintainer,
   `docs/*.md`, `README.md`, or allowlisted `tools/` maintainer doc must resolve to a real file.
2. **Symbol references** (invariant "doc symbol refs"). A doc may assert a code symbol exists
   with a marker: `<!-- verify: tools/finance.py::reconcile -->`. The check resolves the module
   and asserts the symbol is an AST-defined top-level `def`/`class`. Dynamically-defined or
   optional symbols are exempted in `tools/doc-verify-allowlist.json`, each with a reason.
   Precedent: GitLab `graphql-verify`; Python stdlib `doctest`
   (`docs.python.org/3/library/doctest.html`) as the general "executable-doc" idea.
3. **Count truth** (invariant "doc count truth", `tools/count_truth.py`). Global-total claims
   (spokes, atoms, skills, invariants, scenarios, agent roles) are recomputed from the tree and
   must match every live-doc claim. Dated phase-log lines in `STATE.md` and `ledger/` are exempt.
4. **URL provenance** (invariant "url provenance"). Every `http(s)://` literal in `tools/**/*.py`
   must be declared in `source-registry.json`, the operational-URL sidecar allowlist, or the
   excluded-by-rule set.
5. **Content-hash staleness stamping** (`tools/doc_freshness.py`; and, for the knowledge packs,
   `tools/projection_manifest.py`). A manifest binds each high-value doc to the code files it
   describes and records their sha256 at reconcile time; `--check` flags "may be stale" when a
   bound source moves. **Advisory by default.** See the caveat below.
6. **Tools-layer maintainer coverage.** Allowlisted `tools/` directories
   (`TOOLS_MAINTAINER_DIRS`) must each carry a `MAINTAINER_README.md`, and those files are
   reference-checked like skill maintainer docs.
7. **Doc-declared source registration** (invariant "doc source registry", P55; fail-closed like
   the dependency-registry invariant). A doc that cites external authorities declares them in a
   fenced `sources` block (a JSON array; registered ids need `id` + `url`, new sources the full
   seed shape `id`/`name`/`url`/`category`/`tier`) or an inline `<!-- source: an-example-id -->`
   marker. Every declared id must exist in `canonical-sources/source-registry.json` with a
   matching URL, and an unparseable block fails the build too, so a maintainer citation cannot
   silently sit outside the freshness system. `tools/source_sync.py reconcile` (read-only) writes
   the seed file for a new declaration; the human registers it with
   `source_currency.py seed-sources`. Illustrative example ids are exempted in
   `tools/doc-source-allowlist.json`, each with a written reason. Enforcement is opt-in per doc:
   a file with no block and no marker is untouched. Full model: `docs/CURRENCY.md`
   "Doc-declared sources".

## Process conventions

- **CODEOWNERS** (`.github/CODEOWNERS`) maps each component and its maintainer doc to the same
  owner, so a code PR pulls in the doc owner. **Advisory only** for now: this is a solo-maintainer
  project (owner `@flywifi`, a public handle, not PII), and "Require review from Code Owners"
  branch protection would lock out a sole owner who cannot approve their own PR. To turn it into a
  hard gate when a second maintainer joins: in GitHub repo Settings, enable branch protection on
  `main` and check "Require review from Code Owners". Basis:
  `docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners`;
  required-reviewer general availability (GitHub Changelog, 2026-02-17).
- **Architecture Decision Records** (`docs/adr/`, MADR format). ADRs 1 to 5 are the foundational
  architecture decisions; ADRs 6 and up are a faithful reformat of the decision records in
  `ledger/ledger.json`. New decisions get the next number from `docs/adr/0000-template.md`.
  Basis: `adr.github.io`; Michael Nygard, *Documenting Architecture Decisions* (2011); MADR
  (`adr.github.io/madr/`).
- **Changelog** (`CHANGELOG.md`). Keep a Changelog 1.1.0 (`keepachangelog.com`) + Semantic
  Versioning 2.0.0 (`semver.org`). Reconstructed from `STATE.md` + `ledger/ledger.json`; kept
  current going forward, newest-first, grouped Added/Changed/Deprecated/Removed/Fixed/Security.
- **Link checking** (optional, when a link-checker is available): lychee
  (`github.com/lycheeverse/lychee`) is the recommended external tool for catching dead URLs in
  docs; the repo does not vendor it.

## Honest caveat: staleness stamping is emerging practice, not a standard

The content-hash / last-reviewed staleness stamping in guardrail 5 is adopted as sound
engineering, mirroring the repo's own projection-manifest precedent (invariant "projection
staleness"). It is **not** backed by a named external standard. The strongest external anchor is
only the general "keep documentation fresh" guidance (e.g. Google's style guide). It is a
staleness *signal* (the sha of a bound source moved), not a proof the prose is wrong, and prose
cannot be byte-compared to its source. That is why it ships **advisory**, not as a build-breaker.
Do not present it as a cited industry standard.

## When you change code

1. Update the maintainer/SKILL/docs prose in the same change.
2. If you added or renamed a symbol a doc names, update or add its `verify:` marker.
3. If you changed a global count (a spoke, atom, invariant, scenario), fix every live-doc claim.
4. If the prose cites a new external authority, declare it in the doc's `sources` block and seed it
   (`python3 tools/source_sync.py reconcile`, then `source_currency.py seed-sources <generated>`,
   then `build_freshness_bundle.py --apply` since new source ids move the freshness digest).
5. Run `python3 tools/sync_check.py` (and `tools/doc_freshness.py --check`); reconcile the
   staleness manifests if a bound source legitimately changed.
6. Add a `CHANGELOG.md` entry under Unreleased; record any architectural decision as an ADR.

## Known guard-shallowness backlog (P65 audit, documented deliberately, not yet rebuilt)

The P65 full-system audit designed (but did not individually verify) false-negative recipes
against three agent-contract invariants whose checks are marker- or substring-based. They are
recorded here with drafted property-level fixes rather than rebuilt now: deepening all three at
once risks a false-positive storm against a green tree, and none is reachable by accident today
(the P66 remediation closed every VERIFIED instance; invariants 15/36/54/55 were hardened for
real). Pick these up as a dedicated hardening phase, tuning each against pre/post trees:

- **Invariant 14 (agent-definition sections).** Presence of the `## Forbidden tools` /
  `## Allowed tools` headers plus tool-name substrings is enough to pass; a definition could
  carry the headers with an empty or contradictory body. *Drafted fix:* parse the section body
  and require at least one list item per section, and assert the allow/forbid sets are disjoint.
- **Invariant 16 (workflow adversarial step).** A marker string (for example `adversarial-verify`)
  anywhere in the workflow file passes — including inside a comment — without a real second-agent
  step. *Drafted fix:* AST-parse the workflow script and require an `agent()` call whose prompt
  consumes the primary agent's output variable after the primary call.
- **Invariant 17 (read-only mandate marker).** The mandate marker is a substring test; a
  definition could quote the marker while granting write tools. *Drafted fix:* cross-check the
  marker against the definition's Allowed-tools list (no Write/Edit/Bash-mutation tool may
  appear).

The class rule going forward (from the audit): a guard must verify the PROPERTY it protects, not
the presence of a token that usually accompanies the property.
