# 33. P48 Update Channels Branch Fallback

- Date: 2026-07-14
- Status: Accepted

## Context

The version 0.1.0 is stamped internally but no release/tag artifact exists yet, so the release-only poll returned no_release and the self-update path was inert. The user asked for a backup based on the most recent branch updates, framed as stable vs nightly channels. Read-only, never-nag, opt-in; reverts to release comparison automatically once a release is cut.

## Decision

Added a before-a-release fallback + channel model to the self-update lane. When no GitHub release is published, tools/update_check.py compares the installed commit against a tracked branch (one read-only GitHub compare call) and reports behind_unreleased/current/ahead. A named channel (stable->main, nightly->experimental branch) resolves to a branch via resolve_channel(); tools/update.py pulls the same resolved branch; the wizard /updates screen gained a channel selector writing creator-os-config.local.json.

## Consequences

Ledger status at record time: `accepted`. Source: `ledger/ledger.json` id `P48-update-channels-branch-fallback`.
