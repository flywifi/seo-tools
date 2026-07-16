# Publishing setup (YouTube, Instagram, TikTok, Pinterest)

Creator OS can publish to your own accounts through each platform's official API. This is off by
default and stays honest about what each platform actually allows a solo creator to do.

## The two switches (both must be on to make a real network post)

1. **`<platform>_publishing`** — turned on automatically when you connect that platform in the setup
   wizard (a real token is stored). It marks the platform as "direct API" instead of "manual".
2. **`live_publishing_enabled`** — the master safety switch for real network calls, **off by default**.
   While it is off, Creator OS runs every compliance check and advances items to `ready_to_post`, but
   makes **no** network call. Turn it on only when you want real posting.

On top of both flags, **every post requires an explicit human confirmation** in the Scheduling
Dashboard. Agents never post on their own — they produce a confirmation summary for you to approve.

Tokens are stored locally in `pipeline/user-context/api-credentials.local.json` (owner-only file
permissions, gitignored, never committed). The desktop OAuth `client_secret` is not treated as a true
secret — the loopback flow's PKCE and `state` are what protect the exchange.

## How connecting works

Each platform's setup screen has a **Connect** button. It opens that platform's sign-in page in your
browser, you approve the permission, and the platform redirects back to a local address the wizard is
listening on (`http://127.0.0.1:8765/oauth/<platform>/callback`). The wizard verifies a one-time
`state` value (CSRF protection), exchanges the code for a token, stores it, and turns the platform's
publishing flag on. Publishing tokens live under `creds[<platform>].publish` so they never overwrite
the read-only tokens the import feature uses.

If a platform refuses to redirect to a local address (see Instagram), the Connect page also lets you
**paste the authorization code by hand**.

**Safari note (macOS).** Safari's HTTPS-Only behavior can block or upgrade the plain-`http`
`127.0.0.1` callback, so the code may not come back automatically. If Connect stalls in Safari, use
**Chrome or Firefox** for the OAuth step, or fall back to the **paste-the-code-by-hand** box, which
works in any browser. The redirect is registered against `127.0.0.1` (not `localhost`) to avoid
IPv6/name-resolution edge cases.

---

## YouTube — the honest 7-day reality

**What works:** you can authorize your own channel and upload with **no Google verification**. The
`youtube.upload` scope is a *sensitive* scope (not a *restricted* one), so there is no security
assessment. Uploads use a resumable upload and default to **private**.

**The catch:** a local tool has no public website, and Google will not let you move the OAuth consent
screen to *Production* without a verified homepage and privacy-policy URL. So you keep the app in
**Testing** mode and add yourself as a **Test user**. Google expires Testing-mode authorizations about
**every 7 days**, so you will click **Connect** again roughly once a week. This is Google's policy, not
a Creator OS limitation, and the wizard says so up front.

**Setup:** Google Cloud Console → enable *YouTube Data API v3* → OAuth consent screen *External* +
*Testing* + add yourself as a Test user → Credentials → *OAuth client ID* → **Desktop app** → paste the
Client ID + Secret into the wizard → **Connect**. A Desktop client accepts the local redirect
automatically (no redirect registration needed).

**Quota:** ~100 uploads/day by default. **Never public by accident:** uploads default to private, and
projects that Google has not verified are forced to private regardless.

---

## Pinterest — sandbox Pins until Standard access

**What works:** connect with your app's **App ID + Secret** for a durable ~30-day token that
auto-refreshes, or paste a **24-hour test token** from your app dashboard for a quick one-off. Image
Pins upload the file **directly** (base64) — no public URL needed.

**The catch:** with **Trial** access (a new app's default), the Pins you create are **sandbox Pins
visible only to you**. Making Pins public requires **Standard** access, which Pinterest grants after
you record a short video demo of your real integration for review.

**Setup:** Pinterest Business account → developers.pinterest.com → create an app, request `pins:write`
and `boards:read` → register the redirect URL the wizard shows
(`http://127.0.0.1:8765/oauth/pinterest/callback`, exact match) → paste App ID + Secret → **Connect**.
A `board_id` is required to create a Pin. Video Pins are not supported yet (image Pins only).

---

## TikTok — private until TikTok audits your app

**What works:** connect with your **Client Key + Secret**. TikTok access tokens last 24 hours but the
refresh token lasts a year and refreshes silently, so you rarely reconnect. Video uploads send the
**local file directly** (chunked) — no public URL. AI-generated or AI-edited videos are flagged with
TikTok's `is_aigc` label automatically.

**The catch:** until TikTok **audits** your app, every post is forced to **private (SELF_ONLY)** and
only a few test users can post per day. Creator OS reads your allowed privacy levels from TikTok before
each post and **refuses** a public post your app is not cleared for, rather than quietly posting it
private. Public posting unlocks after TikTok approves your app.

**Setup:** developers.tiktok.com → create an app → add *Content Posting API* + *Login Kit*, request
`video.publish` → add the redirect URL the wizard shows
(`http://127.0.0.1:8765/oauth/tiktok/callback`; TikTok allows localhost) → paste Client Key + Secret →
**Connect**. Testing your own account works before the audit.

---

## Instagram — two walls to know about

**Wall 1 — a public media URL.** Instagram does **not** accept a file from your computer. Its servers
fetch your media from a **public https URL** at post time. So a post needs a public `image_url` or
`video_url`. When only a local file is available, Creator OS says so plainly and lets you post by hand,
rather than pretending it uploaded.

**Wall 2 — a professional account (and review to post for others).** You need a Business or Creator
account. Posting to your **own** account works in your app's Development mode; posting on behalf of
**other** people needs Meta App Review.

**Loopback caveat.** Meta does not clearly document accepting a local redirect address. If Connect
fails at the redirect step, use it anyway: on the page that opens, copy the `code` value from your
browser's address bar into the **"paste the code by hand"** box.

**Setup:** developers.facebook.com → create an app → add the *Instagram* product (API with Instagram
Login), request `instagram_business_basic` + `instagram_business_content_publish` → add the redirect
URL the wizard shows under *Valid OAuth Redirect URIs* → paste your Instagram App ID + Secret →
**Connect** (your account id is captured during sign-in). Connect exchanges the short-lived code for a
**60-day** long-lived token that Creator OS refreshes automatically.

---

## Live-account verification checklist (do this once, per platform, at real setup)

This cannot be exercised in the repo's test environment (there are no real apps or accounts), so verify
it on your own machine when you set up real publishing:

1. Register the app / OAuth client in the platform console with the exact redirect URL the wizard shows.
2. Click **Connect** and approve. Confirm you land back on a "connected" page and the platform's
   `<platform>_publishing` flag is now on. (Instagram: confirm the local redirect is accepted, or use
   the paste-the-code fallback.)
3. Confirm a token was saved under `creds[<platform>].publish` in
   `pipeline/user-context/api-credentials.local.json`, and that any import token you had is still there
   (the two must not overwrite each other).
4. Turn on `live_publishing_enabled`, then do **one** real test post to your **own** account at a safe
   visibility, confirming each post by hand in the dashboard:
   - YouTube → private or unlisted
   - TikTok → SELF_ONLY (the only option before audit)
   - Pinterest → a sandbox Pin (Trial) to a board you own
   - Instagram → a professional test account, using a real public media URL
5. Let a token approach expiry (or revoke it) and confirm reconnecting works: YouTube ~weekly in
   Testing mode; the others refresh automatically.

## Notes for future verification (`[NEEDS VERIFICATION]`)

- Instagram loopback/HTTP redirect acceptance for `127.0.0.1`/`localhost` is not clearly documented —
  the paste-the-code fallback exists precisely for this.
- Instagram Graph API version moves ~quarterly (`tools/publishing/instagram.py` pins one; bump if a
  version-deprecation error appears).
- The Facebook Page requirement under Instagram Login is in flux; a linked Page flagged for Page
  Publishing Authorization can still block publishing.
- Pinterest tier/rate numbers and the exact test-token dashboard steps come from Pinterest docs that
  render as a single-page app; reconfirm against your live dashboard.
