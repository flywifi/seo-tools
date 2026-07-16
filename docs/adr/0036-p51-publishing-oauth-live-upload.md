# 36. P51 Publishing Oauth Live Upload

- Date: 2026-07-15
- Status: Accepted

## Context

See the decision below; recorded in the build ledger.

## Decision

Built real publishing OAuth + gated live upload for all four platforms (persona-audit stumbles 8, 9) plus a native folder picker (10). Shared tools/oauth_flow.py runs a per-platform loopback OAuth flow capturing the researched divergences: PKCE base64url for Google, HEX for TikTok, none (confidential) for Pinterest/Instagram; body vs HTTP Basic client auth; TikTok refresh-token rotation persisted. Generalized wizard callback /oauth/<platform>/callback with single-use state CSRF, /api/oauth-start, and a manual paste-the-code fallback (Instagram loopback acceptance is unverified). Fixed the credential clobber: _merge_api_credentials deep-merges and publishing tokens live under creds[plat].publish so they never overwrite importer read tokens; Instagram ig_user_id canonicalized at the root. Live clients (tools/publishing/, all gated behind live_publishing_enabled default-off + human confirmation, all built on an injected transport with zero-network selftests): YouTube resumable upload (default-private, upload-only, provably no monetary/analytics endpoint); Pinterest base64 image Pin (no public URL); TikTok creator_info->init->chunked FILE_UPLOAD->status (SELF_ONLY default, refuses unaudited public, is_aigc); Instagram container->poll->media_publish surfacing the public-URL wall and professional-account requirement honestly instead of faking a local upload. Decision on YouTube: no website-free Production path exists, so the honest flow is Testing mode + ~7-day re-auth, stated on the screen. Native folder picker tools/pick_folder.py (tkinter-in-subprocess + osascript/PowerShell-STA/zenity/kdialog fallbacks + headless degrade) wired as a Browse button on the import and storage screens; the text field stays the floor. Deprecated OOB flow deliberately never implemented. Compliance has_credentials tightened to the publish namespace. Added docs/PUBLISHING.md, an integrations-engine section, and a live-account verification checklist. Drift clean; scenarios 9/9; persona audit 0 orphans, no token leaks.

## Consequences

Ledger status at record time: `accepted`. Source: `ledger/ledger.json` id `P51-publishing-oauth-live-upload`.
