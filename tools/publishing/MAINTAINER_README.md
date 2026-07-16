---
file: tools/publishing/MAINTAINER_README.md
purpose: preserve the non-negotiable safety + data-model invariants of the live publishing layer so a
  future edit cannot silently break them. This is the tools-layer maintainer doc (the skills/ maintainer
  READMEs do not cover tools/).
---

# tools/publishing: Maintainer README

## Purpose
The credentialed, network-touching publish path for YouTube, Instagram, TikTok, and Pinterest. Owns:
the per-platform OAuth token model (shared with `tools/oauth_flow.py`), the four live API clients, and
the `dispatch()` seam (`__init__.py`). Its job ends at "produce a `{ok, status, post_id, permalink,
error}` result for one human-confirmed post." It never decides *whether* to post — that gate lives in
`tools/publishing_compliance.py` + the dashboard/scheduler. No network call happens unless
`live_publishing_enabled` is on (default off) AND the specific entry was human-confirmed.

## Non-negotiable invariants (do NOT weaken without an approval-gated change)
1. **Token data model.** Publishing tokens live under `creds[plat]["publish"]`; the importer's
   read-token lives at `creds[plat]` root. Never assign a whole platform object
   (`creds[plat] = {...}`) — deep-merge via `wizard._merge_api_credentials`, or you silently wipe the
   importer's token. `<!-- verify: tools/wizard.py::_merge_api_credentials -->`
2. **Instagram identity key.** The IG account id is canonical at `creds["instagram"]["ig_user_id"]`
   (platform root). The importer reads *only* `ig_user_id`, and since P58 (A2c) the publisher requires
   a real `ig_user_id` too — it does NOT fall back to `account_id` (usually the linked Facebook Page
   id, the wrong object type for `/{id}/media`). Every new writer MUST set `ig_user_id`.
   `<!-- verify: tools/importers/instagram_import.py -->`
3. **Live gate + human confirm are structural.** Since P57 (F2/F8), `dispatch()` itself ENFORCES both
   gates before touching any client: it refuses with `status:"gated"` unless
   `publishing_compliance.live_publishing_enabled(config)` (or an explicit `allow_live=True`) holds,
   and with `status:"unconfirmed"` unless the caller passes `confirmed=True` asserting a human
   confirmed THIS entry. Callers still pass `config` and `confirmed=True` (the dashboard scheduler is
   the only production caller); the in-dispatch check is defense in depth, not a license for callers to
   skip their own gate. Default is off; while off, no network call.
   `<!-- verify: tools/publishing_compliance.py::live_publishing_enabled -->`
4. **YouTube = upload-only, default private.** The upload path constructs NO monetary/analytics
   endpoint (upload host only), and `status.privacyStatus` defaults to `private`; public requires an
   explicit entry choice. `<!-- verify: tools/publishing/youtube.py::publish -->`
5. **TikTok PKCE is S256 HEX, not base64url.** And its refresh token ROTATES — persist the new one
   from every token response. TikTok posts default `SELF_ONLY` and the client REFUSES a privacy level
   the (possibly unaudited) app is not allowed to use. `<!-- verify: tools/oauth_flow.py::make_pkce -->`
6. **Instagram needs a PUBLIC media URL.** Meta fetches media from a public https URL; there is no
   local-file upload. The client returns `needs_public_url` rather than faking an upload.
   `<!-- verify: tools/publishing/instagram.py::publish -->`

## Known failure modes
- **Whole-object credential clobber** (fixed): writing publish creds as `creds[plat] = plat_creds` wipes
  the importer's read token under the same platform key. Guarded by invariant 1.
- **Importer/publisher key mismatch** (fixed): a writer that sets only `account_id` breaks the importer,
  which reads only `ig_user_id`. Guarded by invariant 2.

## Fragile fallbacks that must not become defaults
- Instagram **manual paste-the-code** fallback (`wizard.py` `/api/oauth-manual`): only for when the
  loopback redirect is rejected; never the primary path.
- TikTok **SELF_ONLY** as the only pre-audit privacy level: acceptable while unaudited, not a substitute
  for passing TikTok's audit.
- Dashboard **manual-post** degrade while `live_publishing_enabled` is off: the shipped behavior, not a
  failure — it must stay no-network.

## Regression cases (mapped to the existing `--selftest`s; the tools layer has no evals/evals.json)
1. YouTube upload-scope is exact-token membership, not substring (`youtube.readonly` must NOT pass) —
   `python3 tools/publishing/youtube.py --selftest` ("missing upload scope not caught").
2. YouTube constructs no monetary/analytics URL + defaults to private — same selftest.
3. TikTok defaults SELF_ONLY, refuses unaudited public, uses FILE_UPLOAD (local bytes, not a URL) —
   `python3 tools/publishing/tiktok.py --selftest`.
4. Instagram public-URL wall + `ig_user_id` path used — `python3 tools/publishing/instagram.py --selftest`.
5. Pinterest base64 image upload (no public URL), board_id required — `python3 tools/publishing/pinterest.py --selftest`.
6. oauth_flow: PKCE hex-vs-base64url per platform + TikTok refresh rotation persisted + no-network —
   `python3 tools/oauth_flow.py --selftest`.
7. Wizard OAuth callback: single-use `state` CSRF + no-clobber merge + flag flip —
   `python3 tools/wizard.py --selftest`.

## Approval-gated changes
Editing any of: `youtube._UPLOAD_SCOPES`, the default `privacyStatus`, a platform's PKCE mode
(`oauth_flow.CONFIG[...]["pkce"]`), the live-gate default, or **adding any new endpoint host** (a new
host also trips drift invariant 46, url-provenance).

## Contributor gotchas / dev traps
- **Secret scanner** (`tools/secret_scan.py`, pattern `credential_value`) flags any literal
  `"access_token": "<12+ chars>"` — even fake test fixtures (only `REPLACE_`/`YOUR_`/`<...>`-style
  placeholders are exempt). In tests bind the key to a variable (`AT = "access_token"; {AT: "FAKE"}`)
  rather than allowlisting a real-looking value. Fix the file, don't exempt (per CLAUDE.md).
- **URL-provenance** (drift invariant 46) statically greps `http(s)://` literals; an inline f-string
  host like `f"http://{cfg.get('h','127.0.0.1')}:..."` parses as an undeclared host. Compute the host
  into a plain variable first (see `oauth_flow.redirect_uri`: `host = ...; f"http://{host}:..."`).

## Minority-report policy
When platform docs and observed behavior disagree, record the chosen interpretation, the conflict, and
the source in `docs/PUBLISHING.md` under its `[NEEDS VERIFICATION]` list; never silently pick one.

## Update checklist
After any change here: run the relevant `--selftest`(s) above, then
`python3 tools/publishing_compliance.py` sanity, then `python3 tools/sync_check.py` (must exit 0).
Live-account verification steps: `docs/PUBLISHING.md`.
