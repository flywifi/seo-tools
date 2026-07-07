#!/usr/bin/env python3
"""Creator OS Setup Wizard

Opens a browser at http://localhost:8765 and guides through:
  - Connecting Google Workspace (Gmail, Calendar, Drive, Docs, Sheets)
  - Connecting Microsoft 365 (Outlook, Calendar, Excel, OneDrive)
  - Updating Claude Desktop configuration automatically

Works on macOS, Windows, and Linux. No extra packages required (stdlib only).

Usage:
  python3 tools/wizard.py
"""

import http.server
import json
import os
import pathlib
import platform
import shutil
import socketserver
import subprocess
import sys
import threading
import time
import urllib.parse
import webbrowser

PORT = 8765
ROOT = pathlib.Path(__file__).resolve().parent.parent

# ── OS helpers ─────────────────────────────────────────────────────────────

def _os() -> str:
    s = platform.system()
    if s == "Darwin":
        return "mac"
    if s == "Windows":
        return "windows"
    return "linux"

def _os_label() -> str:
    return {"mac": "macOS", "windows": "Windows", "linux": "Linux"}[_os()]

def _claude_config_path() -> pathlib.Path:
    os_name = _os()
    if os_name == "mac":
        return pathlib.Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    if os_name == "windows":
        appdata = os.environ.get("APPDATA", str(pathlib.Path.home() / "AppData" / "Roaming"))
        return pathlib.Path(appdata) / "Claude" / "claude_desktop_config.json"
    return pathlib.Path.home() / ".config" / "Claude" / "claude_desktop_config.json"

def _claude_installed() -> bool:
    return _claude_config_path().parent.exists()

def _read_claude_config() -> dict:
    p = _claude_config_path()
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
    return {}

def _write_claude_config(config: dict) -> pathlib.Path:
    p = _claude_config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(config, indent=2), encoding="utf-8")
    return p

def _has_uv() -> bool:
    return shutil.which("uv") is not None

def _install_uv() -> tuple[bool, str]:
    try:
        r = subprocess.run(
            [sys.executable, "-m", "pip", "install", "uv"],
            capture_output=True, text=True, timeout=120,
        )
        if r.returncode == 0:
            return True, ""
        return False, r.stderr.strip()
    except Exception as exc:
        return False, str(exc)

def _node_version() -> str | None:
    try:
        r = subprocess.run(["node", "--version"], capture_output=True, text=True, timeout=5)
        if r.returncode == 0:
            return r.stdout.strip()
    except Exception:
        pass
    return None

def _node_ok() -> bool:
    v = _node_version()
    if not v:
        return False
    try:
        return int(v.lstrip("v").split(".")[0]) >= 20
    except (ValueError, IndexError):
        return False

def _open_url(url: str) -> None:
    """Open a URL in the system browser, cross-platform."""
    os_name = _os()
    try:
        if os_name == "mac":
            subprocess.Popen(["open", url])
        elif os_name == "windows":
            os.startfile(url)  # type: ignore[attr-defined]
        else:
            subprocess.Popen(["xdg-open", url])
    except Exception:
        webbrowser.open(url)

# ── State ──────────────────────────────────────────────────────────────────

_state: dict = {
    "google_done": False,
    "microsoft_done": False,
    "uv_installing": False,
    "uv_error": "",
}
_lock = threading.Lock()

def _get(key: str):
    with _lock:
        return _state.get(key)

def _set(**kwargs) -> None:
    with _lock:
        _state.update(kwargs)

_shutdown = threading.Event()

# ── CSS / HTML helpers ─────────────────────────────────────────────────────

_CSS = """
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',system-ui,sans-serif;
     background:#faf7f4;color:#2d1f1f;min-height:100vh;
     display:flex;flex-direction:column;align-items:center;padding:24px 16px 48px}
.brand{font-size:.8rem;color:#a08080;letter-spacing:.08em;text-transform:uppercase;
       margin-bottom:4px;margin-top:8px}
.card{background:#fff;border-radius:18px;box-shadow:0 2px 18px rgba(0,0,0,.07);
      max-width:560px;width:100%;padding:32px}
h1{font-size:1.45rem;font-weight:700;color:#7c2d2d;margin-bottom:6px}
h2{font-size:1.1rem;font-weight:600;color:#4a2020;margin-bottom:10px}
p{line-height:1.65;color:#4a3030;margin-bottom:14px}
.btn{display:block;width:100%;padding:15px 20px;border:none;border-radius:12px;
     font-size:1rem;font-weight:600;cursor:pointer;text-align:center;
     text-decoration:none;margin-bottom:10px;transition:opacity .15s}
.btn:hover{opacity:.86}
.btn-primary{background:#7c2d2d;color:#fff}
.btn-secondary{background:#f3ecec;color:#7c2d2d}
.btn-success{background:#2d6a2d;color:#fff}
.btn-outline{background:transparent;border:2px solid #7c2d2d;color:#7c2d2d;
             padding:13px 20px}
.steps{list-style:none;margin:16px 0;counter-reset:step}
.steps li{counter-increment:step;padding:11px 0 11px 42px;position:relative;
          border-bottom:1px solid #f3ecec}
.steps li:last-child{border-bottom:none}
.steps li::before{content:counter(step);position:absolute;left:0;top:11px;
                  background:#7c2d2d;color:#fff;width:28px;height:28px;
                  border-radius:50%;display:flex;align-items:center;
                  justify-content:center;font-size:.8rem;font-weight:700}
.note{background:#fef9ec;border-left:3px solid #d4a017;padding:10px 14px;
      border-radius:0 8px 8px 0;font-size:.88rem;color:#5a4810;margin:12px 0}
.success-box{background:#e8f5e8;border-left:3px solid #2d6a2d;padding:10px 14px;
             border-radius:0 8px 8px 0;font-size:.9rem;color:#1a3d1a;margin:12px 0}
.error-box{background:#fde8e8;border-left:3px solid #cc2222;padding:10px 14px;
           border-radius:0 8px 8px 0;font-size:.9rem;color:#5a1010;margin:12px 0}
.progress{display:flex;gap:8px;margin-bottom:24px;align-items:center}
.dot{width:10px;height:10px;border-radius:50%;background:#e8d8d8}
.dot.active{background:#7c2d2d;width:12px;height:12px}
.dot.done{background:#2d6a2d}
label{display:block;font-weight:600;font-size:.9rem;margin-bottom:4px;color:#4a3030}
input[type=text],input[type=password]{width:100%;padding:11px 13px;
  border:2px solid #e8d8d8;border-radius:9px;font-size:.95rem;color:#2d1f1f;
  margin-bottom:14px;outline:none;font-family:monospace}
input:focus{border-color:#7c2d2d}
hr{border:none;border-top:1px solid #f0e8e8;margin:20px 0}
small{color:#7a5a5a;font-size:.82rem;display:block;margin-top:-10px;margin-bottom:14px}
a{color:#7c2d2d}
.hint{font-size:.85rem;color:#7a5a5a;margin-top:4px}
.check{color:#2d6a2d;font-weight:700}
.tag{display:inline-block;background:#f0e8e8;color:#7c2d2d;border-radius:6px;
     padding:2px 8px;font-size:.8rem;font-weight:600;margin-right:4px}
"""

def _page(title: str, body: str, dots: list[str] | None = None) -> str:
    dot_html = ""
    if dots:
        dot_html = '<div class="progress">' + "".join(
            f'<div class="dot {c}"></div>' for c in dots
        ) + "</div>"
    return f"""<!DOCTYPE html><html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} — Creator OS Setup</title>
<style>{_CSS}</style></head>
<body>
<div class="brand">Creator OS</div>
<div class="card">{dot_html}{body}</div>
</body></html>"""

# ── Individual screens ─────────────────────────────────────────────────────

def _screen_welcome() -> str:
    os_label = _os_label()
    claude = "Claude Desktop is installed on this computer." if _claude_installed() else \
             "Claude Desktop does not appear to be installed on this computer."
    return _page("Welcome", f"""
<h1>Welcome to Creator OS Setup</h1>
<p>This wizard connects your Google and Microsoft accounts so Creator OS can read your
calendar, emails from brands, planning docs, and analytics spreadsheets.</p>
<p style="font-size:.9rem;color:#7a5a5a">Detected: <strong>{os_label}</strong>. {claude}</p>
<hr>
<h2>How do you use Creator OS?</h2>
<a class="btn btn-primary" href="/claudeai">I use it at <strong>claude.ai</strong> in my browser</a>
<a class="btn btn-secondary" href="/desktop">I use <strong>Claude Desktop</strong> on this computer</a>
<p class="hint">Not sure? If you have the Claude app installed on your computer, choose Desktop.
If you go to claude.ai in a web browser, choose the first option.</p>
<hr>
<a class="btn btn-outline" href="/cross-modality">Use Creator OS on another AI (Custom GPT, Gemini, ...)</a>
""", dots=["active", "dot", "dot", "dot"])

def _screen_claudeai() -> str:
    return _page("Google Workspace on claude.ai", """
<h1>Connect Google to claude.ai</h1>
<p>claude.ai has built-in Google Workspace support. No downloads or technical setup required
&#8212; just click Connect and sign in.</p>
<ol class="steps">
  <li>Go to <a href="https://claude.ai" target="_blank">claude.ai</a> and sign in.</li>
  <li>Click your profile picture in the top-right corner, then click <strong>Settings</strong>.</li>
  <li>In the left sidebar, click <strong>Integrations</strong> (or <strong>Connectors</strong>).</li>
  <li>Find <strong>Google Workspace</strong> and click <strong>Add</strong>.</li>
  <li>Sign in with your Google account and click <strong>Allow</strong>.</li>
</ol>
<div class="success-box">
  After connecting, Creator OS can see your Gmail, Google Calendar, and Google Drive.
  Try: "What brand emails did I get this week?" or "What&#8217;s on my content calendar?"
</div>
<div class="note">
  <strong>Microsoft 365 (Outlook, Excel):</strong> claude.ai does not yet have a built-in
  Microsoft connector. If you need Outlook or Excel integration, you will need to use
  Claude Desktop instead.
</div>
<a class="btn btn-success" href="/done">I&#8217;ve connected Google &mdash; show me what to try</a>
<a class="btn btn-outline" href="/">Back</a>
""", dots=["done", "active", "dot", "dot"])

def _screen_desktop(error: str = "") -> str:
    uv_status = '<span class="check">&#10003;</span> uv is installed' if _has_uv() \
                else '&#9744; uv not yet installed (wizard will install it automatically)'
    node_v = _node_version()
    node_status = f'<span class="check">&#10003;</span> Node.js {node_v} is installed' if _node_ok() \
                  else '&#9744; Node.js 20+ not found (needed for Microsoft 365 only)'
    err_html = f'<div class="error-box">{error}</div>' if error else ""
    return _page("Claude Desktop Setup", f"""
<h1>Claude Desktop Setup</h1>
<p>The wizard will update your Claude Desktop settings to add Google Workspace and Microsoft 365.
You will restart Claude Desktop at the end and sign in when prompted.</p>
{err_html}
<h2>Prerequisites on this computer</h2>
<p style="margin-bottom:6px">{uv_status}</p>
<p style="margin-bottom:16px">{node_status}</p>
<hr>
<h2>What do you want to connect?</h2>
<a class="btn btn-primary" href="/google">Connect Google Workspace
  <span class="tag" style="background:#4a2020;color:#fff;margin-left:6px">Gmail</span>
  <span class="tag" style="background:#4a2020;color:#fff">Calendar</span>
  <span class="tag" style="background:#4a2020;color:#fff">Drive</span>
  <span class="tag" style="background:#4a2020;color:#fff">Sheets</span>
</a>
<a class="btn btn-secondary" href="/microsoft">Connect Microsoft 365
  <span class="tag" style="margin-left:6px">Outlook</span>
  <span class="tag">Calendar</span>
  <span class="tag">Excel</span>
  <span class="tag">OneDrive</span>
</a>
<a class="btn btn-outline" href="/">Back</a>
<div class="note">You can connect both. Start with whichever you use more.</div>
""", dots=["done", "done", "active", "dot"])

def _screen_google(error: str = "") -> str:
    err_html = f'<div class="error-box">{error}</div>' if error else ""
    already = _get("google_done")
    if already:
        return _screen_google_done()
    return _page("Connect Google Workspace", f"""
<h1>Connect Google Workspace</h1>
<p>Creator OS will be able to read your Gmail, Google Calendar, Google Drive, Docs, and Sheets.
This is a <strong>one-time setup</strong> that takes about 5 minutes.</p>
{err_html}
<h2>Step 1 of 2 &mdash; Get your Google credentials (one time only)</h2>
<ol class="steps">
  <li>Open <a href="https://console.cloud.google.com" target="_blank">Google Cloud Console</a>
      and sign in with your Google account.</li>
  <li>Click <strong>Select a project</strong> at the top, then <strong>New Project</strong>.
      Name it anything (e.g. "Creator OS"). Click <strong>Create</strong>.</li>
  <li>In the left menu go to <strong>APIs &amp; Services &rarr; Library</strong>.
      Search for and enable: <strong>Gmail API</strong>, <strong>Google Calendar API</strong>,
      <strong>Google Drive API</strong>.</li>
  <li>Go to <strong>APIs &amp; Services &rarr; OAuth consent screen</strong>.
      Choose <strong>External</strong>, fill in App name ("Creator OS"), your email, and save.</li>
  <li>Go to <strong>APIs &amp; Services &rarr; Credentials</strong>.
      Click <strong>+ Create Credentials &rarr; OAuth client ID</strong>.
      Application type: <strong>Desktop app</strong>. Click <strong>Create</strong>.</li>
  <li>Copy the <strong>Client ID</strong> and <strong>Client Secret</strong> that appear.
      Paste them below.</li>
</ol>
<div class="note">These credentials stay on your computer only. They are never sent to
Creator OS servers or committed to git.</div>
<hr>
<h2>Step 2 of 2 &mdash; Paste your credentials</h2>
<form method="POST" action="/api/write-google">
  <label for="client_id">Google Client ID</label>
  <input type="text" id="client_id" name="client_id"
         placeholder="123456789-abc...apps.googleusercontent.com" required>
  <label for="client_secret">Google Client Secret</label>
  <input type="password" id="client_secret" name="client_secret"
         placeholder="GOCSPX-..." required>
  <button class="btn btn-primary" type="submit">Save Google Connection</button>
</form>
<a class="btn btn-outline" href="/desktop">Back</a>
""", dots=["done", "done", "active", "dot"])

def _screen_google_done() -> str:
    return _page("Google Connected", """
<h1><span class="check">&#10003;</span> Google Workspace connected</h1>
<div class="success-box">
  Creator OS has been configured to use Google Workspace via Claude Desktop.
</div>
<p>When you restart Claude Desktop, it will open a browser window and ask you to sign in
with your Google account. Click <strong>Allow</strong> when prompted.</p>
<p><strong>Creator OS can now:</strong></p>
<ul style="margin:0 0 16px 20px;line-height:1.8;color:#4a3030">
  <li>Read brand emails and partnership inquiries from Gmail</li>
  <li>See your content calendar and brand meeting dates</li>
  <li>Access planning docs, briefs, and contracts in Drive</li>
  <li>Pull analytics data from Google Sheets</li>
</ul>
<a class="btn btn-primary" href="/microsoft">Also connect Microsoft 365</a>
<a class="btn btn-secondary" href="/publishing-setup">Set up social media publishing</a>
<a class="btn btn-success" href="/done">I&#8217;m done &mdash; show me what to try</a>
""", dots=["done", "done", "done", "active"])

def _screen_microsoft(error: str = "", installing: bool = False) -> str:
    already = _get("microsoft_done")
    if already:
        return _screen_microsoft_done()
    if not _node_ok():
        return _screen_node_missing()
    install_note = '<div class="note">Connecting Microsoft... this may take a few seconds.</div>' \
                   if installing else ""
    err_html = f'<div class="error-box">{error}</div>' if error else ""
    return _page("Connect Microsoft 365", f"""
<h1>Connect Microsoft 365</h1>
<p>Creator OS will be able to read your Outlook email, calendar, Excel spreadsheets,
and OneDrive documents. <strong>No credentials needed upfront</strong> &mdash; you will
sign in to your Microsoft account the first time you use it in Claude Desktop.</p>
{err_html}{install_note}
<div class="success-box">
  Node.js is installed. You are ready to connect Microsoft 365.
</div>
<p>Clicking the button below adds Microsoft 365 to your Claude Desktop configuration.
After you restart Claude Desktop, it will walk you through signing in.</p>
<form method="POST" action="/api/write-microsoft">
  <button class="btn btn-primary" type="submit">Add Microsoft 365 to Claude Desktop</button>
</form>
<a class="btn btn-outline" href="/desktop">Back</a>
""", dots=["done", "done", "active", "dot"])

def _screen_node_missing() -> str:
    os_name = _os()
    if os_name == "mac":
        node_install = """
<p>Run this in Terminal to install Node.js:</p>
<pre style="background:#f3ecec;padding:12px;border-radius:8px;font-size:.9rem;
            overflow-x:auto;margin-bottom:14px">brew install node</pre>
<p>If Homebrew is not installed, see <code>docs/SETUP_MAC.md</code>.</p>"""
    elif os_name == "windows":
        node_install = """
<p>Download and install Node.js from the official site:</p>
<a class="btn btn-primary" href="https://nodejs.org/en/download"
   target="_blank" style="margin-bottom:14px">Open nodejs.org downloads</a>
<p>Choose the <strong>LTS</strong> version (20 or higher). Run the installer and
accept the defaults.</p>"""
    else:
        node_install = """
<p>Install Node.js 20+ using your package manager:</p>
<pre style="background:#f3ecec;padding:12px;border-radius:8px;font-size:.9rem;
            overflow-x:auto;margin-bottom:14px"># Debian / Ubuntu
sudo apt install -y nodejs npm

# Fedora / RHEL
sudo dnf install -y nodejs

# Arch
sudo pacman -S nodejs npm</pre>"""
    return _page("Node.js Required", f"""
<h1>Node.js is needed for Microsoft 365</h1>
<p>The Microsoft 365 connector requires <strong>Node.js version 20 or higher</strong>.
It is free and takes about 2 minutes to install.</p>
{node_install}
<hr>
<p>Once Node.js is installed, <a href="/microsoft">come back and click here</a> to continue.</p>
<a class="btn btn-outline" href="/desktop">Back</a>
""", dots=["done", "done", "active", "dot"])

def _screen_microsoft_done() -> str:
    return _page("Microsoft 365 Connected", """
<h1><span class="check">&#10003;</span> Microsoft 365 added</h1>
<div class="success-box">
  Microsoft 365 has been added to your Claude Desktop configuration.
</div>
<p>When you restart Claude Desktop, a browser window will open and ask you to sign in
with your Microsoft account. Follow the prompts to allow access.</p>
<p><strong>Creator OS can now:</strong></p>
<ul style="margin:0 0 16px 20px;line-height:1.8;color:#4a3030">
  <li>Read brand emails and partnership inquiries from Outlook</li>
  <li>See your calendar and brand meeting dates</li>
  <li>Pull analytics data from Excel spreadsheets</li>
  <li>Access documents and files in OneDrive</li>
</ul>
<a class="btn btn-primary" href="/google">Also connect Google Workspace</a>
<a class="btn btn-secondary" href="/publishing-setup">Set up social media publishing</a>
<a class="btn btn-success" href="/done">I&#8217;m done &mdash; show me what to try</a>
""", dots=["done", "done", "done", "active"])

def _screen_publishing_setup(error: str = "") -> str:
    creds = _load_api_credentials()
    err_html = f'<div class="error-box">{error}</div>' if error else ""

    def _status(plat: str) -> str:
        if creds.get(plat):
            return '<span class="check">&#10003; Connected</span>'
        return "&#9744; Not configured"

    return _page("Publishing Setup", f"""
<h1>Social Media Publishing Setup</h1>
<p>Connect your platform accounts so Creator OS can schedule and publish posts directly.
Each platform requires its own API credentials.</p>
{err_html}
<h2>Platform Status</h2>
<p>{_status("youtube")} YouTube</p>
<p>{_status("instagram")} Instagram</p>
<p>{_status("tiktok")} TikTok</p>
<p>{_status("pinterest")} Pinterest</p>
<hr>
<h2>Set up a platform</h2>
<a class="btn btn-primary" href="/publishing-setup/youtube"
   style="background:#ff0000">YouTube Publishing</a>
<a class="btn btn-primary" href="/publishing-setup/instagram"
   style="background:#e1306c">Instagram Publishing</a>
<a class="btn btn-primary" href="/publishing-setup/tiktok"
   style="background:#010101">TikTok Publishing</a>
<a class="btn btn-primary" href="/publishing-setup/pinterest"
   style="background:#e60023">Pinterest Publishing</a>
<a class="btn btn-outline" href="/done">Back to Setup</a>
<div class="note">You can set up platforms one at a time. Platforms without credentials
will fall back to manual posting (copy-paste checklists).</div>
""", dots=["done", "done", "done", "active"])


def _screen_publishing_youtube(error: str = "") -> str:
    creds = _load_api_credentials()
    yt = creds.get("youtube") or {}
    has_token = bool(yt.get("access_token") or yt.get("refresh_token"))
    if has_token:
        return _page("YouTube Connected", """
<h1><span class="check">&#10003;</span> YouTube Publishing Ready</h1>
<div class="success-box">YouTube app credentials and a user access token are configured.
Creator OS can upload and schedule videos via the YouTube Data API v3.</div>
<p>To update your credentials, paste new values below and save again.</p>
<hr>
""" + _youtube_form() + """
<a class="btn btn-outline" href="/publishing-setup">Back</a>
""", dots=["done", "done", "done", "active"])
    if yt:
        # App credentials saved, but no user authorization token yet: not publish-ready.
        return _page("YouTube App Registered", """
<h1>YouTube App Registered</h1>
<div class="note"><strong>One step remains.</strong> Your Google OAuth app credentials are
saved, but YouTube publishing also needs user <em>authorization</em> (the sign-in that grants
the <code>youtube.upload</code> permission and returns an access token). That authorization
step is not wired up yet, so the <code>youtube_publishing</code> flag stays off and YouTube
posts fall back to manual posting for now. Instagram, TikTok, and Pinterest collect a token
directly and are publish-ready once saved.</div>
<p>To update your app credentials, paste new values below and save again.</p>
<hr>
""" + _youtube_form() + """
<a class="btn btn-outline" href="/publishing-setup">Back</a>
""", dots=["done", "done", "done", "active"])

    err_html = f'<div class="error-box">{error}</div>' if error else ""
    return _page("YouTube Publishing", f"""
<h1>Set Up YouTube Publishing</h1>
<p>Creator OS uses the <strong>YouTube Data API v3</strong> to upload and schedule videos.
You need a Google Cloud project with the YouTube Data API enabled.</p>
{err_html}
<ol class="steps">
  <li>Open <a href="https://console.cloud.google.com" target="_blank">Google Cloud Console</a>.
      Use the same project as Google Workspace, or create a new one.</li>
  <li>Go to <strong>APIs &amp; Services &rarr; Library</strong>. Search for
      <strong>YouTube Data API v3</strong> and click <strong>Enable</strong>.</li>
  <li>Go to <strong>APIs &amp; Services &rarr; Credentials</strong>.
      Click <strong>+ Create Credentials &rarr; OAuth client ID</strong>.
      Application type: <strong>Desktop app</strong>.</li>
  <li>Add the scope <code>https://www.googleapis.com/auth/youtube.upload</code>
      to your OAuth consent screen.</li>
  <li>Copy the <strong>Client ID</strong> and <strong>Client Secret</strong> below.</li>
</ol>
<div class="note">If you already set up Google Workspace, you can reuse the same
OAuth credentials. Just add the <code>youtube.upload</code> scope.</div>
<hr>
""" + _youtube_form() + """
<a class="btn btn-outline" href="/publishing-setup">Back</a>
""", dots=["done", "done", "done", "active"])


def _youtube_form() -> str:
    return """
<h2>YouTube API Credentials</h2>
<form method="POST" action="/api/write-publishing">
  <input type="hidden" name="platform" value="youtube">
  <label for="yt_client_id">Google OAuth Client ID</label>
  <input type="text" id="yt_client_id" name="client_id"
         placeholder="123456789-abc...apps.googleusercontent.com" required>
  <label for="yt_client_secret">Google OAuth Client Secret</label>
  <input type="password" id="yt_client_secret" name="client_secret"
         placeholder="GOCSPX-..." required>
  <button class="btn btn-primary" type="submit" style="background:#ff0000">
    Save YouTube Credentials</button>
</form>"""


def _screen_publishing_instagram(error: str = "") -> str:
    creds = _load_api_credentials()
    if creds.get("instagram"):
        return _page("Instagram Connected", """
<h1><span class="check">&#10003;</span> Instagram Publishing Ready</h1>
<div class="success-box">Instagram API credentials are configured. Creator OS can publish
Reels and posts via the Instagram Graph API.</div>
<hr>
""" + _instagram_form() + """
<a class="btn btn-outline" href="/publishing-setup">Back</a>
""", dots=["done", "done", "done", "active"])

    err_html = f'<div class="error-box">{error}</div>' if error else ""
    return _page("Instagram Publishing", f"""
<h1>Set Up Instagram Publishing</h1>
<p>Creator OS uses the <strong>Instagram Graph API</strong> (v25.0) to publish Reels and posts.
You need a Meta Developer App with Content Publishing API access.</p>
{err_html}
<ol class="steps">
  <li>Go to <a href="https://developers.facebook.com" target="_blank">Meta for Developers</a>
      and create an app (type: <strong>Business</strong>).</li>
  <li>Under <strong>Add Products</strong>, add <strong>Instagram Graph API</strong>.</li>
  <li>In <strong>App Review</strong>, request the <code>instagram_content_publish</code>
      and <code>instagram_business_basic</code> permissions.</li>
  <li>Link your Instagram Business or Creator account to a Facebook Page
      in the app dashboard.</li>
  <li>Generate a long-lived <strong>User Access Token</strong> with content publishing scope.</li>
  <li>Find your <strong>Instagram Business Account ID</strong> from the API Explorer:
      <code>GET /me/accounts</code> &rarr; get page ID &rarr;
      <code>GET /{{page-id}}?fields=instagram_business_account</code></li>
</ol>
<div class="note">Instagram requires a Business or Creator account linked to a Facebook Page.
Personal accounts cannot use the publishing API.</div>
<hr>
""" + _instagram_form() + """
<a class="btn btn-outline" href="/publishing-setup">Back</a>
""", dots=["done", "done", "done", "active"])


def _instagram_form() -> str:
    return """
<h2>Instagram API Credentials</h2>
<form method="POST" action="/api/write-publishing">
  <input type="hidden" name="platform" value="instagram">
  <label for="ig_access_token">Instagram Access Token</label>
  <input type="text" id="ig_access_token" name="access_token"
         placeholder="EAAx..." required>
  <label for="ig_account_id">Instagram Business Account ID</label>
  <input type="text" id="ig_account_id" name="account_id"
         placeholder="17841400..." required>
  <button class="btn btn-primary" type="submit" style="background:#e1306c">
    Save Instagram Credentials</button>
</form>"""


def _screen_publishing_tiktok(error: str = "") -> str:
    creds = _load_api_credentials()
    if creds.get("tiktok"):
        return _page("TikTok Connected", """
<h1><span class="check">&#10003;</span> TikTok Publishing Ready</h1>
<div class="success-box">TikTok API credentials are configured. Creator OS can publish
videos via the TikTok Content Posting API.</div>
<div class="note">TikTok does not support scheduled publishing natively. The Scheduling
Dashboard handles this with a background scheduler. Keep the dashboard running for
scheduled posts to dispatch automatically.</div>
<hr>
""" + _tiktok_form() + """
<a class="btn btn-outline" href="/publishing-setup">Back</a>
""", dots=["done", "done", "done", "active"])

    err_html = f'<div class="error-box">{error}</div>' if error else ""
    return _page("TikTok Publishing", f"""
<h1>Set Up TikTok Publishing</h1>
<p>Creator OS uses the <strong>TikTok Content Posting API</strong> to upload videos.
You need a TikTok Developer account with the <code>video.publish</code> scope.</p>
{err_html}
<ol class="steps">
  <li>Go to <a href="https://developers.tiktok.com" target="_blank">TikTok for Developers</a>
      and sign in with your TikTok account.</li>
  <li>Create a new app. Under <strong>Products</strong>, add
      <strong>Content Posting API</strong> and <strong>Login Kit</strong>.</li>
  <li>Set a redirect URI on the app (TikTok requires one). You can use any URL you
      control, for example <code>https://example.com/callback</code> &mdash; you will
      generate and paste the access token manually below, so the wizard does not capture
      this callback.</li>
  <li>Submit for review. Once approved, copy your <strong>Client Key</strong> and
      <strong>Client Secret</strong>.</li>
  <li>Generate a <strong>User Access Token</strong> using the Login Kit OAuth flow
      with the <code>video.publish</code> scope.</li>
</ol>
<div class="note">TikTok requires app review before you can publish via API. This can
take 1 to 3 business days. In the meantime, use Manual mode (copy-paste checklists).</div>
<hr>
""" + _tiktok_form() + """
<a class="btn btn-outline" href="/publishing-setup">Back</a>
""", dots=["done", "done", "done", "active"])


def _tiktok_form() -> str:
    return """
<h2>TikTok API Credentials</h2>
<form method="POST" action="/api/write-publishing">
  <input type="hidden" name="platform" value="tiktok">
  <label for="tt_client_key">TikTok Client Key</label>
  <input type="text" id="tt_client_key" name="client_key"
         placeholder="aw..." required>
  <label for="tt_client_secret">TikTok Client Secret</label>
  <input type="password" id="tt_client_secret" name="client_secret"
         placeholder="..." required>
  <label for="tt_access_token">TikTok Access Token</label>
  <input type="text" id="tt_access_token" name="access_token"
         placeholder="act...." required>
  <button class="btn btn-primary" type="submit" style="background:#010101">
    Save TikTok Credentials</button>
</form>"""


def _screen_publishing_pinterest(error: str = "") -> str:
    creds = _load_api_credentials()
    if creds.get("pinterest"):
        return _page("Pinterest Connected", """
<h1><span class="check">&#10003;</span> Pinterest Publishing Ready</h1>
<div class="success-box">Pinterest API credentials are configured. Creator OS can create
pins and video pins via the Pinterest API v5.</div>
<hr>
""" + _pinterest_form() + """
<a class="btn btn-outline" href="/publishing-setup">Back</a>
""", dots=["done", "done", "done", "active"])

    err_html = f'<div class="error-box">{error}</div>' if error else ""
    return _page("Pinterest Publishing", f"""
<h1>Set Up Pinterest Publishing</h1>
<p>Creator OS uses the <strong>Pinterest API v5</strong> to create pins.
You need a Pinterest Business account and a developer app.</p>
{err_html}
<ol class="steps">
  <li>Convert your Pinterest account to a
      <a href="https://www.pinterest.com/business/create/" target="_blank">Business account</a>
      (free).</li>
  <li>Go to <a href="https://developers.pinterest.com" target="_blank">Pinterest Developers</a>
      and create a new app.</li>
  <li>Request the <code>pins:write</code> and <code>boards:write</code> scopes.</li>
  <li>Generate an <strong>Access Token</strong> via the OAuth flow.</li>
</ol>
<div class="note">Pinterest developer apps start in sandbox mode. You can create pins
immediately; they will be visible only to you until the app is approved for production.</div>
<hr>
""" + _pinterest_form() + """
<a class="btn btn-outline" href="/publishing-setup">Back</a>
""", dots=["done", "done", "done", "active"])


def _pinterest_form() -> str:
    return """
<h2>Pinterest API Credentials</h2>
<form method="POST" action="/api/write-publishing">
  <input type="hidden" name="platform" value="pinterest">
  <label for="pin_access_token">Pinterest Access Token</label>
  <input type="text" id="pin_access_token" name="access_token"
         placeholder="pina_..." required>
  <button class="btn btn-primary" type="submit" style="background:#e60023">
    Save Pinterest Credentials</button>
</form>"""


def _load_api_credentials() -> dict:
    """Read api-credentials.local.json and return a dict keyed by platform."""
    creds_path = ROOT / "pipeline" / "user-context" / "api-credentials.local.json"
    if creds_path.exists():
        try:
            return json.loads(creds_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
    return {}


def _save_api_credentials(creds: dict) -> None:
    """Write api-credentials.local.json."""
    creds_path = ROOT / "pipeline" / "user-context" / "api-credentials.local.json"
    creds_path.parent.mkdir(parents=True, exist_ok=True)
    creds_path.write_text(json.dumps(creds, indent=2), encoding="utf-8")


def _screen_done() -> str:
    google = _get("google_done")
    microsoft = _get("microsoft_done")
    connected = []
    if google:
        connected.append("Google Workspace (Gmail, Calendar, Drive, Sheets)")
    if microsoft:
        connected.append("Microsoft 365 (Outlook, Calendar, Excel, OneDrive)")

    if connected:
        connected_html = "<ul style='margin:0 0 16px 20px;line-height:1.8;color:#1a3d1a'>" + \
                         "".join(f"<li>{c}</li>" for c in connected) + "</ul>"
        restart = """<div class="note"><strong>Restart Claude Desktop now.</strong>
It will ask you to sign in to your connected accounts the first time you use them.</div>"""
    else:
        connected_html = "<p>No services were connected in this session.</p>"
        restart = ""

    return _page("Setup Complete", f"""
<h1>You are all set!</h1>
{connected_html}
{restart}
<h2>Things to try in Creator OS</h2>
<ul class="steps">
  <li>"What brand emails or partnership offers did I get this week?"</li>
  <li>"What&#8217;s on my content calendar for the next two weeks?"</li>
  <li>"Pull my latest analytics from the tracking spreadsheet."</li>
  <li>"I got an email from West Elm about a collab &mdash; add it to the deal pipeline."</li>
  <li>"Plan a seasonal home decor project video for my YouTube channel."</li>
</ul>
<div class="success-box">
  Creator OS routes these requests through the right spokes automatically.
  You do not need to tell it which tool to use.
</div>
<hr>
<h2>Social media publishing</h2>
<p>To schedule and publish posts directly to YouTube, Instagram, TikTok, and Pinterest:</p>
<a class="btn btn-secondary" href="/publishing-setup">Set up social media publishing</a>
<p style="font-size:.85rem;color:#7a5a5a">You can close this window at any time.
To run the wizard again: <code>python3 tools/wizard.py</code></p>
""", dots=["done", "done", "done", "done"])

# ── HTTP handler ───────────────────────────────────────────────────────────

def _screen_freshness(saved: str = "") -> str:
    """Freshness / data-store setup: pick where your refreshed reference data lives. Local-only."""
    opts = "".join(
        f'<option value="{m}">{m.replace("_", " ").title()} '
        f'&rarr; {FRESHNESS_STORE_MATRIX[m]["store"]}</option>'
        for m in ["desktop", "cross_platform", "gemini", "chatgpt", "web_only", "on_device"]
    )
    saved_html = f'<div class="note" style="background:#eef7ee">{saved}</div>' if saved else ""
    return _page("Freshness &amp; Data Store", f"""
<h1>Keep your data fresh &mdash; your way</h1>
<p>Choose where your <strong>own</strong> refreshed reference data (platform specs, rates, API
versions, code editions) is stored. Creator OS keeps it current on your machine and in the store you
pick.</p>
<div class="note"><strong>Your data stays yours.</strong> The system never pushes, proposes, or nags
anything to GitHub. Downloading a newer shared baseline from the repo is always an optional choice you
make on your own &mdash; nobody sends you homework.</div>
{saved_html}
<form method="POST" action="/api/write-freshness">
  <label>How do you mainly use Creator OS?</label>
  <select name="modality">{opts}</select>
  <label style="margin-top:12px">Check for updates every (days)</label>
  <input type="number" name="cadence_days" value="30" min="1" max="365" />
  <button class="btn" type="submit" style="margin-top:16px">Save my store choice</button>
</form>
<p style="margin-top:16px"><a class="btn btn-outline" href="/">Back to start</a></p>
""")


def _skill_modality_summary() -> dict:
    """Scan skills/*/SKILL.md for the '## Cross-modality' Class line. Returns {'A':[...], 'B':[...],
    'C':[...], 'unknown':[...]} of spoke names, so the wizard can say what runs where."""
    out: dict[str, list] = {"A": [], "B": [], "C": [], "unknown": []}
    skills_dir = ROOT / "skills"
    if not skills_dir.exists():
        return out
    for d in sorted(p for p in skills_dir.iterdir() if p.is_dir() and p.name != "atoms"):
        f = d / "SKILL.md"
        if not f.exists():
            continue
        txt = f.read_text(encoding="utf-8")
        if "## Cross-modality" not in txt:
            out["unknown"].append(d.name)
            continue
        seg = txt.split("## Cross-modality", 1)[1]
        cls = "unknown"
        for line in seg.splitlines():
            s = line.strip()
            if s.startswith("Class:"):
                token = s.split(":", 1)[1].strip()[:1].upper()
                cls = token if token in ("A", "B", "C") else "unknown"
                break
        out[cls].append(d.name)
    return out


# Per-surface wiring guidance (mirrors shared/cross-modality-engine.md packaging map).
_SURFACES = {
    "claude_desktop": ("Claude Desktop (local MCP)",
        ["Add the MCP server from implementation/claude/desktop/claude_desktop_config_snippet.json.",
         "Restart Claude Desktop. Tools like jurisdiction_resolve run offline; live lookups ask for consent."],
        "native", "Every class (A, B, C) runs natively."),
    "claude_code": ("Claude Code / CLI",
        ["Run the tools directly (python3 tools/...), or use the same MCP server."],
        "native", "Every class (A, B, C) runs natively."),
    "claude_web": ("claude.ai web + mobile",
        ["Host the remote MCP: python3 tools/mcp_server.py --serve-remote (reachable from Anthropic cloud).",
         "In claude.ai, add it as a Custom Connector (remote MCP). One endpoint also serves ChatGPT + Gemini."],
        "seam", "Class A native; B and C via the hosted remote-MCP connector."),
    "custom_gpt": ("Custom GPT (OpenAI)",
        ["In the GPT builder, add an Action and paste implementation/gpt/actions/*.yaml. Auth = None.",
         "The GPT calls the public endpoints itself (server-side point-in-polygon)."],
        "action", "Class A knowledge-only; B via a GPT Action; C only if you host the tool."),
    "gemini_api": ("Gemini API (developer)",
        ["Load implementation/gemini/*function-declarations.json as functionDeclarations.",
         "When Gemini returns a call, YOUR app executes the HTTPS request and returns the result."],
        "action", "Class A knowledge-only; B and C via your backend executing the call."),
    "gemini_gems": ("Gemini 'Gems' (consumer)",
        ["Paste implementation/gemini/system-instruction.md into a Gem for the knowledge-only path.",
         "Gems cannot call custom tools: paste a lon/lat yourself, or move to the Gemini API."],
        "none", "Class A only. B and C are unavailable here (the one dead end)."),
    "human_curl": ("Human (curl / browser, no AI)",
        ["python3 tools/geo_source_fetch.py resolve \"<address>\", or curl the public /query endpoints."],
        "curl", "Class B via curl; Class C by running the tool locally."),
}


def _screen_cross_modality(surface: str = "") -> str:
    """Show, for the user's AI surface, exactly how to wire Creator OS capabilities + what runs there."""
    summ = _skill_modality_summary()
    picker = "".join(
        f'<a class="btn btn-outline" href="/cross-modality?surface={k}" '
        f'style="display:block;margin:6px 0">{v[0]}</a>'
        for k, v in _SURFACES.items())
    body = f"""
<h1>Use Creator OS on any AI (or none)</h1>
<p>Every skill declares where it can run outside Claude (see <code>shared/cross-modality-engine.md</code>).
Pick your surface for the exact setup steps and what is available there.</p>
<div class="note"><strong>Capability classes:</strong> A = pure reasoning (runs everywhere);
B = offloadable (a public/hosted endpoint does the work); C = needs a local runtime or a hosted seam.
Your skills today: <strong>{len(summ['A'])}</strong> Class A, <strong>{len(summ['B'])}</strong> Class B,
<strong>{len(summ['C'])}</strong> Class C.</div>
{picker}
<p style="margin-top:16px"><a class="btn btn-outline" href="/">Back to start</a></p>
"""
    if surface in _SURFACES:
        label, steps, kind, avail = _SURFACES[surface]
        steps_html = "".join(f"<li>{s}</li>" for s in steps)
        # which of the user's skills work here
        if kind in ("native", "seam", "action", "curl"):
            reach = "All classes reachable." if kind in ("native", "seam") else \
                    ("Class A + B reachable; Class C needs a hosted tool." if kind == "action" else
                     "Class B + C reachable; Class A is reasoning-only.")
        else:  # none = gems
            reach = (f"Only Class A ({len(summ['A'])} skills) works. Class B + C "
                     f"({len(summ['B']) + len(summ['C'])} skills) need the API or a coordinate you paste.")
        body = f"""
<h1>{label}</h1>
<div class="note">{avail}</div>
<h2>Setup steps</h2>
<ol>{steps_html}</ol>
<div class="note"><strong>What runs here:</strong> {reach}</div>
<p style="font-size:.85rem;color:#7a5a5a">Class A: {', '.join(summ['A']) or 'none'}<br>
Class B: {', '.join(summ['B']) or 'none'}<br>Class C: {', '.join(summ['C']) or 'none'}</p>
<p style="margin-top:16px"><a class="btn btn-outline" href="/cross-modality">Pick another surface</a>
<a class="btn btn-outline" href="/">Back to start</a></p>
"""
    return _page("Cross-Modality Setup", body)


class _Handler(http.server.BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        pass  # suppress default request log noise

    def _send(self, body: str, status: int = 200,
              content_type: str = "text/html") -> None:
        enc = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(enc)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(enc)

    def _redirect(self, location: str) -> None:
        self.send_response(302)
        self.send_header("Location", location)
        self.end_headers()

    def _read_form(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length).decode("utf-8")
        parsed = urllib.parse.parse_qs(raw)
        return {k: v[0] for k, v in parsed.items()}

    def do_GET(self) -> None:
        path = urllib.parse.urlparse(self.path).path

        if path == "/oauth/youtube/callback":
            # Reserved OAuth callback (dark stub). When live publishing is built, exchange
            # the ?code= query param for a refresh token at https://oauth2.googleapis.com/token
            # using the saved client_id/client_secret and the youtube.upload scope, then store
            # the token in pipeline/user-context/api-credentials.local.json under "youtube" and
            # set youtube_publishing: true. Today it just explains that the flow is not enabled.
            self._send(_page("YouTube Authorization (not enabled yet)", """
<h1>YouTube Authorization Not Enabled Yet</h1>
<div class="note">This is the reserved callback for the YouTube OAuth sign-in. The
authorization-code exchange that stores your upload token is not implemented yet, so YouTube
publishing runs in manual mode for now. No action is needed here.</div>
<a class="btn btn-outline" href="/publishing-setup">Back to publishing setup</a>
"""))
            return

        if path == "/cross-modality":
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            self._send(_screen_cross_modality(q.get("surface", [""])[0]))
            return

        routes: dict[str, str | None] = {
            "/": _screen_welcome(),
            "/cross-modality": _screen_cross_modality(),
            "/claudeai": _screen_claudeai(),
            "/desktop": _screen_desktop(),
            "/google": _screen_google(),
            "/microsoft": _screen_microsoft(),
            "/done": _screen_done(),
            "/publishing-setup": _screen_publishing_setup(),
            "/publishing-setup/youtube": _screen_publishing_youtube(),
            "/publishing-setup/instagram": _screen_publishing_instagram(),
            "/publishing-setup/tiktok": _screen_publishing_tiktok(),
            "/publishing-setup/pinterest": _screen_publishing_pinterest(),
            "/freshness-setup": _screen_freshness(),
        }
        if path in routes:
            self._send(routes[path])
        elif path == "/quit":
            self._send(_page("Closing", "<p>Wizard closed. You can close this tab.</p>"))
            _shutdown.set()
        else:
            self._send("<h1>Not found</h1>", 404)

    def do_POST(self) -> None:
        path = urllib.parse.urlparse(self.path).path

        if path == "/api/write-freshness":
            data = self._read_form()
            rec = freshness_store_recommendation(data.get("modality", "cross_platform"))
            store = rec["recommended_store"]
            _write_freshness_config(store, data.get("cadence_days", "30"), rec["modality"])
            self._send(_screen_freshness(saved=(
                f"Saved. Recommended store for <strong>{rec['modality'].replace('_',' ')}</strong>: "
                f"<strong>{store}</strong>. {rec['why']} <br><em>{rec['note']}</em><br>"
                f"{rec['guarantee']}"
            )))
            return

        if path == "/api/write-google":
            data = self._read_form()
            client_id = data.get("client_id", "").strip()
            client_secret = data.get("client_secret", "").strip()

            if not client_id or not client_secret:
                self._send(_screen_google(error="Both Client ID and Client Secret are required."))
                return

            # Ensure uv is available
            if not _has_uv():
                ok, err = _install_uv()
                if not ok:
                    self._send(_screen_google(
                        error=f"Could not install uv automatically: {err}. "
                              "Run: pip install uv  then come back and try again."
                    ))
                    return

            # Write google-workspace MCP entry
            try:
                config = _read_claude_config()
                config.setdefault("mcpServers", {})
                config["mcpServers"]["google-workspace"] = {
                    "command": "uvx",
                    "args": ["workspace-mcp"],
                    "env": {
                        "GOOGLE_OAUTH_CLIENT_ID": client_id,
                        "GOOGLE_OAUTH_CLIENT_SECRET": client_secret,
                    },
                }
                written = _write_claude_config(config)

                # Update local capability flag
                _update_capability_flag("google_workspace", True)

                _set(google_done=True)
                print(f"[wizard] Google Workspace written to {written}")
                self._redirect("/google")
            except Exception as exc:
                self._send(_screen_google(error=f"Could not update Claude Desktop config: {exc}"))

        elif path == "/api/write-microsoft":
            if not _node_ok():
                self._redirect("/microsoft")
                return
            try:
                config = _read_claude_config()
                config.setdefault("mcpServers", {})
                config["mcpServers"]["microsoft-365"] = {
                    "command": "npx",
                    "args": ["-y", "@softeria/ms-365-mcp-server"],
                }
                written = _write_claude_config(config)

                # Update local capability flag
                _update_capability_flag("microsoft_365", True)

                _set(microsoft_done=True)
                print(f"[wizard] Microsoft 365 written to {written}")
                self._redirect("/microsoft")
            except Exception as exc:
                self._send(_screen_microsoft(error=f"Could not update Claude Desktop config: {exc}"))

        elif path == "/api/write-publishing":
            data = self._read_form()
            plat = data.get("platform", "")
            if plat not in ("youtube", "instagram", "tiktok", "pinterest"):
                self._redirect("/publishing-setup")
                return

            creds = _load_api_credentials()
            plat_creds: dict = {}

            if plat == "youtube":
                cid = data.get("client_id", "").strip()
                csec = data.get("client_secret", "").strip()
                if not cid or not csec:
                    self._send(_screen_publishing_youtube(
                        error="Both Client ID and Client Secret are required."))
                    return
                plat_creds = {"client_id": cid, "client_secret": csec}

            elif plat == "instagram":
                token = data.get("access_token", "").strip()
                acct = data.get("account_id", "").strip()
                if not token or not acct:
                    self._send(_screen_publishing_instagram(
                        error="Both Access Token and Account ID are required."))
                    return
                plat_creds = {"access_token": token, "account_id": acct}

            elif plat == "tiktok":
                ckey = data.get("client_key", "").strip()
                csec = data.get("client_secret", "").strip()
                token = data.get("access_token", "").strip()
                if not ckey or not csec or not token:
                    self._send(_screen_publishing_tiktok(
                        error="Client Key, Client Secret, and Access Token are all required."))
                    return
                plat_creds = {
                    "client_key": ckey,
                    "client_secret": csec,
                    "access_token": token,
                }

            elif plat == "pinterest":
                token = data.get("access_token", "").strip()
                if not token:
                    self._send(_screen_publishing_pinterest(
                        error="Access Token is required."))
                    return
                plat_creds = {"access_token": token}

            try:
                creds[plat] = plat_creds
                _save_api_credentials(creds)
                # Only flip the publishing flag when a usable publishing credential exists.
                # YouTube collects an OAuth app (client_id/secret) but no user token yet, so
                # its flag stays off until the OAuth authorization step is completed.
                has_token = bool(plat_creds.get("access_token") or plat_creds.get("refresh_token"))
                if plat == "youtube" and not has_token:
                    print("[wizard] youtube app credentials saved "
                          "(user authorization still required; youtube_publishing flag not set)")
                else:
                    _update_capability_flag(f"{plat}_publishing", True)
                    print(f"[wizard] {plat} publishing credentials saved")
                self._redirect(f"/publishing-setup/{plat}")
            except Exception as exc:
                screen_fn = {
                    "youtube": _screen_publishing_youtube,
                    "instagram": _screen_publishing_instagram,
                    "tiktok": _screen_publishing_tiktok,
                    "pinterest": _screen_publishing_pinterest,
                }[plat]
                self._send(screen_fn(error=f"Could not save credentials: {exc}"))

        else:
            self._send("{}", 404, "application/json")


# ── Helpers ────────────────────────────────────────────────────────────────

def _update_capability_flag(key: str, value) -> None:
    """Set a capability flag in creator-os-config.local.json (local only; never GitHub)."""
    local_path = ROOT / "creator-os-config.local.json"
    try:
        cfg = json.loads(local_path.read_text(encoding="utf-8")) if local_path.exists() else {}
        cfg.setdefault("capabilities", {})[key] = value
        local_path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    except Exception as exc:
        print(f"[wizard] Warning: could not update capability flag {key}: {exc}")


# ── P36 freshness / store orchestration ──────────────────────────────────────
# The store each modality can actually write to (from the P36 per-platform research). The freshness
# runtime writes ONLY to the user's own store; it never pushes, proposes, or nags anything to GitHub.
FRESHNESS_STORE_MATRIX = {
    "desktop": {
        "store": "local_fs",
        "why": "Claude Desktop's filesystem MCP is the only true write-in-place store; best fidelity, no hosting, no OAuth.",
        "note": "Keep the overlay file OUT of a continuously-synced folder (iCloud/Dropbox) to avoid last-writer-wins races.",
    },
    "cross_platform": {
        "store": "google_drive",
        "why": "Google Drive/Docs/Sheets is the neutral store every surface shares; Google hosts it, you host nothing.",
        "note": "Uses append-new-dated-file + union-merge (Claude cannot update a Sheet in place); Gemini writes natively, ChatGPT writes on Enterprise/Dev-mode.",
    },
    "gemini": {
        "store": "google_drive",
        "why": "Gemini writes refreshed data natively into Docs/Sheets/Drive and auto-saves.",
        "note": "Advanced Docs/Sheets writes are tier-gated (AI Pro/Ultra); verify your plan.",
    },
    "chatgpt": {
        "store": "google_drive",
        "why": "ChatGPT has no native writable dataset store; route writes to a connected Google Drive (Enterprise write actions or a Drive-write MCP in Developer Mode).",
        "note": "Otherwise fall back to export-and-you-save: ChatGPT exports a dated file you file into Drive.",
    },
    "web_only": {
        "store": "google_drive",
        "why": "claude.ai web/mobile has no writable Project store (knowledge is upload-only), so the Drive connector's create-file is the store.",
        "note": "Falls back to export-and-you-save when create-file is unavailable.",
    },
    "on_device": {
        "store": "local_fs",
        "why": "A plain JSON file in a folder you control, edited by the Desktop filesystem MCP.",
        "note": "If the folder is iCloud/Dropbox-synced, prefer single-device edits; the append-only union-merge protects against clobber but sync can still slow things down.",
    },
}


def freshness_store_recommendation(modality: str) -> dict:
    """Pure: recommend a personal freshness store for a modality, with rationale + trade-offs. The
    repo is never a write target; every option keeps the user's data in a store they control."""
    m = (modality or "").strip().lower().replace("-", "_").replace(" ", "_")
    rec = FRESHNESS_STORE_MATRIX.get(m, FRESHNESS_STORE_MATRIX["cross_platform"])
    return {
        "modality": m if m in FRESHNESS_STORE_MATRIX else "cross_platform",
        "recommended_store": rec["store"],
        "why": rec["why"],
        "note": rec["note"],
        "switchable_to": sorted({v["store"] for v in FRESHNESS_STORE_MATRIX.values()} | {"remote_mcp"}),
        "guarantee": ("Your refreshed data stays in your own store. The system never pushes, proposes, "
                      "or nags anything to GitHub. Downloading a newer repo baseline is an optional "
                      "choice you make on your own."),
    }


def _write_freshness_config(store_backend: str, cadence_days: int, modality: str = "") -> None:
    """Persist the chosen freshness store + cadence to creator-os-config.local.json (local only)."""
    valid = {"local_fs", "google_drive", "remote_mcp"}
    if store_backend not in valid:
        store_backend = "local_fs"
    try:
        cadence = int(cadence_days)
    except (TypeError, ValueError):
        cadence = 30
    _update_capability_flag("task_store_backend", store_backend)
    local_path = ROOT / "creator-os-config.local.json"
    try:
        cfg = json.loads(local_path.read_text(encoding="utf-8")) if local_path.exists() else {}
        cfg["freshness"] = {
            "store_backend": store_backend,
            "cadence_days": cadence,
            "modality": modality,
            "writes_to_github": False,
            "_note": "Personal freshness overlay location. The runtime writes only here, never GitHub.",
        }
        local_path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    except Exception as exc:
        print(f"[wizard] Warning: could not write freshness config: {exc}")


# ── Main ───────────────────────────────────────────────────────────────────

class _Server(socketserver.TCPServer):
    allow_reuse_address = True


def main() -> None:
    server = _Server(("127.0.0.1", PORT), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    url = f"http://localhost:{PORT}/"
    print(f"Creator OS Setup Wizard running at {url}")
    print("Opening browser... (press Ctrl+C to quit)")

    # Small delay so the server is ready before the browser hits it
    time.sleep(0.3)
    _open_url(url)

    try:
        _shutdown.wait()
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
        print("\nWizard closed.")


if __name__ == "__main__":
    main()
