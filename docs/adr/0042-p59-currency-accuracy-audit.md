# 42. P59 Currency/Accuracy Audit (versioning, maintainer files, docs, error logs)

- Date: 2026-07-16
- Status: Accepted

## Context

The automated guards (`version.py --check`, invariant 38, `count_truth.py`, the drift guard) all
passed, but they are blind by design to several accuracy surfaces: dated stamps, selftest
pass-counts quoted in maintainer prose, whether a CHANGELOG release heading corresponds to a real
tag, and whether a result-mapping branch reports failures honestly. Two advisory signals
(doc-freshness invariant 51 and the moving-date invariant 43) were firing uncleared. Four read-only
research agents mapped the surfaces; every load-bearing lead was re-verified directly (count_truth,
version --check, doc_freshness --check, finance --selftest, git tags, the GitHub Releases API)
before any change landed.

## Decision

**Fixed (each traced to a cited, re-verified finding):**
- `versions.json` `updated` re-dated (lagged at 2026-06-30 across P52 to P58; no guard validates it).
- `tools/publishing/MAINTAINER_README.md` invariants 2 and 3 rewritten: since P57, `dispatch()`
  itself enforces the live gate and the human-confirm requirement (`gated`/`unconfirmed` refusals),
  and since P58 the Instagram publisher requires a real `ig_user_id` with no `account_id` fallback.
  The prose still described the pre-P57/pre-P58 behavior.
- Seven stale `finance.py --selftest` pass-count claims (44/59/71) across six finance atom
  maintainer docs corrected to the actual 99. These counts are invisible to the count-truth
  invariant (global totals only) and were unbound in doc-freshness.
- `docs/WIZARD.md`: the server bind is loopback `127.0.0.1` (not "localhost"), and the P57/P58
  request guards (origin check, path confinement, body cap, corrupt-config backup, single-use
  import token) are now described.
- `docs/ARCHITECTURE.md`: the atoms table presented 27 atoms as the installed inventory while 105
  exist; reframed as the founding illustrative subset with the true total stated (now guarded by
  the count-truth invariant).
- `tools/dashboard/server.py`: the scheduler treated any dispatch status outside
  gated/unconfirmed/auth_required as success, so an `ok:false` client refusal (empty_media,
  needs_public_url, upload_failed, no_board, privacy_not_allowed, and a dozen more) was recorded
  as "published" with a null post id. Success is now keyed on `ok` via `_apply_dispatch_result`;
  refusals land as "failed" with the client's error. A new `python3 tools/dashboard/server.py
  --selftest` (9/9) pins the mapping.
- Doc-freshness manifest re-blessed (invariant 51 green), and the finance maintainer docs are now
  content-hash-bound to `tools/finance.py` so the stale-count class is machine-caught next time.
- `docs/PUBLISHING.md` was re-verified line-by-line against the current publishing/oauth code:
  no drift (redirect hosts, gate wording, rotation/refresh claims, default-private all accurate).

**Stale-by-decision (recorded, deliberately NOT changed, per review):**
- The CHANGELOG `[0.1.0] - 2026-07-14` heading and its tag links refer to a GitHub release that has
  not been published (zero tags, zero releases), and `plugin.json` `autoUpdate: true` advertises the
  release-driven update lane. Both stay as-is until the owner publishes the real release. Hand-off:
  run `python3 tools/release.py --plan` where `gh` exists, or dispatch
  `.github/workflows/release.yml`.
- The `creator-os-release` registry entry has `last_checked: null` against its 7-day interval.
  Hand-off: `python3 tools/update_check.py check --apply`.
- The staged volatile corrections stay staged: the NY synthetic-performer moving-date advisory
  (invariant 43) keeps firing by accepted choice
  (`python3 tools/source_currency.py mark-checked ny-synthetic-performer-law --changed` clears it),
  and the EU AI Act Article 50 seed remains unapplied (seeding moves the freshness digest and is a
  deliberate human step).

## Consequences

Every item on the four audited surfaces is verified-current, corrected, or explicitly recorded as
stale-by-decision with its exact remediation command, so the repo's accuracy state is fully
accounted for. The one behavior change is honesty-only: a failed live publish can no longer be
recorded as published. The advisory landscape is exactly one intended signal (invariant 43).

**Verified by:** drift guard clean at 52 invariants; `scenario_check` 9/9; `count_truth`
22/105/129/5/22/5/52/9; `version.py --check` consistent; `doc_freshness --check` all current;
the new dashboard selftest 9/9; `secret_scan --staged` clean on every commit.

Ledger status at record time: `shipped`. Source: `ledger/ledger.json` id
`P59-currency-accuracy-audit`.
