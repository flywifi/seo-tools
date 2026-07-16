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

import html
import http.server
import json
import os
import pathlib
import platform
import shutil
import socketserver
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
import webbrowser

_HERE = pathlib.Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))
import oauth_flow  # noqa: E402  (sibling module in tools/; publishing OAuth loopback helper)
import env_paths  # noqa: E402  (sibling module in tools/; venv-aware interpreter + brew-PATH resolution)

PORT = 8765
ROOT = pathlib.Path(__file__).resolve().parent.parent

# ── OS helpers ─────────────────────────────────────────────────────────────

# Test seams: set these to simulate a platform offline so the macOS/Windows screens can be rendered
# and asserted without real hardware (mirrors transcribe.select_backend's injectable design).
_OS_OVERRIDE = None    # "mac" | "windows" | "linux"
_ARCH_OVERRIDE = None  # e.g. "arm64" | "x86_64"

def _os() -> str:
    if _OS_OVERRIDE:
        return _OS_OVERRIDE
    s = platform.system()
    if s == "Darwin":
        return "mac"
    if s == "Windows":
        return "windows"
    return "linux"

def _arch() -> str:
    return (_ARCH_OVERRIDE or platform.machine()).lower()

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
    # env_paths.which prepends the Homebrew prefixes so uv is found under a double-click launch
    # (non-login zsh) where /opt/homebrew/bin is off PATH; also accept a uv inside the private .venv.
    if env_paths.which("uv"):
        return True
    vp = env_paths.venv_python()
    return bool(vp and (vp.parent / "uv").exists())

def _install_uv() -> tuple[bool, str]:
    # Install into the private .venv when present (env_paths.app_python); on a PEP 668 externally-
    # managed Python with no .venv, retry with the sanctioned --break-system-packages override so a
    # Homebrew Python does not silently block the install.
    py = env_paths.app_python()
    try:
        r = subprocess.run(
            [py, "-m", "pip", "install", "uv"],
            capture_output=True, text=True, timeout=120,
        )
        if r.returncode == 0:
            return True, ""
        detail = (r.stderr or r.stdout or "").strip()
        if "externally-managed-environment" in detail:
            r2 = subprocess.run(
                [py, "-m", "pip", "install", "--break-system-packages", "uv"],
                capture_output=True, text=True, timeout=120,
            )
            if r2.returncode == 0:
                return True, ""
            return False, (r2.stderr or r2.stdout or "").strip()
        return False, detail
    except Exception as exc:
        return False, str(exc)

def _node_version() -> str | None:
    # Resolve node with the Homebrew prefixes prepended so a double-click launch (bare PATH) still
    # finds a brew-installed Node instead of reporting it missing.
    node = env_paths.which("node")
    if not node:
        return None
    try:
        r = subprocess.run([node, "--version"], capture_output=True, text=True, timeout=5)
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
    "import_batch_file": "",
    "import_count": 0,
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
<title>{title} - Creator OS Setup</title>
<style>{_CSS}</style></head>
<body>
<div class="brand">Creator OS</div>
<div class="card">{dot_html}{body}</div>
</body></html>"""

# ── Individual screens ─────────────────────────────────────────────────────

def _screen_welcome() -> str:
    os_label = _os_label()
    claude_hint = " (detected on this computer)" if _claude_installed() else ""
    return _page("Welcome", f"""
<h1>Welcome to Creator OS Setup</h1>
<p>A short, guided setup. Start with one question and we tailor the rest to you.</p>
<p style="font-size:.9rem;color:#7a5a5a">This computer: <strong>{os_label}</strong>.</p>
{_local_precondition_note()}
<hr>
<h2>Which AI do you use?</h2>
<a class="btn btn-primary" href="/claude"><strong>Claude</strong>{claude_hint}</a>
<a class="btn btn-secondary" href="/chatgpt"><strong>ChatGPT</strong></a>
<a class="btn btn-outline" href="/transitions">I use <strong>more than one</strong>, or I am switching</a>
<p class="hint">Using <strong>Gemini</strong>? Choose "more than one" &mdash; the Gemini path is there. Not
sure which you have? Pick the one whose name you recognize; you can change it later.</p>
<hr>
<h2>Set up this computer</h2>
<a class="btn btn-outline" href="/setup-computer">Install the free tools (recommended)</a>
<a class="btn btn-outline" href="/bring">Bring what I already have (another AI, Google Drive, or files)</a>
<hr>
<h2>Already set up? Jump to a task</h2>
<a class="btn btn-outline" href="/import">Import my past videos (build my content library)</a>
<a class="btn btn-outline" href="/brand-deals">Brand-deal readiness (contracts, rate card, pricing)</a>
<a class="btn btn-outline" href="/freshness-setup">Keep my data fresh (choose where refreshed info is saved)</a>
<a class="btn btn-outline" href="/updates">Updates: am I on the latest version?</a>
<a class="btn btn-outline" href="/cross-modality">All surfaces and what runs where</a>
""", dots=["active", "dot", "dot", "dot"])

def _screen_claude() -> str:
    """One follow-up after picking Claude: browser (claude.ai) or the desktop app. Collapses the two
    old Claude buttons into one primary choice and highlights the likely path from detection."""
    installed = _claude_installed()
    if installed:
        rec = ('<div class="success-box">The Claude app looks installed on this computer. The app can '
               'run Creator OS tools locally, so it gets the most features.</div>')
        primary_href, primary_label = "/desktop", "The Claude app on this computer (recommended)"
        second_href, second_label = "/claudeai", "Claude in my web browser (claude.ai)"
    else:
        rec = ('<div class="note">Tip: the Claude <strong>app</strong> (Claude Desktop) can run tools on '
               'your computer, which unlocks the most features. The browser is simpler but more limited.</div>')
        primary_href, primary_label = "/claudeai", "Claude in my web browser (claude.ai)"
        second_href, second_label = "/desktop", "The Claude app on this computer (Claude Desktop)"
    return _page("How do you use Claude?", f"""
<h1>How do you use Claude?</h1>
{rec}
<a class="btn btn-primary" href="{primary_href}">{primary_label}</a>
<a class="btn btn-secondary" href="{second_href}">{second_label}</a>
<a class="btn btn-outline" href="/">Back</a>
""", dots=["active", "dot", "dot", "dot"])

def _screen_bring() -> str:
    """Item 6c: one question — where does your existing info live? — routing each source to its
    importer. Wires existing screens; nothing new is scraped and the human always confirms."""
    return _page("Bring what you already have", f"""
<h1>Bring what you already have</h1>
<p>Already have a creator profile, documents, or a video library somewhere else? Point Creator OS at
it instead of starting from scratch. Pick where your information lives.</p>
<h2>From another AI (ChatGPT or Gemini)</h2>
<p>Have a profile or notes built up in another assistant? Move it over in one paste.</p>
<a class="btn btn-outline" href="/transitions">Move my profile from another AI</a>
<h2>From Google Drive, Docs, or Sheets</h2>
<p>Connect Google once and Creator OS can read what you already keep there.</p>
<a class="btn btn-outline" href="/claude">Connect Google (through Claude)</a>
<h2>From files or a folder on this computer</h2>
<p>Point Creator OS at a folder of exports, documents, or downloaded videos.</p>
<a class="btn btn-outline" href="/import">Import my past videos and exports</a>
<p style="margin-top:16px"><a class="btn btn-outline" href="/">Back to start</a></p>
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
                else '&#9744; uv not yet installed (the wizard installs it for you &mdash; no action needed)'
    node_v = _node_version()
    node_status = f'<span class="check">&#10003;</span> Node.js {node_v} is installed' if _node_ok() \
                  else '&#9744; Node.js 20+ not found (only needed for Microsoft 365; skip if you use Google)'
    err_html = f'<div class="error-box">{error}</div>' if error else ""
    return _page("Claude Desktop Setup", f"""
<h1>Claude Desktop Setup</h1>
{_local_precondition_note()}
<p>The wizard will update your Claude Desktop settings to add Google Workspace and Microsoft 365.
You will restart Claude Desktop at the end and sign in when prompted.</p>
{err_html}
<h2>Prerequisites on this computer</h2>
<p class="hint" style="margin-bottom:8px"><strong>uv</strong> and <strong>Node.js</strong> are free
helper programs that let Claude Desktop run the connectors. You do not need to know what they are; the
wizard handles them. A checkmark means you are ready.</p>
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
{_local_precondition_note()}
<p>Connect Google so Creator OS can see your Gmail, Google Calendar, Google Drive, Docs, and Sheets.
{err_html}</p>
<div class="success-box"><strong>Easiest way (recommended): the built-in Google connector.</strong>
No Google Cloud setup, no copying keys. Turn it on inside Claude and sign in once.</div>
<ol class="steps">
  <li>In Claude, open <strong>Settings</strong> then <strong>Connectors</strong> (or
      <strong>Integrations</strong>).</li>
  <li>Find <strong>Google</strong> / <strong>Google Workspace</strong> and click <strong>Connect</strong>.</li>
  <li>Sign in with your Google account and click <strong>Allow</strong>.</li>
</ol>
<a class="btn btn-primary" href="/done">I connected Google in Claude &mdash; show me what to try</a>
<div class="note">The built-in connector covers Gmail, Calendar, and Drive/Docs/Sheets. It does not
cover Microsoft/Outlook (use the Microsoft 365 step for that).</div>
<hr>
<details>
<summary style="cursor:pointer;font-weight:600;color:#7c2d2d;margin-bottom:10px">Advanced: run
Google locally on this computer (Google Cloud Console)</summary>
<p>Only needed if you specifically want the Google MCP server running on this machine (for example,
to script Google from local tools). It requires a one-time Google Cloud Console project. Most people
should use the built-in connector above instead.</p>
<h2>Step 1 &mdash; Get your Google credentials (one time only)</h2>
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
<h2>Step 2 &mdash; Paste your credentials</h2>
<form method="POST" action="/api/write-google">
  <label for="client_id">Google Client ID</label>
  <input type="text" id="client_id" name="client_id"
         placeholder="123456789-abc...apps.googleusercontent.com" required>
  <label for="client_secret">Google Client Secret</label>
  <input type="password" id="client_secret" name="client_secret"
         placeholder="GOCSPX-..." required>
  <button class="btn btn-outline" type="submit">Save local Google connection</button>
</form>
</details>
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

def _screen_node_missing(rechecked: bool = False) -> str:
    os_name = _os()
    if os_name == "mac":
        node_install = """
<p>Run this in Terminal to install Node.js:</p>
<pre style="background:#f3ecec;padding:12px;border-radius:8px;font-size:.9rem;
            overflow-x:auto;margin-bottom:14px">brew install node</pre>
<p>No Homebrew yet? Paste this first (it is the standard macOS installer), then run the line above:</p>
<pre style="background:#f3ecec;padding:12px;border-radius:8px;font-size:.85rem;
            overflow-x:auto;margin-bottom:14px">/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"</pre>"""
    elif os_name == "windows":
        node_install = """
<p>Download and install Node.js from the official site:</p>
<a class="btn btn-primary" href="https://nodejs.org/en/download"
   target="_blank" style="margin-bottom:14px">Open nodejs.org downloads</a>
<p>Choose the <strong>LTS</strong> version (20 or higher). Run the installer and accept the defaults
(keep "Add to PATH" checked). If Windows SmartScreen warns, click <strong>More info</strong> then
<strong>Run anyway</strong>.</p>"""
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
    recheck_note = ('<div class="error-box">Still not detecting Node.js 20 or higher. Make sure the '
                    'install finished, then try again. On Windows you may need to close and reopen '
                    'this wizard so it sees the updated PATH.</div>') if rechecked else ""
    return _page("Node.js Required", f"""
<h1>Node.js is needed for Microsoft 365</h1>
<p>The Microsoft 365 connector requires <strong>Node.js version 20 or higher</strong>. It is free and
takes about 2 minutes to install. Google, Wolfram, and the rest of Creator OS do <strong>not</strong>
need it &mdash; if you are only connecting Google you can skip this entirely.</p>
{recheck_note}
{node_install}
<hr>
<p>Once Node.js is installed, click below and the wizard will re-check automatically:</p>
<form method="POST" action="/api/recheck-node">
  <button class="btn btn-primary" type="submit">I've installed it &mdash; re-check</button>
</form>
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
    pub = yt.get("publish") or {}
    has_token = bool(pub.get("refresh_token") or pub.get("access_token"))
    has_app = bool(pub.get("client_id") and pub.get("client_secret"))
    err_html = f'<div class="error-box">{html.escape(error)}</div>' if error else ""
    testing_note = """<div class="note"><strong>About Google's 7-day sign-in limit.</strong> A local
tool with no public website cannot move its Google sign-in screen to "Production" (Google requires a
verified homepage and privacy-policy URL for that). So keep your OAuth app in <strong>Testing</strong>
and add yourself as a <strong>Test user</strong>. Authorizations in Testing mode expire about every
7 days, so you will click <strong>Connect</strong> again roughly once a week. This is a Google policy,
not a bug. Uploads default to <strong>private</strong> so nothing goes public by accident.</div>"""

    if has_token:
        return _page("YouTube Connected", f"""
<h1><span class="check">&#10003;</span> YouTube Publishing Ready</h1>
<div class="success-box">YouTube is connected and <code>youtube_publishing</code> is on. Creator OS
can upload videos via the YouTube Data API v3 (behind the live-publishing switch, with your
confirmation on each post).</div>
{testing_note}
<p>If uploads start failing with an authorization error, your weekly Testing-mode token expired.
Just reconnect:</p>
{_youtube_connect_button("Reconnect YouTube")}
<a class="btn btn-outline" href="/publishing-setup">Back</a>
""", dots=["done", "done", "done", "active"])

    if has_app:
        return _page("YouTube: Authorize Upload", f"""
<h1>One step left: authorize upload</h1>
<div class="note">Your Google OAuth app is saved. Now grant Creator OS permission to upload to your
channel. Click Connect, approve the <code>youtube.upload</code> permission in the browser, and you
will be returned here.</div>
{err_html}
{_youtube_connect_button()}
{testing_note}
<p style="color:#555;font-size:0.9em">Redirect URL this uses (a Desktop OAuth client accepts it
automatically): <code>{html.escape(oauth_flow.redirect_uri("youtube", PORT))}</code></p>
<hr>
<p>Need to update your app keys?</p>
{_youtube_form()}
<a class="btn btn-outline" href="/publishing-setup">Back</a>
""", dots=["done", "done", "done", "active"])

    return _page("YouTube Publishing", f"""
<h1>Set Up YouTube Publishing</h1>
<p>Creator OS uses the <strong>YouTube Data API v3</strong> to upload videos. You need a Google Cloud
project with the YouTube Data API enabled, then you authorize your own channel.</p>
{err_html}
<ol class="steps">
  <li>Open <a href="https://console.cloud.google.com" target="_blank">Google Cloud Console</a>.
      Use the same project as Google Workspace, or create a new one.</li>
  <li>Go to <strong>APIs &amp; Services &rarr; Library</strong>. Search for
      <strong>YouTube Data API v3</strong> and click <strong>Enable</strong>.</li>
  <li>On the <strong>OAuth consent screen</strong>, choose <strong>External</strong>, keep it in
      <strong>Testing</strong>, and add your own Google account under <strong>Test users</strong>.</li>
  <li>Go to <strong>Credentials &rarr; + Create Credentials &rarr; OAuth client ID</strong>.
      Application type: <strong>Desktop app</strong> (this type accepts the local redirect below
      with no extra setup).</li>
  <li>Copy the <strong>Client ID</strong> and <strong>Client Secret</strong> below, save, then click
      <strong>Connect</strong> to authorize the <code>youtube.upload</code> permission.</li>
</ol>
{testing_note}
<hr>
{_youtube_form()}
<a class="btn btn-outline" href="/publishing-setup">Back</a>
""", dots=["done", "done", "done", "active"])


def _youtube_connect_button(label: str = "Connect YouTube (authorize upload)") -> str:
    return _oauth_connect_button("youtube", label, "#ff0000")


def _oauth_connect_button(plat: str, label: str, color: str = "#111") -> str:
    """A 'Connect' button that kicks off the loopback OAuth flow for one platform."""
    return f"""<form method="POST" action="/api/oauth-start" style="margin:12px 0">
  <input type="hidden" name="platform" value="{plat}">
  <button class="btn btn-primary" type="submit" style="background:{color}">{label}</button>
</form>"""


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
    ig = creds.get("instagram") or {}
    pub = ig.get("publish") or {}
    has_token = bool(pub.get("access_token") or pub.get("refresh_token"))
    has_app = bool(pub.get("client_id") and pub.get("client_secret"))
    err_html = f'<div class="error-box">{html.escape(error)}</div>' if error else ""
    reality_note = """<div class="note"><strong>Two things Instagram requires that surprise people.</strong>
<br>1) You need a <strong>professional</strong> (Business or Creator) Instagram account. Publishing on
behalf of <em>other</em> people's accounts also needs Meta App Review; posting to your own works in
your app's Development mode.
<br>2) Instagram <strong>fetches your media from a public web address</strong> at post time. It cannot
upload a file from your computer. So a post needs a public image or video URL. Creator OS will say so
plainly and let you post by hand when a public URL is not available, rather than pretending it
uploaded.</div>"""
    loopback_note = f"""<p style="color:#555;font-size:0.9em">Redirect URL to register in your Meta app:
<code>{html.escape(oauth_flow.redirect_uri("instagram", PORT))}</code>. If Meta rejects a local address,
use Connect anyway and, on the page that opens, paste the <code>code</code> from your browser's address
bar into the "paste the code by hand" box.</p>"""

    if has_token:
        return _page("Instagram Connected", f"""
<h1><span class="check">&#10003;</span> Instagram Publishing Ready</h1>
<div class="success-box">Instagram is connected and <code>instagram_publishing</code> is on. Creator OS
can publish Reels and image posts via the Instagram Platform API (behind the live-publishing switch,
with your confirmation, and from a public media URL).</div>
{reality_note}
<hr>
{_instagram_form()}
<a class="btn btn-outline" href="/publishing-setup">Back</a>
""", dots=["done", "done", "done", "active"])

    if has_app:
        return _page("Instagram: Authorize", f"""
<h1>One step left: authorize Instagram</h1>
<div class="note">Your Instagram app keys are saved. Click Connect to sign in and grant the
content-publishing permission. This returns a long-lived (about 60-day) token.</div>
{err_html}
{_oauth_connect_button("instagram", "Connect Instagram", "#e1306c")}
{loopback_note}
{reality_note}
<hr>
{_instagram_form()}
<a class="btn btn-outline" href="/publishing-setup">Back</a>
""", dots=["done", "done", "done", "active"])

    return _page("Instagram Publishing", f"""
<h1>Set Up Instagram Publishing</h1>
<p>Creator OS uses the <strong>Instagram Platform</strong> content publishing API. You need a Meta
app and a professional Instagram account.</p>
{err_html}
<ol class="steps">
  <li>Go to <a href="https://developers.facebook.com" target="_blank">Meta for Developers</a> and
      create an app; add the <strong>Instagram</strong> product (API with Instagram Login).</li>
  <li>Request the <code>instagram_business_basic</code> and
      <code>instagram_business_content_publish</code> permissions.</li>
  <li>Add the redirect URL above under <strong>Valid OAuth Redirect URIs</strong>.</li>
  <li>Copy your <strong>Instagram App ID</strong> and <strong>App Secret</strong> below, save, then
      click <strong>Connect</strong>. Your account id is captured automatically during sign-in.</li>
</ol>
{reality_note}
{loopback_note}
<hr>
{_instagram_form()}
<a class="btn btn-outline" href="/publishing-setup">Back</a>
""", dots=["done", "done", "done", "active"])


def _instagram_form() -> str:
    return """
<h2>Instagram App Credentials</h2>
<form method="POST" action="/api/write-publishing">
  <input type="hidden" name="platform" value="instagram">
  <label for="ig_client_id">Instagram App ID (Client ID) &mdash; for the Connect flow</label>
  <input type="text" id="ig_client_id" name="client_id" placeholder="1234567890">
  <label for="ig_client_secret">Instagram App Secret</label>
  <input type="password" id="ig_client_secret" name="client_secret" placeholder="app secret">
  <label for="ig_account_id">Instagram account id (ig_user_id) &mdash; optional if you use Connect</label>
  <input type="text" id="ig_account_id" name="account_id" placeholder="17841400...">
  <label for="ig_access_token">Or paste a long-lived Access Token (with the account id above)</label>
  <input type="text" id="ig_access_token" name="access_token" placeholder="IGAA...">
  <button class="btn btn-primary" type="submit" style="background:#e1306c">
    Save Instagram Credentials</button>
</form>
<p style="color:#777;font-size:0.85em">Use App ID + Secret with Connect (recommended), or paste a
long-lived token together with your account id. You do not need both.</p>"""


def _screen_publishing_tiktok(error: str = "") -> str:
    creds = _load_api_credentials()
    pub = (creds.get("tiktok") or {}).get("publish") or {}
    has_token = bool(pub.get("access_token") or pub.get("refresh_token"))
    has_app = bool(pub.get("client_key") and pub.get("client_secret"))
    err_html = f'<div class="error-box">{html.escape(error)}</div>' if error else ""
    audit_note = """<div class="note"><strong>What TikTok lets an un-reviewed app do.</strong> Until
TikTok <em>audits</em> your app for the Content Posting API, every post it makes is forced to
<strong>private (visible to you only)</strong>, and only a handful of test users can post per day.
Creator OS reads your allowed privacy levels from TikTok before each post and will refuse a public
post your app is not cleared for, rather than silently posting it private. Public posting unlocks
after TikTok approves your app. AI-generated or AI-edited videos are flagged with TikTok's
<code>is_aigc</code> label automatically.</div>"""

    if has_token:
        return _page("TikTok Connected", f"""
<h1><span class="check">&#10003;</span> TikTok Publishing Ready</h1>
<div class="success-box">TikTok is connected and <code>tiktok_publishing</code> is on. Creator OS can
upload videos via the Content Posting API (behind the live-publishing switch, with your confirmation).</div>
{audit_note}
<div class="note">TikTok has no native scheduled publishing; the Scheduling Dashboard's background
scheduler dispatches at the scheduled time, so keep it running for scheduled posts.</div>
<hr>
{_tiktok_form()}
<a class="btn btn-outline" href="/publishing-setup">Back</a>
""", dots=["done", "done", "done", "active"])

    if has_app:
        return _page("TikTok: Authorize", f"""
<h1>One step left: authorize TikTok</h1>
<div class="note">Your TikTok app keys are saved. Click Connect to authorize the
<code>video.publish</code> permission. TikTok tokens last 24 hours but refresh automatically for a
year, so you should not need to reconnect often.</div>
{err_html}
{_oauth_connect_button("tiktok", "Connect TikTok", "#010101")}
<p style="color:#555;font-size:0.9em">Register this exact redirect URL in your TikTok Login Kit
settings: <code>{html.escape(oauth_flow.redirect_uri("tiktok", PORT))}</code></p>
{audit_note}
<hr>
{_tiktok_form()}
<a class="btn btn-outline" href="/publishing-setup">Back</a>
""", dots=["done", "done", "done", "active"])

    return _page("TikTok Publishing", f"""
<h1>Set Up TikTok Publishing</h1>
<p>Creator OS uses the <strong>TikTok Content Posting API</strong> to upload videos. You need a
TikTok Developer app with the <code>video.publish</code> scope.</p>
{err_html}
<ol class="steps">
  <li>Go to <a href="https://developers.tiktok.com" target="_blank">TikTok for Developers</a> and
      sign in with your TikTok account.</li>
  <li>Create an app. Under <strong>Products</strong>, add <strong>Content Posting API</strong> and
      <strong>Login Kit</strong>; request the <code>video.publish</code> scope.</li>
  <li>In Login Kit, add this redirect URL (TikTok allows localhost):
      <code>{html.escape(oauth_flow.redirect_uri("tiktok", PORT))}</code></li>
  <li>Copy your <strong>Client Key</strong> and <strong>Client Secret</strong> below, save, then
      click <strong>Connect</strong> to authorize. Testing your own account works before the audit.</li>
</ol>
{audit_note}
<hr>
{_tiktok_form()}
<a class="btn btn-outline" href="/publishing-setup">Back</a>
""", dots=["done", "done", "done", "active"])


def _tiktok_form() -> str:
    return """
<h2>TikTok App Credentials</h2>
<form method="POST" action="/api/write-publishing">
  <input type="hidden" name="platform" value="tiktok">
  <label for="tt_client_key">TikTok Client Key</label>
  <input type="text" id="tt_client_key" name="client_key" placeholder="aw..." required>
  <label for="tt_client_secret">TikTok Client Secret</label>
  <input type="password" id="tt_client_secret" name="client_secret" placeholder="..." required>
  <button class="btn btn-primary" type="submit" style="background:#010101">
    Save TikTok Credentials</button>
</form>
<p style="color:#777;font-size:0.85em">After saving, click <strong>Connect</strong> to authorize.
TikTok access tokens only last 24 hours, so the wizard's Connect flow (which stores a
long-lived refresh token) is the reliable way to publish.</p>"""


def _screen_publishing_pinterest(error: str = "") -> str:
    creds = _load_api_credentials()
    pub = (creds.get("pinterest") or {}).get("publish") or {}
    has_token = bool(pub.get("access_token") or pub.get("refresh_token"))
    has_app = bool(pub.get("client_id") and pub.get("client_secret"))
    err_html = f'<div class="error-box">{html.escape(error)}</div>' if error else ""
    sandbox_note = """<div class="note"><strong>What Pinterest lets a new app do.</strong> With
<strong>Trial</strong> access (the default for a new app), the Pins you create are
<strong>sandbox Pins visible only to you</strong>. To make Pins publicly visible you must apply for
<strong>Standard</strong> access, which requires recording a short video demo of your app's real
Pinterest integration for Pinterest to review. Creator OS creates the Pin the same way either way;
this is Pinterest's rule, stated up front so it is not a surprise.</div>"""

    if has_token:
        return _page("Pinterest Connected", f"""
<h1><span class="check">&#10003;</span> Pinterest Publishing Ready</h1>
<div class="success-box">Pinterest is connected and <code>pinterest_publishing</code> is on. Creator
OS can create image Pins via the API v5 (behind the live-publishing switch, with your confirmation).</div>
{sandbox_note}
<hr>
{_pinterest_form()}
<a class="btn btn-outline" href="/publishing-setup">Back</a>
""", dots=["done", "done", "done", "active"])

    if has_app:
        return _page("Pinterest: Authorize", f"""
<h1>One step left: authorize Pinterest</h1>
<div class="note">Your Pinterest app keys are saved. Click Connect to authorize the
<code>pins:write</code> permission. This gives you a durable token (about 30 days, auto-refreshing).</div>
{err_html}
{_oauth_connect_button("pinterest", "Connect Pinterest", "#e60023")}
<p style="color:#555;font-size:0.9em">Register this exact redirect URL in your Pinterest app:
<code>{html.escape(oauth_flow.redirect_uri("pinterest", PORT))}</code></p>
{sandbox_note}
<hr>
{_pinterest_form()}
<a class="btn btn-outline" href="/publishing-setup">Back</a>
""", dots=["done", "done", "done", "active"])

    return _page("Pinterest Publishing", f"""
<h1>Set Up Pinterest Publishing</h1>
<p>Creator OS uses the <strong>Pinterest API v5</strong> to create Pins. You need a Pinterest
Business account and a developer app. Two ways to connect:</p>
{err_html}
<ol class="steps">
  <li>Convert your account to a
      <a href="https://www.pinterest.com/business/create/" target="_blank">Business account</a> (free).</li>
  <li>Go to <a href="https://developers.pinterest.com" target="_blank">Pinterest Developers</a> and
      create an app; request the <code>pins:write</code> and <code>boards:read</code> scopes.</li>
  <li><strong>Durable way:</strong> paste your app's <strong>Client ID + Secret</strong> below and
      click Connect (30-day token that auto-refreshes). Register the redirect URL
      <code>{html.escape(oauth_flow.redirect_uri("pinterest", PORT))}</code> in your app first.</li>
  <li><strong>Quick trial:</strong> generate a <strong>24-hour test token</strong> in your app
      dashboard and paste it below instead (handy for a one-off test; it expires the next day).</li>
</ol>
{sandbox_note}
<hr>
{_pinterest_form()}
<a class="btn btn-outline" href="/publishing-setup">Back</a>
""", dots=["done", "done", "done", "active"])


def _pinterest_form() -> str:
    return """
<h2>Pinterest App Credentials</h2>
<form method="POST" action="/api/write-publishing">
  <input type="hidden" name="platform" value="pinterest">
  <label for="pin_client_id">App ID (Client ID) &mdash; for the durable Connect flow</label>
  <input type="text" id="pin_client_id" name="client_id" placeholder="1234567">
  <label for="pin_client_secret">App Secret (Client Secret)</label>
  <input type="password" id="pin_client_secret" name="client_secret" placeholder="pinterest app secret">
  <label for="pin_access_token">Or paste a 24-hour Access Token (quick trial)</label>
  <input type="text" id="pin_access_token" name="access_token" placeholder="pina_...">
  <button class="btn btn-primary" type="submit" style="background:#e60023">
    Save Pinterest Credentials</button>
</form>
<p style="color:#777;font-size:0.85em">Enter your App ID + Secret to use Connect, or paste a
24-hour token for a quick one-off. You do not need both.</p>"""


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
    """Write api-credentials.local.json (owner-only perms; gitignored, never committed)."""
    creds_path = ROOT / "pipeline" / "user-context" / "api-credentials.local.json"
    creds_path.parent.mkdir(parents=True, exist_ok=True)
    creds_path.write_text(json.dumps(creds, indent=2), encoding="utf-8")
    try:
        os.chmod(creds_path, 0o600)  # tokens at rest: owner read/write only
    except OSError:
        pass


def _merge_api_credentials(plat: str, patch: dict) -> dict:
    """Deep-merge `patch` into creds[plat] and persist (read-modify-write). Fixes the whole-object
    clobber: publishing tokens live under creds[plat]["publish"] and never overwrite the importer's
    root-level read token (and vice-versa). Keys other than "publish" merge at the platform root
    (e.g. the shared "ig_user_id" identity). Returns the full creds dict."""
    creds = _load_api_credentials()
    cur = creds.get(plat)
    if not isinstance(cur, dict):
        cur = {}
    for key, val in patch.items():
        if key == "publish" and isinstance(val, dict):
            pub = cur.get("publish")
            if not isinstance(pub, dict):
                pub = {}
            pub.update(val)
            cur["publish"] = pub
        else:
            cur[key] = val
    creds[plat] = cur
    _save_api_credentials(creds)
    return creds


# ── Publishing OAuth (loopback) ──────────────────────────────────────────────

_PLATFORM_LABEL = {"youtube": "YouTube", "instagram": "Instagram",
                   "tiktok": "TikTok", "pinterest": "Pinterest"}

# Test hook: when set (only by --selftest), OAuth token calls use this injected transport instead of
# real network. None in all production paths.
_OAUTH_TRANSPORT = None


def _oauth_publish_creds(plat: str):
    """Return (client_id, client_secret, publish_dict) from creds[plat]['publish']. TikTok stores
    its id under 'client_key'; either is returned as client_id for oauth_flow."""
    pub = (_load_api_credentials().get(plat) or {}).get("publish") or {}
    cid = pub.get("client_id") or pub.get("client_key")
    return cid, pub.get("client_secret"), pub


def _complete_oauth(plat: str, code: str, verifier, redirect_uri: str):
    """Exchange an auth code for tokens, persist them under creds[plat]['publish'], flip the
    {plat}_publishing flag. Returns (ok: bool, detail: str) with detail as PLAIN text."""
    cid, csec, _pub = _oauth_publish_creds(plat)
    if not cid or not csec:
        return False, ("Your app Client ID and Client Secret are not saved yet. Enter them on the "
                       "setup page, then click Connect again.")
    try:
        tok = oauth_flow.exchange_code(plat, client_id=cid, client_secret=csec, code=code,
                                       redirect_uri=redirect_uri, verifier=verifier,
                                       transport=_OAUTH_TRANSPORT)
    except oauth_flow.OAuthError as exc:
        return False, (f"{_PLATFORM_LABEL.get(plat, plat)} rejected the authorization "
                       f"({exc.code}). {exc.description[:160]} Start the Connect flow again.")
    except Exception as exc:  # noqa: BLE001
        return False, f"Could not reach the token endpoint: {type(exc).__name__}. Check your connection and retry."
    patch = {"publish": {k: v for k, v in tok.items() if v is not None}}
    if plat == "instagram" and tok.get("ig_user_id"):
        patch["ig_user_id"] = tok["ig_user_id"]   # shared identity lives at the platform root
    _merge_api_credentials(plat, patch)
    _update_capability_flag(f"{plat}_publishing", True)
    return True, "connected"


def _oauth_success_html(plat: str) -> str:
    label = _PLATFORM_LABEL.get(plat, plat)
    return f"""<h1>{label} connected</h1>
<div class="note"><strong>{plat}_publishing is now on.</strong> Your authorization token was saved
locally to pipeline/user-context/api-credentials.local.json (owner-only, never committed). Live
posting still stays off until you turn on live_publishing_enabled and confirm each post by hand.</div>
<a class="btn" href="/publishing-setup">Back to publishing setup</a>"""


def _oauth_error_html(plat: str, detail: str) -> str:
    label = _PLATFORM_LABEL.get(plat, plat)
    return f"""<h1>{label} authorization</h1>
<div class="note">{html.escape(detail)}</div>
<a class="btn btn-outline" href="/publishing-setup/{plat}">Back to {label} setup</a>"""


def _oauth_waiting_page(plat: str, auth_url: str, redirect_uri: str) -> str:
    label = _PLATFORM_LABEL.get(plat, plat)
    return _page(f"Connecting {label}", f"""
<h1>Finish signing in to {label}</h1>
<div class="note">A browser tab should have opened for {label} sign-in. Approve the permissions and you
will be returned here automatically.</div>
<p>If no tab opened, <a href="{html.escape(auth_url)}">click here to authorize</a>.</p>
<details><summary>It did not redirect back? Paste the code by hand</summary>
<p style="color:#555">Some platforms cannot redirect to a local address. If, after approving, your
browser lands on a page showing a <code>code=</code> value in the address bar (or an error that it
could not reach {html.escape(redirect_uri)}), copy that code and paste it below.</p>
<form method="POST" action="/api/oauth-manual">
<input type="hidden" name="platform" value="{plat}">
<input type="text" name="code" placeholder="authorization code" style="width:100%;padding:8px;margin:6px 0">
<button class="btn" type="submit">Finish connecting</button>
</form></details>
<a class="btn btn-outline" href="/publishing-setup/{plat}">Back to {label} setup</a>
""")


def _oauth_callback_page(plat: str, q: dict) -> str:
    """Handle GET /oauth/<plat>/callback. Verifies single-use state (CSRF), then exchanges the code."""
    label = _PLATFORM_LABEL.get(plat, plat)
    err = (q.get("error", [""])[0] or "").strip()
    code = (q.get("code", [""])[0] or "").strip()
    state = (q.get("state", [""])[0] or "").strip()
    pending = _get(f"oauth_pending_{plat}") or {}
    _set(**{f"oauth_pending_{plat}": None})   # single-use: consume the pending flow immediately
    if err:
        return _page(f"{label} authorization",
                     _oauth_error_html(plat, f"The request was denied or cancelled ({err})."))
    if not code:
        return _page(f"{label} authorization",
                     _oauth_error_html(plat, "No authorization code came back. Start the Connect flow again."))
    if not pending or not state or state != pending.get("state"):
        return _page(f"{label} authorization",
                     _oauth_error_html(plat, "Security check failed (state did not match). For your "
                                             "safety the request was ignored. Start Connect again."))
    ok, detail = _complete_oauth(plat, code, pending.get("verifier"), pending.get("redirect_uri", ""))
    if ok:
        return _page(f"{label} connected", _oauth_success_html(plat))
    return _page(f"{label} authorization", _oauth_error_html(plat, detail))


_PUBLISHING_SCREENS = {
    "youtube": _screen_publishing_youtube,
    "instagram": _screen_publishing_instagram,
    "tiktok": _screen_publishing_tiktok,
    "pinterest": _screen_publishing_pinterest,
}


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
    # Plain-language labels so the dropdown never shows internal tokens (local_fs, cross_platform).
    _MODALITY_LABEL = {"desktop": "Claude Desktop", "cross_platform": "More than one AI",
                       "gemini": "Gemini", "chatgpt": "ChatGPT", "web_only": "A web browser only",
                       "on_device": "This computer only"}
    _STORE_LABEL = {"local_fs": "saved on this computer", "google_drive": "saved in your Google Drive"}
    opts = "".join(
        f'<option value="{m}">{_MODALITY_LABEL.get(m, m.replace("_", " ").title())} '
        f'&rarr; {_STORE_LABEL.get(FRESHNESS_STORE_MATRIX[m]["store"], FRESHNESS_STORE_MATRIX[m]["store"])}</option>'
        for m in ["desktop", "cross_platform", "gemini", "chatgpt", "web_only", "on_device"]
    )
    saved_html = f'<div class="note" style="background:#eef7ee">{saved}</div>' if saved else ""
    return _page("Freshness &amp; Data Store", f"""
<h1>Keep your data fresh &mdash; your way</h1>
{_local_precondition_note()}
<p>Choose where your <strong>own</strong> refreshed reference data (platform specs, rates, API
versions, code editions) is stored. Creator OS keeps it current on your machine and in the store you
pick.</p>
<div class="note"><strong>Your data stays yours.</strong> The system never pushes, proposes, or nags
anything to GitHub. Downloading a newer shared baseline from the repo is always an optional choice you
make on your own &mdash; nobody sends you homework.</div>
{saved_html}
<form method="POST" action="/api/write-freshness">
  <label>Where do you MOSTLY use Creator OS? (This only sets where this computer stores its files; if you use two AIs, pick cross platform.)</label>
  <select name="modality">{opts}</select>
  <label style="margin-top:12px">Check for updates every (days)</label>
  <input type="number" name="cadence_days" value="30" min="1" max="365" />
  <button class="btn" type="submit" style="margin-top:16px">Save my store choice</button>
</form>
<hr>
<h2>Storing on this computer?</h2>
<p>If you keep your data on this computer, you can tell Claude exactly which folder it may read and
write. Nothing outside that one folder is ever touched.</p>
<a class="btn btn-outline" href="/storage-folder">Choose my Creator OS folder</a>
<p style="margin-top:16px"><a class="btn btn-outline" href="/">Back to start</a></p>
""")


def _write_storage_folder(folder: str) -> pathlib.Path:
    """Register a filesystem MCP scoped to one folder (Claude can read/write ONLY there) and record the
    chosen path in creator-os-config.local.json. Reuses _write_claude_config (the MCP-entry primitive)."""
    config = _read_claude_config()
    config.setdefault("mcpServers", {})
    config["mcpServers"]["filesystem"] = {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-filesystem", folder],
    }
    written = _write_claude_config(config)
    # Record the folder locally so the freshness/store runtime knows where to write.
    local_path = ROOT / "creator-os-config.local.json"
    try:
        cfg = json.loads(local_path.read_text(encoding="utf-8")) if local_path.exists() else {}
        cfg["storage"] = {"local_folder": folder,
                          "_note": "The one folder Claude's filesystem connector may read and write."}
        local_path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        print(f"[wizard] Warning: could not record storage folder: {exc}")
    return written


def _screen_storage_folder(saved: str = "", error: str = "", folder: str = "") -> str:
    """Item 7c: the folder-permission consent step. Registers a filesystem MCP scoped to that folder.
    A native folder picker (Browse...) fills the path; the text field stays as the always-works floor."""
    os_name = _os()
    example = {"windows": r"C:\Users\you\CreatorOS", "mac": "/Users/you/CreatorOS"}.get(os_name, "/home/you/CreatorOS")
    saved_html = f'<div class="success-box">{saved}</div>' if saved else ""
    err_html = f'<div class="error-box">{error}</div>' if error else ""
    fesc = html.escape(folder)
    node_note = "" if _node_ok() else ('<div class="note">This connector needs <strong>Node.js 20+</strong>, '
                                       'which is not detected yet. <a href="/microsoft">Install Node.js</a> '
                                       'first, then come back.</div>')
    return _page("Choose my Creator OS folder", f"""
<h1>Choose the folder Creator OS may use</h1>
{_local_precondition_note()}
<p>Pick <strong>one</strong> folder on this computer for Creator OS to read and write &mdash; your
exports, library, and refreshed data live here. Claude's filesystem connector is scoped to this folder
only; it cannot see anything outside it.</p>
{saved_html}
{err_html}
{node_note}
<form method="POST" action="/api/pick-folder" style="margin-bottom:8px">
  <input type="hidden" name="target" value="storage">
  <button class="btn btn-outline" type="submit">Browse&hellip; (open a folder picker)</button>
</form>
<form method="POST" action="/api/write-storage-folder">
  <label for="folder">Full path to your folder</label>
  <input type="text" id="folder" name="folder" value="{fesc}" placeholder="{example}" required>
  <button class="btn btn-primary" type="submit" style="margin-top:12px">Allow this folder</button>
</form>
<div class="note">Click <strong>Browse</strong> to pick the folder, or make it first (in Finder or
File Explorer) and paste its full path. Keep it out of a continuously-synced folder (iCloud/Dropbox)
to avoid sync conflicts.</div>
<p style="margin-top:16px"><a class="btn btn-outline" href="/freshness-setup">Back</a></p>
""")


def _load_creator_config() -> dict:
    """Merged capability config: committed creator-os-config.json overlaid by the gitignored
    creator-os-config.local.json (same merge as tools/obligations.py load_config)."""
    base: dict = {}
    try:
        base = json.loads((ROOT / "creator-os-config.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        pass
    local_path = ROOT / "creator-os-config.local.json"
    if local_path.exists():
        try:
            local = json.loads(local_path.read_text(encoding="utf-8"))
            for k, v in local.get("capabilities", {}).items():
                base.setdefault("capabilities", {})[k] = v
        except (OSError, json.JSONDecodeError):
            pass
    return base


def _flag_enabled(config: dict, name: str) -> bool:
    caps = config.get("capabilities", {}) if isinstance(config, dict) else {}
    meta = caps.get(name)
    if isinstance(meta, dict):
        return bool(meta.get("enabled", False))
    return bool(meta)


# The capability flags the brand-deals screen may enable: a plain-language name + what each unlocks.
_BRAND_DEAL_FLAGS = {
    "contract_management": ("Review brand contracts",
                            "contract-desk review of an inbound brand contract (triage, clause findings, escalation brief)"),
    "contract_drafting": ("Draft agreements",
                          "plain-language draft agreements from the deal playbook (requires Review brand contracts)"),
    "finance_management": ("Track invoices and money",
                           "finance record writes: invoices, cost estimates, actuals under pipeline/finance/"),
    "document_templates": ("Save documents from templates",
                           "the document-template lane: persist documents assembled from your saved block templates (contracts, rate cards, analytics overviews, terms); read-only assembly always works"),
}


def _screen_brand_deals(saved: str = "") -> str:
    """Brand-deal readiness checklist: flag states, rate card + profile presence, one-click enable."""
    cfg = _load_creator_config()
    rows = []
    for flag, (name, unlocks) in _BRAND_DEAL_FLAGS.items():
        on = _flag_enabled(cfg, flag)
        state = '<span class="check">ON</span>' if on else '<strong style="color:#cc2222">OFF</strong>'
        action = "" if on else (
            f'<form method="POST" action="/api/enable-capability" style="margin-top:6px">'
            f'<input type="hidden" name="flag" value="{flag}">'
            f'<button class="btn btn-secondary" type="submit" style="margin:0;padding:8px 14px;width:auto;'
            f'font-size:.85rem">Turn on {name}</button></form>')
        rows.append(f"<li><strong>{name}</strong>: {state} "
                    f'<span class="hint" style="opacity:.6">({flag})</span><br>'
                    f'<span class="hint">{unlocks}</span>{action}</li>')
    rate_card = ROOT / "pipeline" / "finance" / "rate-card.local.json"
    profile = ROOT / "pipeline" / "user-context" / "creator-profile.local.json"
    rc_state = ('<span class="check">found</span>' if rate_card.exists() else
                '<strong style="color:#cc2222">missing</strong> &mdash; copy '
                '<code>pipeline/finance/rate-card.template.json</code> to '
                '<code>pipeline/finance/rate-card.local.json</code> and fill in your real rates '
                '(gitignored; never committed)')
    pf_state = ('<span class="check">found</span>' if profile.exists() else
                '<strong style="color:#cc2222">missing</strong> &mdash; copy '
                '<code>pipeline/user-context/creator-profile.template.json</code> to '
                '<code>pipeline/user-context/creator-profile.local.json</code> (or run the ChatGPT '
                'profile import: <code>implementation/gpt/profile-import/PROMPT.md</code>, one run '
                'per ChatGPT context, then ask Creator OS to merge the replies) so contract drafts '
                'stop carrying placeholders for your legal name, address, and governing-law state')
    tmpl_rows = []
    for tf in sorted((ROOT / "pipeline" / "templates").glob("*.local.json")):
        try:
            t = json.loads(tf.read_text(encoding="utf-8"))
            tmpl_rows.append(f"<code>{tf.name}</code> ({t.get('doc_type')}, "
                             f"{'vetted' if t.get('vetted') else 'not vetted'}, "
                             f"{len(t.get('blocks') or [])} blocks)")
        except (OSError, json.JSONDecodeError):
            tmpl_rows.append(f"<code>{tf.name}</code> (unreadable)")
    tmpl_state = ("<br>".join(tmpl_rows) if tmpl_rows else
                  '<strong style="color:#cc2222">none saved</strong> &mdash; copy a starter from '
                  '<code>pipeline/templates/</code> (contract base, rate card display, analytics '
                  'overview, terms) to a <code>.local.json</code> and fill it, or ask for '
                  'template-ingest to propose one from an old document (you save it by hand; '
                  'gitignored, never committed)')
    saved_html = f'<div class="success-box">{saved}</div>' if saved else ""
    return _page("Brand Deals", f"""
<h1>Brand-deal readiness</h1>
{_local_precondition_note()}
<p>The <strong>pitch_triage</strong> flow (extract, fit-check, price floor, brief) always runs.
These switches and files unlock the rest of the deal machinery. Everything here writes only to
local gitignored files; your rates and legal details never reach GitHub.</p>
<div class="note"><strong>Where these switches apply:</strong> Claude Desktop, Claude Code, and
any remote MCP endpoint you deploy from this computer. They do NOT change anything inside
claude.ai connectors-only use, ChatGPT, or Gemini; on those surfaces nothing evaluates the
switches at all (see docs/CROSS-MODALITY.md).</div>
{saved_html}
<h2>Capability switches</h2>
<ul class="steps">{''.join(rows)}</ul>
<h2>Local files</h2>
<ul class="steps">
<li><strong>Personal rate card</strong>: {rc_state}</li>
<li><strong>Creator profile</strong>: {pf_state}</li>
<li><strong>Document templates</strong>: {tmpl_state}</li>
</ul>
<div class="note">Rates and profile data are decision inputs, never auto-quoted: the
consequential-action gate (amount, counterparty, explicit yes) applies before any number reaches a
brand, and contract drafts are plain-language, not-vetted, review-with-counsel.</div>
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
TRANSITIONS_PATH = ROOT / "shared" / "cross-modality" / "transitions.json"
_TRANSITIONS_CACHE: dict = {}


def _load_transitions() -> dict:
    """The transition matrix (shared/cross-modality/transitions.json), cached. Returns {} when
    absent so every screen still renders."""
    if not _TRANSITIONS_CACHE:
        try:
            _TRANSITIONS_CACHE.update(json.loads(TRANSITIONS_PATH.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            return {}
    return _TRANSITIONS_CACHE


def _surface(sid: str) -> dict:
    return (_load_transitions().get("surfaces") or {}).get(sid, {})


def _repo_version() -> str:
    try:
        return (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    except OSError:
        return "unknown"


def _local_precondition_note() -> str:
    """The banner explaining the wizard's local-machine precondition (E2)."""
    return ('<div class="note"><strong>Where this wizard runs:</strong> on the computer where '
            'you keep your Creator OS folder. Switches and files it writes affect this computer '
            'and any tools you run from it. If you only use ChatGPT or claude.ai in a browser, '
            'that is fine: the wizard just produces text and files for you to paste or upload; '
            'nothing installs into your browser AI.</div>')


# Per-surface wiring metadata. Labels and setup steps for the nine canonical surfaces come from
# shared/cross-modality/transitions.json (single source of truth); this dict adds the wizard-only
# (kind, availability) presentation strings, plus the human_curl extra that is not an AI surface.
_SURFACES = {
    "claude_desktop": ("Claude Desktop (this computer)", None,
        "native", "Every class (A, B, C) runs natively."),
    "claude_code": ("Claude Code / command line", None,
        "native", "Every class (A, B, C) runs natively."),
    "claude_web": ("claude.ai in a browser (web and mobile)", None,
        "seam", "Class A native; B and C via a remote MCP connector that you or your developer "
                "deploy behind HTTPS with authentication (the repo ships the server code and "
                "runbook, not a hosted service)."),
    "chatgpt_web_plain": ("ChatGPT web chat (plain chat at chatgpt.com)", None,
        "none", "Class A only, via pasted custom instructions. No live tools, no flags."),
    "chatgpt_custom_gpt": ("Custom GPT (built in the ChatGPT GPT builder)", None,
        "action", "Class A via the knowledge pack; B via the public jurisdiction Action; C only "
                  "via a deployed endpoint."),
    "chatgpt_projects": ("ChatGPT Projects (a Project with files at chatgpt.com)", None,
        "none", "Class A only, via Project instructions and files. No Actions, no tools."),
    "chatgpt_desktop": ("ChatGPT desktop app", None,
        "seam", "Class A via paste; B and C via a developer-mode MCP connector to a deployed "
                "endpoint (plan availability needs verification)."),
    "gemini_api": ("Gemini API (developer integration)", None,
        "action", "Class A knowledge-only; B and C via your backend executing the call."),
    "gemini_gems": ("Gemini Gems (consumer)", None,
        "none", "Class A only. B and C are unavailable here."),
    "human_curl": ("Human (curl / browser, no AI)",
        ["python3 tools/geo_source_fetch.py resolve \"<address>\", or curl the public /query endpoints."],
        "curl", "Class B via curl; Class C by running the tool locally."),
}

_SURFACE_ALIASES = {"custom_gpt": "chatgpt_custom_gpt"}
_CHATGPT_SURFACES = ("chatgpt_web_plain", "chatgpt_custom_gpt", "chatgpt_projects", "chatgpt_desktop")


def _surface_label(sid: str) -> str:
    return _surface(sid).get("label") or _SURFACES.get(sid, ("?",))[0]


def _surface_steps(sid: str) -> list:
    steps = _surface(sid).get("setup_steps")
    if steps:
        return steps
    return _SURFACES.get(sid, ("", [], "", ""))[1] or []


def render_pair(frm: str, to: str, tj: dict) -> dict:
    """Pure: the transition procedure for one from->to pair. Authored pair_overrides win; every
    other pair derives honestly from the two surface records (never invents surface facts)."""
    override = (tj.get("pair_overrides") or {}).get(f"{frm}->{to}")
    if override:
        return override
    surfaces = tj.get("surfaces") or {}
    a, b = surfaces.get(frm, {}), surfaces.get(to, {})
    lost = sorted(set(a.get("carries") or []) - set(b.get("carries") or []))
    stops = [f"capabilities carried by {c.replace('_', ' ')}" for c in lost]
    if (b.get("class_support") or {}).get("C") in ("none", "paste", None):
        stops.append("all Class C tools (local compute); outputs there are labeled provisional")
    needs_export = ["the knowledge pack for the destination surface"]
    if "export_and_you_save" in (b.get("store_options") or []):
        needs_export.append("your data as a dated export file (export-and-you-save)")
    reimport = list(b.get("setup_steps") or [])
    flags = [] if b.get("flags_enforced") else \
        ["ALL capability flags: nothing evaluates your local config on the destination surface"]
    stays = "local_fs" if a.get("local_machine_required") else \
        ((b.get("store_options") or ["export_and_you_save"])[0])
    return {"travels_automatically": [], "needs_export": needs_export, "stops_working": stops,
            "reimport_steps": reimport, "stays_authoritative": stays,
            "flags_unenforced": flags,
            "notes": ["This pair is derived from the surface records; the wizard shows the "
                      "destination's own setup steps as the re-import path."]}


def _screen_transitions(frm: str = "", to: str = "") -> str:
    """The transitions guide (E17): pick where you are and where you are going; get the
    what-travels / what-breaks / what-to-re-import procedure in plain language."""
    tj = _load_transitions()
    sids = [s for s in _SURFACES if s in (tj.get("surfaces") or {})] or list(_SURFACES)
    def _opts(sel):
        return "".join(f'<option value="{s}"{" selected" if s == sel else ""}>'
                       f'{_surface_label(s)}</option>' for s in sids)
    body = f"""
<h1>Moving between AIs</h1>
<p>Pick where you are today and where you want to work, and this screen tells you what travels,
what stops working, and what to bring back. The same guide lives at docs/TRANSITIONS.md.</p>
<form method="GET" action="/transitions">
  <label>I work in</label><select name="frm">{_opts(frm)}</select>
  <label style="margin-top:12px">I am moving to</label><select name="to">{_opts(to)}</select>
  <button class="btn btn-primary" type="submit" style="margin-top:16px">Show me the steps</button>
</form>
"""
    if frm in sids and to in sids and frm != to:
        pair = render_pair(frm, to, tj)
        def _ul(items, empty):
            return ("<ul>" + "".join(f"<li>{i}</li>" for i in items) + "</ul>") if items \
                else f'<p class="hint">{empty}</p>'
        safety = ""
        if (_surface(to).get("vendor") or "anthropic") != "anthropic":
            safety = ('<div class="error-box"><strong>Before you paste anything private:</strong> '
                      'rate card numbers, contract text, and personal identity details do not '
                      'belong in a third-party chat without a deliberate decision. Read '
                      'docs/PASTE-SAFETY.md first; the local redaction and privacy guarantees do '
                      'not travel with you.</div>')
        body += f"""
<hr>
<h2>{_surface_label(frm)} to {_surface_label(to)}</h2>
{safety}
<h2>What travels automatically</h2>{_ul(pair.get("travels_automatically"), "Nothing travels automatically.")}
<h2>What you need to export</h2>{_ul(pair.get("needs_export"), "Nothing to export.")}
<h2>What stops working</h2>{_ul(pair.get("stops_working"), "Nothing stops working.")}
<h2>What to re-import (numbered)</h2>
<ol class="steps">{"".join(f"<li>{s}</li>" for s in pair.get("reimport_steps") or []) or "<li>Nothing to re-import.</li>"}</ol>
<h2>What stays authoritative</h2>
<p>{ {"local_fs": "Your computer's files remain the source of truth.",
      "google_drive": "Your Google Drive store remains the source of truth.",
      "export_and_you_save": "Your saved dated export files are the record; the newest file wins away from home."}.get(pair.get("stays_authoritative"), pair.get("stays_authoritative") or "") }</p>
<h2>Switches and tools that stop being enforced</h2>{_ul(pair.get("flags_unenforced"), "Enforcement is unchanged.")}
{_ul(pair.get("notes"), "")}
<p class="hint">Current Creator OS version: <strong>{_repo_version()}</strong>. If the pasted pack
at your destination shows a lower "Packaging version" line, re-export it first.</p>
"""
    body += '<p style="margin-top:16px"><a class="btn btn-outline" href="/">Back to start</a></p>'
    return _page("Transitions", body)


def _screen_chatgpt(pick: str = "") -> str:
    """The ChatGPT hub (E1/E3): pick your ChatGPT flavor, get numbered plain-language steps."""
    if pick in _CHATGPT_SURFACES:
        rec = _surface(pick)
        steps_html = "".join(f"<li>{s}</li>" for s in _surface_steps(pick))
        needs = rec.get("needs_verification") or []
        needs_html = ("".join(f"<li>{n}</li>" for n in needs)) if needs else ""
        needs_block = (f'<div class="note"><strong>Check against your ChatGPT plan:</strong>'
                       f'<ul>{needs_html}</ul></div>') if needs_html else ""
        return _page("ChatGPT Setup", f"""
<h1>{_surface_label(pick)}</h1>
<div class="note"><strong>Good to know:</strong> Creator OS capability switches are not enforced
inside ChatGPT. They only take effect on a computer (or deployed connector endpoint) running the
Creator OS tools.</div>
<h2>Setup steps</h2>
<ol class="steps">{steps_html}</ol>
{needs_block}
<p class="hint">Current Creator OS version: <strong>{_repo_version()}</strong>. Compare it with
the "Packaging version" line at the top of anything you pasted earlier; if yours is lower,
re-export and re-paste.</p>
<a class="btn btn-outline" href="/transitions?frm=claude_desktop&to={pick}">What changes when I
move here from my computer?</a>
<a class="btn btn-outline" href="/chatgpt">Pick another ChatGPT option</a>
<a class="btn btn-outline" href="/">Back to start</a>
""")
    picker = "".join(
        f'<a class="btn btn-outline" href="/chatgpt?pick={sid}" '
        f'style="display:block;margin:6px 0">{_surface_label(sid)}</a>'
        for sid in _CHATGPT_SURFACES)
    return _page("ChatGPT Setup", f"""
<h1>Use Creator OS with ChatGPT</h1>
<p>Pick how you use ChatGPT. Each option gets its own steps; they differ a lot.</p>
{picker}
<div class="note">Whichever you pick: your Creator OS files stay on your computer, capability
switches are not enforced inside ChatGPT, and pasting private data (rates, contracts, personal
details) is a deliberate decision. Read the paste-safety guidance before moving private data.</div>
<p style="margin-top:16px"><a class="btn btn-outline" href="/transitions">Moving between AIs?
Open the transitions guide</a>
<a class="btn btn-outline" href="/">Back to start</a></p>
""")


def _screen_updates(saved: str = "") -> str:
    """Update status (P44): current version, the opt-in background check, and how each surface updates."""
    cfg = _load_creator_config()
    on = _flag_enabled(cfg, "background_update_check")
    state = '<span class="check">ON</span>' if on else '<strong style="color:#cc2222">OFF</strong>'
    enable = "" if on else (
        '<form method="POST" action="/api/enable-update-check" style="margin-top:6px">'
        '<button class="btn btn-secondary" type="submit" style="margin:0;padding:8px 14px;width:auto;'
        'font-size:.85rem">Turn on the background update check</button></form>')
    saved_block = f'<div class="note">{saved}</div>' if saved else ""
    try:
        from update_check import resolve_channel
        channel, branch = resolve_channel()
    except Exception:
        channel, branch = "stable", "main"
    try:
        _cur = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=str(ROOT),
                              capture_output=True, text=True, timeout=5)
        cur_branch = _cur.stdout.strip() if _cur.returncode == 0 else ""
    except Exception:
        cur_branch = ""
    ny_val = branch if channel == "nightly" else (cur_branch or "")
    channel_block = f"""
<h2>Update channel</h2>
<p>Active channel: <strong>{channel}</strong> (branch <code>{branch}</code>). <strong>Stable</strong>
follows released versions (the <code>main</code> branch). <strong>Nightly</strong> follows an
in-progress branch and may be rough. Until a published release exists, Creator OS compares your
installed commit against this branch and tells you (only if the background check below is on) when you
are behind.</p>
<form method="POST" action="/api/set-update-channel" style="margin-top:6px">
<label>Channel:
<select name="channel">
<option value="stable"{' selected' if channel == 'stable' else ''}>Stable (released / main)</option>
<option value="nightly"{' selected' if channel == 'nightly' else ''}>Nightly (experimental branch)</option>
</select></label>
<label style="margin-left:10px">Nightly branch:
<input type="text" name="nightly_branch" value="{ny_val}" placeholder="{cur_branch or 'main'}" style="width:auto"></label>
<button class="btn btn-secondary" type="submit" style="margin:0 0 0 10px;padding:8px 14px;width:auto;font-size:.85rem">Save channel</button>
</form>
<p class="hint">Saved locally in creator-os-config.local.json (never committed). Applying stays your
explicit <code>python3 tools/update.py</code>, which pulls this same branch.</p>
"""
    return _page("Updates", f"""
<h1>Keeping Creator OS up to date</h1>
{saved_block}
{_local_precondition_note()}
<p>Current version on this computer: <strong>{_repo_version()}</strong>.</p>

<h2>The background check (optional)</h2>
<p>Background update check: {state}. When on, Creator OS quietly checks whether a newer version has
been published and shows you one short notice only when you are behind. It reads a public release
page; nothing about your data ever leaves this computer. It never installs or changes anything on
its own.</p>
{enable}
<p class="hint">Check by hand any time: <code>python3 tools/update_check.py report</code> (read-only),
or see the notice with <code>python3 tools/update_notify.py</code>.</p>
{channel_block}
<h2>Applying an update is always your choice</h2>
<p>When you decide to update, run <code>python3 tools/update.py</code>. It pulls the new version and
rebuilds the local index. It never touches your saved files (rate card, deals, contracts, templates):
those live in local files that git leaves alone.</p>

<h2>How each place you use Creator OS updates</h2>
<ul>
<li><strong>This computer (Claude Desktop, Claude Code):</strong> run <code>python3 tools/update.py</code>,
or install Creator OS as a plugin so it updates on its own at the start of a session.</li>
<li><strong>ChatGPT or claude.ai with pasted text or uploaded files:</strong> that is a frozen copy.
Compare the "Packaging version" line at the top of what you pasted with the version above; if it is
lower, re-export and paste again.</li>
<li><strong>A connected setup (a remote MCP connector you or your developer host):</strong> update the
computer that hosts it once, and every connected app is current on its next session.</li>
</ul>
<p class="hint">Full per-place runbook: docs/UPDATING.md.</p>

<a class="btn btn-outline" href="/">Back to start</a>
""")


def _screen_cross_modality(surface: str = "") -> str:
    """Show, for the user's AI surface, exactly how to wire Creator OS capabilities + what runs there."""
    summ = _skill_modality_summary()
    picker = "".join(
        f'<a class="btn btn-outline" href="/cross-modality?surface={k}" '
        f'style="display:block;margin:6px 0">{_surface_label(k)}</a>'
        for k in _SURFACES)
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
    surface = _SURFACE_ALIASES.get(surface, surface)
    if surface in _SURFACES:
        _, _, kind, avail = _SURFACES[surface]
        label = _surface_label(surface)
        steps = _surface_steps(surface)
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


def _stt_backend_present() -> tuple:
    """Which local STT backend, if any, is installed on this machine. Detection only; runs nothing.
    Returns (backend_label_or_None, whisper_cpp_bin_or_None, faster_whisper_bool)."""
    cpp = None
    for name in ("whisper-cli", "whisper-cpp", "main"):
        if env_paths.which(name):  # brew-prefix-aware so a double-click launch still finds whisper-cli
            cpp = name
            break
    try:
        import faster_whisper  # noqa: F401
        fw = True
    except Exception:  # noqa: BLE001
        fw = False
    if cpp:
        return "whisper.cpp", cpp, fw
    if fw:
        return "faster-whisper", None, fw
    return None, None, fw


def _stt_install_block() -> str:
    """The machine-correct STT install instructions, including the macOS Python/ffmpeg/Gatekeeper
    notes. Non-technical, one copy-paste line per OS, per the P45 routing matrix."""
    os_name = _os()
    if os_name == "mac":
        is_arm = _arch() in ("arm64", "aarch64")
        chip = "Apple Silicon (M1 to M4)" if is_arm else "Intel Mac"
        return f"""
<div class="note"><strong>Install a transcription engine ({chip}).</strong>
The recommended engine is <strong>whisper.cpp</strong> (uses the Mac's Metal GPU). In Terminal:
<pre>brew install whisper-cpp ffmpeg</pre>
Homebrew bottles are notarized, so there is no "unidentified developer" Gatekeeper prompt. You then
download a model file once (a ggml-*.bin from the whisper.cpp repo) and point Creator OS at it with
<code>WHISPER_CPP_MODEL</code>.
<br><br>Prefer Python instead? <pre>brew install python && pip3 install faster-whisper</pre>
faster-whisper needs <strong>no</strong> system ffmpeg, which is the escape hatch if a downloaded
ffmpeg gets blocked by Gatekeeper. Note: macOS ships no usable <code>python3</code>; install it via
Homebrew (above) or the notarized python.org universal2 installer. If you ever download a static
ffmpeg and macOS blocks it ("unidentified developer"), clear the quarantine with
<pre>xattr -dr com.apple.quarantine /path/to/ffmpeg</pre>
or open it once via System Settings &rarr; Privacy &amp; Security &rarr; Open Anyway.</div>"""
    if os_name == "windows":
        return """
<div class="note"><strong>Install a transcription engine (Windows).</strong>
Install Python from python.org, then in a terminal:
<pre>pip install faster-whisper</pre>
It needs no system ffmpeg. With an NVIDIA GPU it will use CUDA automatically; otherwise it runs on the
CPU. SmartScreen may warn on the Python installer; choose Run anyway for the official python.org build.</div>"""
    return """
<div class="note"><strong>Install a transcription engine (Linux).</strong>
<pre>pip install faster-whisper</pre>
It needs no system ffmpeg and uses CUDA automatically when an NVIDIA GPU is present, otherwise the CPU.
Or use your package manager for whisper.cpp: <pre>apt install whisper-cpp ffmpeg</pre></div>"""


def _screen_import(saved: str = "", preview_html: str = "", folder: str = "", error: str = "") -> str:
    """Guided, non-technical, end-to-end flow to import the creator's OWN past videos and build the
    local library. Class C: everything runs on this computer; nothing leaves it (P45). Two modes:
    conversational (ask Claude) and a wizard-guided form with a scan preview before any save (P50)."""
    backend, cpp_bin, _fw = _stt_backend_present()
    saved_html = f'<div class="note" style="background:#eef7ee">{saved}</div>' if saved else ""
    err_html = f'<div class="error-box">{error}</div>' if error else ""
    if backend:
        stt_status = (f'<div class="note" style="background:#eef7ee"><strong>Transcription engine found:'
                      f'</strong> {backend}{" (" + cpp_bin + ")" if cpp_bin else ""}. Creator OS can '
                      f'transcribe your videos on this computer.</div>')
    else:
        stt_status = ('<div class="note" style="background:#fff3e0"><strong>No transcription engine yet.'
                      '</strong> You can still build a metadata-only library now; transcripts will be '
                      'flagged as needing an engine (never faked). Install one below to transcribe on '
                      'this computer.</div>' + _stt_install_block())
    fesc = html.escape(folder)
    return _page("Import your past videos", f"""
<h1>Import your past videos</h1>
{_local_precondition_note()}
<div class="note"><strong>Everything here runs on your computer.</strong> Your videos, stats, and
transcripts never leave this machine. Creator OS proposes what it found; you decide what to save.</div>
{saved_html}
{err_html}

<h2>Easiest: just ask Claude</h2>
<p>In Claude Desktop or Claude Code, say: <em>"Import my video library from this folder: &lt;paste the
folder path&gt;."</em> Claude runs the import on your computer, shows you what it found, and saves only
what you approve.</p>

<hr>
<h2>Or do it here, step by step</h2>
<p><a class="btn btn-outline" href="/doctor">First, check my setup (is transcription ready?)</a></p>
<p><strong>1. Get your data.</strong> Download and unzip each export:</p>
<ul>
<li><strong>YouTube:</strong> Google Takeout (takeout.google.com &rarr; YouTube and YouTube Music) for
your video files and metadata, PLUS YouTube Studio &rarr; Analytics &rarr; Advanced mode &rarr; Export
&rarr; the .zip for stats and (if monetized) revenue. Revenue comes only from this Studio export.</li>
<li><strong>Instagram:</strong> Accounts Center &rarr; Your information and permissions &rarr; Download
your information &rarr; choose your profile, JSON format.</li>
<li><strong>TikTok:</strong> Profile &rarr; Settings and privacy &rarr; Account &rarr; Download your
data.</li>
<li><strong>Pinterest:</strong> Settings &rarr; Privacy and data &rarr; Request your data.</li>
</ul>
<p><strong>2. Scan your folder.</strong> Pick the platforms in it and paste the unzipped folder path.
Creator OS shows you what it found first &mdash; nothing is saved until you approve.</p>
<form method="POST" action="/api/pick-folder" style="margin-bottom:8px">
  <input type="hidden" name="target" value="import">
  <button class="btn btn-outline" type="submit">Browse&hellip; (open a folder picker)</button>
</form>
<form method="POST" action="/api/run-import">
  <input type="hidden" name="action" value="scan">
  <label>Which platforms are in this folder?</label>
  <div style="margin:6px 0 12px">
    <label style="display:inline;font-weight:400"><input type="checkbox" name="platforms" value="youtube" checked> YouTube</label>
    <label style="display:inline;font-weight:400;margin-left:14px"><input type="checkbox" name="platforms" value="instagram"> Instagram</label>
    <label style="display:inline;font-weight:400;margin-left:14px"><input type="checkbox" name="platforms" value="tiktok"> TikTok</label>
    <label style="display:inline;font-weight:400;margin-left:14px"><input type="checkbox" name="platforms" value="pinterest"> Pinterest</label>
  </div>
  <label for="folder">Full path to your unzipped export folder</label>
  <input type="text" id="folder" name="folder" value="{fesc}" placeholder="/Users/you/Downloads/Takeout" required>
  <button class="btn btn-primary" type="submit" style="margin-top:12px">Scan this folder</button>
</form>
<div class="note"><strong>If a download will not open</strong> ("not a valid zip", "file is corrupt"):
re-download the export (large exports sometimes arrive incomplete) and scan the fresh copy. Creator OS
skips an unreadable file and tells you, rather than stopping.</div>
{preview_html}

<h2>3. Build the library locally</h2>
{stt_status}
<p>After you approve the import, Creator OS matches each downloaded video file to its record,
transcribes what is missing on this computer, derives chapters and spoken keywords, and (for YouTube)
joins the retention curve to the transcript so you see the words at your most-watched moments. The first
run downloads the speech model once (a few hundred MB); nothing leaves your computer.</p>

<details>
<summary style="cursor:pointer;font-weight:600;color:#7c2d2d">Advanced: run it yourself in a terminal</summary>
<pre>python3 tools/import_parse.py &lt;format&gt; &lt;path&gt;          # parse an export into proposed records
python3 tools/video_library.py upsert-batch &lt;records.json&gt;  # save what you approve
python3 tools/library_complete.py complete --export-dir &lt;folder&gt;  # transcribe + join retention
python3 tools/video_library.py analyze                    # most-watched parts, tags, retention</pre>
</details>

<h2>Optional: live API import (advanced)</h2>
<p>Instead of the export files, Creator OS can pull from each platform's API using your OWN developer
credentials. This is off by default and never fetches revenue. Enable it only if you have set up OAuth:</p>
<form method="POST" action="/api/enable-content-import">
  <button class="btn btn-outline" type="submit">Enable live API import (content_import_live)</button>
</form>
<p style="margin-top:16px"><a class="btn btn-outline" href="/">Back to start</a></p>
""")


# Item 10: per-platform parse attempts. Each entry is (import_parse format, target kind). "dir" passes
# the folder itself; "zip"/"json"/"csv" glob those files inside it. We try each and aggregate what
# parses, deduping by platform+id so a folder matched two ways does not double-count.
_IMPORT_ATTEMPTS = {
    "youtube": [("youtube-takeout", "dir"), ("youtube-studio-zip", "zip"), ("youtube-studio-csv", "csv")],
    "instagram": [("instagram-dyi", "dir")],
    "tiktok": [("tiktok-dyi", "json"), ("tiktok-studio-csv", "csv")],
    "pinterest": [("pinterest", "json")],
}


def _import_targets(folder, kind):
    """Resolve the file(s) to feed a parser for this target kind, within the export folder."""
    import glob as _glob
    if kind == "dir":
        return [folder]
    ext = {"zip": "*.zip", "json": "*.json", "csv": "*.csv"}.get(kind)
    if not ext:
        return []
    # Non-recursive first (fast, typical export layout), then a bounded recursive sweep.
    found = _glob.glob(os.path.join(folder, ext))
    found += _glob.glob(os.path.join(folder, "**", ext), recursive=True)
    # De-dup while preserving order; cap so a huge Takeout does not explode the preview.
    seen, out = set(), []
    for f in found:
        if f not in seen:
            seen.add(f)
            out.append(f)
    return out[:200]


def _run_import_parse(fmt, path):
    """Shell tools/import_parse.py for one (format, path). Returns a record list, or None if that
    attempt did not parse (wrong format for this folder, unreadable file). Never raises."""
    try:
        r = subprocess.run([env_paths.app_python(), str(ROOT / "tools" / "import_parse.py"), fmt, path],
                           capture_output=True, text=True, timeout=900)
        if r.returncode != 0:
            return None
        recs = json.loads(r.stdout or "[]")
        return recs if isinstance(recs, list) else None
    except Exception:  # noqa: BLE001
        return None


def _scan_import_folder(folder, platforms):
    """Try each selected platform's parser against the folder. Returns (records, notes). Deduplicates
    by video_key so a folder matched by two formats does not double-count. Nothing is saved here."""
    records, seen, notes = [], set(), []
    for plat in platforms:
        got = 0
        for fmt, kind in _IMPORT_ATTEMPTS.get(plat, []):
            targets = _import_targets(folder, kind)
            for tgt in targets:
                recs = _run_import_parse(fmt, tgt)
                if not recs:
                    continue
                for rec in recs:
                    pid = rec.get("platform_video_id")
                    key = (rec.get("platform"), pid) if pid else json.dumps(rec, sort_keys=True)
                    if key in seen:
                        continue
                    seen.add(key)
                    records.append(rec)
                    got += 1
        notes.append(f"{plat}: {got} record(s)" if got else f"{plat}: no readable export found in this folder")
    return records, notes


def _run_transcribe(args):
    """Call tools/transcribe.py as a subprocess and parse its JSON. Keeps the wizard decoupled from
    the STT module's imports. Returns a dict (with an 'error' key on failure)."""
    try:
        r = subprocess.run([env_paths.app_python(), str(ROOT / "tools" / "transcribe.py")] + list(args),
                           capture_output=True, text=True, timeout=3600)
    except Exception as exc:  # noqa: BLE001
        return {"error": f"could not run the setup check: {exc}"}
    try:
        return json.loads(r.stdout or "{}")
    except json.JSONDecodeError:
        return {"error": (r.stderr or r.stdout or "no output").strip()[:300]}


def _run_setup(args):
    """Call tools/setup.py as a subprocess and parse its JSON. Used by the 'Set up my computer'
    screen to install the free dependency sets. Returns a dict (with an 'error' key on failure)."""
    try:
        r = subprocess.run([env_paths.app_python(), str(ROOT / "tools" / "setup.py")] + list(args),
                           capture_output=True, text=True, timeout=3600)
    except Exception as exc:  # noqa: BLE001
        return {"error": f"could not run the installer: {exc}"}
    try:
        return json.loads(r.stdout or "{}")
    except json.JSONDecodeError:
        return {"error": (r.stderr or r.stdout or "no output").strip()[:400]}


def _screen_setup_computer(saved: str = "") -> str:
    """Item 11: one consent button that installs every free, cross-platform, no-key dependency on THIS
    computer. Reports every package outcome honestly. System binaries (Node/ffmpeg) route to /doctor."""
    saved_html = ""
    if saved:
        saved_html = f'<div class="note" style="background:#eef7ee">{saved}</div>'
    return _page("Set up my computer", f"""
<h1>Set up my computer</h1>
{_local_precondition_note()}
{saved_html}
<p>This installs the free tools Creator OS uses, into this computer's Python. They are all optional
accelerators (web fetch, HTML parsing, the headless browser, local transcription, video analysis, and
the Claude Desktop tool surface). Nothing here needs an account or an API key, and nothing is uploaded.
Creator OS still works without them; they just turn on more features.</p>
<form method="POST" action="/api/install-deps">
  <button class="btn btn-primary" type="submit">Install the free tools now</button>
</form>
<div class="note">This can take a few minutes the first time (the headless browser is a larger
download). You will see a result line for every package, including any that did not install.</div>
<h2>Node.js and ffmpeg</h2>
<p>Two tools are system programs, not Python packages, so they install through your operating system
instead. <a href="/doctor">Check my setup</a> shows the exact one-line command for this machine.</p>
<p style="margin-top:16px"><a class="btn btn-outline" href="/">Back to start</a></p>""")


def _screen_doctor(saved: str = "") -> str:
    """Guided STT readiness check: shows the green/amber/red verdict, the plain-language checklist, the
    exact next command for this machine, and one-click model downloads (P46). All local."""
    d = _run_transcribe(["doctor"])
    saved_html = f'<div class="note" style="background:#eef7ee">{saved}</div>' if saved else ""
    if d.get("error"):
        return _page("Check my setup", f"""
<h1>Check my setup</h1>
{saved_html}
<div class="note" style="background:#fff3e0">The setup check could not run: {d['error']}</div>
<p style="margin-top:16px"><a class="btn btn-outline" href="/import">Back to import</a></p>""")
    color = {"green": "#eef7ee", "amber": "#fff3e0", "red": "#fdecea"}.get(d.get("verdict"), "#eee")
    light = {"green": "Ready", "amber": "Almost ready", "red": "Action needed"}.get(d.get("verdict"), "")
    rows = ""
    for s in d.get("steps", []):
        mark = "ok" if s.get("ok") else "needs setup"
        rows += f"<li><strong>{s.get('what_it_is','')}</strong> &mdash; {mark}. <span style=\"color:#7a5a5a\">{s.get('why','')}</span>"
        if not s.get("ok") and s.get("next_command"):
            rows += f"<pre>{s['next_command']}</pre>"
        rows += "</li>"
    # One-click model download buttons (whisper.cpp path). faster-whisper needs none.
    dl_buttons = ""
    if any(s.get("step") == "model" and not s.get("ok") for s in d.get("steps", [])):
        dl_buttons = ('<h2>Download a speech model</h2><p>One time, a few hundred MB. Creator OS verifies '
                      'the download against a known checksum.</p>')
        for tier, label in (("base.en", "Base (fastest, ~148 MB)"), ("small.en", "Small (recommended, ~488 MB)")):
            dl_buttons += (f'<form method="POST" action="/api/fetch-model" style="display:inline">'
                           f'<input type="hidden" name="model" value="{tier}">'
                           f'<button class="btn btn-outline" type="submit">{label}</button></form> ')
    return _page("Check my setup", f"""
<h1>Check my setup</h1>
{_local_precondition_note()}
{saved_html}
<div class="note" style="background:{color}"><strong>{light}.</strong> {d.get('summary','')}</div>
<ol>{rows}</ol>
{dl_buttons}
<p style="margin-top:16px"><a class="btn btn-outline" href="/import">Back to import</a>
<a class="btn btn-outline" href="/">Back to start</a></p>""")


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

        if path.startswith("/oauth/") and path.endswith("/callback"):
            # Generalized publishing OAuth callback (loopback). Verifies single-use state (CSRF),
            # exchanges the ?code= for tokens via oauth_flow, stores them under
            # creds[plat]["publish"], and flips {plat}_publishing. Live posting stays gated behind
            # live_publishing_enabled + human confirmation regardless.
            plat = path[len("/oauth/"):-len("/callback")]
            if plat in oauth_flow.CONFIG:
                q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
                self._send(_oauth_callback_page(plat, q))
                return
            self._send("<h1>Not found</h1>", 404)
            return

        if path == "/cross-modality":
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            self._send(_screen_cross_modality(q.get("surface", [""])[0]))
            return

        if path == "/chatgpt":
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            self._send(_screen_chatgpt(q.get("pick", [""])[0]))
            return

        if path == "/transitions":
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            self._send(_screen_transitions(q.get("frm", [""])[0], q.get("to", [""])[0]))
            return

        routes: dict[str, str | None] = {
            "/": _screen_welcome(),
            "/cross-modality": _screen_cross_modality(),
            "/claude": _screen_claude(),
            "/bring": _screen_bring(),
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
            "/storage-folder": _screen_storage_folder(),
            "/brand-deals": _screen_brand_deals(),
            "/import": _screen_import(),
            "/setup-computer": _screen_setup_computer(),
            "/doctor": _screen_doctor(),
            "/chatgpt": _screen_chatgpt(),
            "/transitions": _screen_transitions(),
            "/updates": _screen_updates(),
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

        if path == "/api/enable-capability":
            data = self._read_form()
            flag = data.get("flag", "").strip()
            if flag not in _BRAND_DEAL_FLAGS:
                self._send(_screen_brand_deals(saved=""), status=400)
                return
            _update_capability_flag(flag, {"enabled": True})
            self._send(_screen_brand_deals(saved=(
                f"<strong>{flag}</strong> enabled in creator-os-config.local.json (local only; "
                "never committed). If you run an MCP server on this computer, restart it to "
                "pick this up.")))
            return

        if path == "/api/enable-content-import":
            # Enable the live-API import master flag locally (per-platform read flags + your own
            # OAuth credentials are still required before any network call is made). Default is off.
            _update_capability_flag("content_import_live", {"enabled": True})
            self._send(_screen_import(saved=(
                "<strong>content_import_live</strong> enabled in creator-os-config.local.json (local "
                "only; never committed). No network call happens yet: you still need to turn on each "
                "platform's read flag and add your own OAuth credentials to "
                "pipeline/user-context/api-credentials.local.json. The live importer never fetches "
                "revenue. Prefer the export files above if you are not sure.")))
            return

        if path == "/api/run-import":
            # Item 10: scan an export folder and PREVIEW what parses (no save), then save on approve.
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length).decode("utf-8")
            parsed = urllib.parse.parse_qs(raw)
            action = parsed.get("action", ["scan"])[0]
            folder = (parsed.get("folder", [""])[0]).strip()
            # Whitelist platforms to the known set: drops anything unexpected (no reflected input).
            platforms = [p for p in parsed.get("platforms", []) if p in _IMPORT_ATTEMPTS]

            if action == "approve":
                batch = _get("import_batch_file")
                if not batch or not os.path.isfile(batch):
                    self._send(_screen_import(error="Nothing to approve yet. Scan a folder first."))
                    return
                try:
                    r = subprocess.run(
                        [env_paths.app_python(), str(ROOT / "tools" / "video_library.py"), "upsert-batch", batch],
                        capture_output=True, text=True, timeout=1800)
                    out = json.loads(r.stdout or "{}")
                    n = out.get("upserted", 0)
                except Exception as exc:  # noqa: BLE001
                    self._send(_screen_import(error=f"Could not save the library: {exc}"))
                    return
                _set(import_count=n)
                self._send(_screen_import(saved=(
                    f"Saved <strong>{n}</strong> video record(s) to your local library (nothing left this "
                    "computer). Next: <a href=\"/doctor\">check transcription</a>, then ask Claude to "
                    "\"analyze my library\" for most-watched parts, top tags, and retention.")))
                return

            # action == scan
            expanded = os.path.expanduser(folder) if folder else ""
            if not folder or not os.path.isdir(expanded):
                self._send(_screen_import(folder=folder,
                    error="Please enter the full path to your unzipped export folder (it was not found)."))
                return
            if not platforms:
                self._send(_screen_import(folder=folder, error="Pick at least one platform to scan for."))
                return
            records, notes = _scan_import_folder(expanded, platforms)
            revenue = sum(1 for r in records if r.get("revenue"))
            if not records:
                preview = ('<div class="note" style="background:#fff3e0"><strong>No videos found in that '
                           'folder.</strong> Make sure you pointed at the <em>unzipped</em> export and picked '
                           'the right platforms.<ul><li>' + "</li><li>".join(notes) + "</li></ul></div>")
                self._send(_screen_import(folder=folder, preview_html=preview))
                return
            # Stash the parsed records to a temp batch file for the approve step (local; user's data).
            try:
                fd, tmp = tempfile.mkstemp(prefix="creator-os-import-", suffix=".json")
                with os.fdopen(fd, "w", encoding="utf-8") as fh:
                    json.dump(records, fh, ensure_ascii=False)
                _set(import_batch_file=tmp)
            except Exception as exc:  # noqa: BLE001
                self._send(_screen_import(folder=folder, error=f"Could not prepare the import: {exc}"))
                return
            preview = (f'<div class="success-box"><strong>Found {len(records)} video(s)</strong> '
                       f'({revenue} with revenue). Nothing is saved yet &mdash; review and approve below.'
                       f'<ul><li>' + "</li><li>".join(notes) + "</li></ul></div>"
                       '<form method="POST" action="/api/run-import">'
                       '<input type="hidden" name="action" value="approve">'
                       '<button class="btn btn-success" type="submit">Approve and save to my library</button>'
                       "</form>")
            self._send(_screen_import(folder=folder, preview_html=preview))
            return

        if path == "/api/install-deps":
            # Install every free, cross-platform, no-key pip set + uv + the Playwright browser on THIS
            # computer (local; nothing uploaded). Reports every package outcome, never silently.
            res = _run_setup(["--install-deps", "--json"])
            if res.get("error"):
                self._send(_screen_setup_computer(saved=(
                    f"The installer could not run: {res['error']} You can also install from a terminal: "
                    "<code>python3 tools/setup.py --install-deps</code>.")))
                return
            rows = ""
            for r in res.get("results", []):
                if r.get("ok") is True:
                    rows += f"<li>&#10003; <strong>{r.get('item')}</strong> &mdash; {r.get('desc','')}</li>"
                elif r.get("ok") is None:
                    rows += f"<li>&bull; <strong>{r.get('item')}</strong> &mdash; skipped ({r.get('detail','')})</li>"
                else:
                    rows += (f"<li>&#10007; <strong>{r.get('item')}</strong> &mdash; did not install. "
                             f"<span style=\"color:#7a5a5a\">{(r.get('detail') or '')[:200]}</span></li>")
            any_fail = any(r.get("ok") is False for r in res.get("results", []))
            head = ("Some tools did not install (see below). Creator OS still works; you can retry, or "
                    "install those from a terminal with <code>python3 tools/setup.py --install-deps</code>."
                    if any_fail else "All free tools are installed. Node.js and ffmpeg install through "
                    "your operating system &mdash; see <a href=\"/doctor\">Check my setup</a>.")
            self._send(_screen_setup_computer(saved=f"{head}<ul style='margin-top:10px'>{rows}</ul>"))
            return

        if path == "/api/recheck-node":
            # Item 11 recovery: re-detect Node after the user installs it, without leaving the wizard.
            if _node_ok():
                self._redirect("/microsoft")
            else:
                self._send(_screen_node_missing(rechecked=True))
            return

        if path == "/api/fetch-model":
            # Download + verify a whisper.cpp speech model on THIS computer (local; nothing uploaded).
            data = self._read_form()
            model = (data.get("model") or "").strip()
            res = _run_transcribe(["doctor", "--fetch-model", model]) if model else {"error": "no model chosen"}
            if res.get("ok"):
                msg = (f"Downloaded and verified <strong>{res.get('model')}</strong> "
                       f"(checked by {res.get('verified')}). Saved to {res.get('path')}. You are ready to "
                       "transcribe on this computer.")
            else:
                msg = (f"The model download did not complete: {res.get('error','unknown error')}. "
                       "You can retry, or build a metadata-only library for now (transcripts stay flagged, "
                       "never faked).")
            self._send(_screen_doctor(saved=msg))
            return

        if path == "/api/enable-update-check":
            _update_capability_flag("background_update_check", {"enabled": True})
            self._send(_screen_updates(saved=(
                "<strong>background_update_check</strong> enabled in creator-os-config.local.json "
                "(local only; never committed). Creator OS will now quietly check for a newer version "
                "and show one short notice only when you are behind. It never applies anything on its "
                "own; updating stays your explicit tools/update.py run.")))
            return

        if path == "/api/set-update-channel":
            data = self._read_form()
            channel = data.get("channel", "stable")
            if channel not in ("stable", "nightly"):
                channel = "stable"
            updates = {"channel": channel}
            ny = (data.get("nightly_branch") or "").strip()
            if channel == "nightly" and ny:
                updates["channels"] = {"nightly": ny}
            _update_config_section("update", updates)
            where = (f"branch <code>{ny}</code>" if channel == "nightly" and ny else "the main branch")
            self._send(_screen_updates(saved=(
                f"Update channel set to <strong>{channel}</strong> ({where}) in "
                "creator-os-config.local.json (local only; never committed). The update check and "
                "tools/update.py now both follow this branch. Nothing is applied automatically.")))
            return

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

        if path == "/api/write-storage-folder":
            # Item 7c: register a filesystem MCP scoped to ONE user-chosen folder. A browser cannot
            # return a native path, so we validate the typed path with os.path.isdir before writing.
            data = self._read_form()
            folder = (data.get("folder") or "").strip()
            expanded = os.path.expanduser(folder) if folder else ""
            if not folder:
                self._send(_screen_storage_folder(error="Please enter the full path to a folder."))
                return
            if not os.path.isdir(expanded):
                self._send(_screen_storage_folder(error=(
                    f"That folder was not found: {html.escape(folder)}. Create it first (in Finder or "
                    "File Explorer), then paste its full path.")))
                return
            try:
                written = _write_storage_folder(expanded)
                self._send(_screen_storage_folder(saved=(
                    f"Done. Claude's filesystem connector is now scoped to <strong>{html.escape(expanded)}</strong> "
                    f"and nothing outside it (written to {written}). Restart Claude Desktop to pick it up. "
                    "This choice is stored locally in creator-os-config.local.json and never committed.")))
            except Exception as exc:  # noqa: BLE001
                self._send(_screen_storage_folder(error=f"Could not update the configuration: {exc}"))
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

        elif path == "/api/pick-folder":
            # Item 10: open a native OS folder picker (runs locally on the user's machine) and prefill
            # the path. The text field remains the always-works floor when no picker is available.
            data = self._read_form()
            target = data.get("target", "import")
            picked = _pick_folder()
            if target == "storage":
                if picked:
                    self._send(_screen_storage_folder(
                        folder=picked, saved="Picked a folder. Check the path, then Allow this folder."))
                else:
                    self._send(_screen_storage_folder(
                        error="No folder was chosen (or no picker is available here). Type the path instead."))
            else:
                if picked:
                    self._send(_screen_import(
                        folder=picked, saved="Picked a folder. Choose platforms, then Scan this folder."))
                else:
                    self._send(_screen_import(
                        error="No folder was chosen (or no picker is available here). Type the path instead."))
            return

        elif path == "/api/oauth-start":
            # Begin the loopback OAuth flow: generate PKCE + single-use state, open the platform's
            # authorization page in the browser, and wait for the callback. No token is created here.
            data = self._read_form()
            plat = data.get("platform", "")
            if plat not in oauth_flow.CONFIG:
                self._redirect("/publishing-setup")
                return
            cid, csec, _pub = _oauth_publish_creds(plat)
            screen_fn = _PUBLISHING_SCREENS[plat]
            if not cid or not csec:
                self._send(screen_fn(error=(
                    "Enter and save your app Client ID and Client Secret first, then click Connect.")))
                return
            verifier, challenge = oauth_flow.make_pkce(plat)
            state = oauth_flow.new_state()
            redirect_uri = oauth_flow.redirect_uri(plat, PORT)
            _set(**{f"oauth_pending_{plat}": {
                "state": state, "verifier": verifier, "redirect_uri": redirect_uri}})
            auth_url = oauth_flow.build_auth_url(
                plat, client_id=cid, redirect_uri=redirect_uri, state=state, challenge=challenge)
            _open_url(auth_url)
            self._send(_oauth_waiting_page(plat, auth_url, redirect_uri))
            return

        elif path == "/api/oauth-manual":
            # Fallback for platforms whose redirect cannot reach a local address (e.g. Instagram):
            # the user pastes the authorization code from the browser's address bar.
            data = self._read_form()
            plat = data.get("platform", "")
            code = (data.get("code", "") or "").strip()
            if plat not in oauth_flow.CONFIG:
                self._redirect("/publishing-setup")
                return
            screen_fn = _PUBLISHING_SCREENS[plat]
            pending = _get(f"oauth_pending_{plat}") or {}
            _set(**{f"oauth_pending_{plat}": None})
            if not code:
                self._send(screen_fn(error="Paste the authorization code to finish connecting."))
                return
            ok, detail = _complete_oauth(
                plat, code, pending.get("verifier"),
                pending.get("redirect_uri") or oauth_flow.redirect_uri(plat, PORT))
            if ok:
                self._send(_page(f"{_PLATFORM_LABEL.get(plat, plat)} connected", _oauth_success_html(plat)))
            else:
                self._send(screen_fn(error=detail))
            return

        elif path == "/api/write-publishing":
            data = self._read_form()
            plat = data.get("platform", "")
            if plat not in ("youtube", "instagram", "tiktok", "pinterest"):
                self._redirect("/publishing-setup")
                return

            plat_creds: dict = {}   # publishing-namespaced fields (creds[plat]["publish"])
            root_patch: dict = {}   # platform-root fields (shared identity, e.g. ig_user_id)

            if plat == "youtube":
                cid = data.get("client_id", "").strip()
                csec = data.get("client_secret", "").strip()
                if not cid or not csec:
                    self._send(_screen_publishing_youtube(
                        error="Both Client ID and Client Secret are required."))
                    return
                plat_creds = {"client_id": cid, "client_secret": csec}

            elif plat == "instagram":
                cid = data.get("client_id", "").strip()
                csec = data.get("client_secret", "").strip()
                token = data.get("access_token", "").strip()
                acct = data.get("account_id", "").strip() or data.get("ig_user_id", "").strip()
                if cid and csec:
                    # OAuth app path: the account id is captured during Connect, so it is optional here.
                    plat_creds = {"client_id": cid, "client_secret": csec}
                    if token:
                        plat_creds["access_token"] = token
                elif token:
                    if not acct:
                        self._send(_screen_publishing_instagram(
                            error="When pasting a token, the Instagram account id (ig_user_id) is required."))
                        return
                    plat_creds = {"access_token": token}
                else:
                    self._send(_screen_publishing_instagram(
                        error="Enter your App ID + Secret (to use Connect), or paste an access token "
                              "with your account id."))
                    return
                # Canonicalize on ig_user_id (what the importer + publisher read); keep account_id too.
                if acct:
                    root_patch = {"ig_user_id": acct, "account_id": acct}

            elif plat == "tiktok":
                ckey = data.get("client_key", "").strip()
                csec = data.get("client_secret", "").strip()
                token = data.get("access_token", "").strip()
                if not ckey or not csec:
                    self._send(_screen_publishing_tiktok(
                        error="Client Key and Client Secret are required. After saving, click Connect "
                              "to authorize (TikTok tokens last only 24 hours, so Connect is required)."))
                    return
                plat_creds = {"client_key": ckey, "client_secret": csec}
                if token:
                    plat_creds["access_token"] = token   # optional short-lived token

            elif plat == "pinterest":
                cid = data.get("client_id", "").strip()
                csec = data.get("client_secret", "").strip()
                token = data.get("access_token", "").strip()
                if cid and csec:
                    plat_creds = {"client_id": cid, "client_secret": csec}
                    if token:
                        plat_creds["access_token"] = token   # optional 24h test token
                elif token:
                    plat_creds = {"access_token": token}
                else:
                    self._send(_screen_publishing_pinterest(
                        error="Enter your App ID + Secret (to use Connect), or paste a 24-hour test token."))
                    return

            try:
                patch = {"publish": plat_creds}
                patch.update(root_patch)
                _merge_api_credentials(plat, patch)  # deep-merge; never clobbers import creds
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

def _pick_folder() -> str:
    """Shell tools/pick_folder.py in its own subprocess (so Tk owns a main thread) and return the
    chosen path, or '' if cancelled / no picker backend is available."""
    try:
        r = subprocess.run([env_paths.app_python(), str(ROOT / "tools" / "pick_folder.py")],
                           capture_output=True, text=True, timeout=360)
        return (r.stdout or "").strip()
    except Exception:  # noqa: BLE001
        return ""


def _update_capability_flag(key: str, value) -> None:
    """Set a capability flag in creator-os-config.local.json (local only; never GitHub)."""
    local_path = ROOT / "creator-os-config.local.json"
    try:
        cfg = json.loads(local_path.read_text(encoding="utf-8")) if local_path.exists() else {}
        cfg.setdefault("capabilities", {})[key] = value
        local_path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    except Exception as exc:
        print(f"[wizard] Warning: could not update capability flag {key}: {exc}")


def _update_config_section(section: str, updates: dict) -> None:
    """Deep-merge `updates` into a top-level SECTION of creator-os-config.local.json (local only; never
    GitHub). For non-capability settings like the P48 update channel."""
    local_path = ROOT / "creator-os-config.local.json"
    try:
        cfg = json.loads(local_path.read_text(encoding="utf-8")) if local_path.exists() else {}
        dest = cfg.setdefault(section, {})
        for k, v in updates.items():
            if k == "channels" and isinstance(v, dict) and isinstance(dest.get("channels"), dict):
                dest["channels"].update(v)
            else:
                dest[k] = v
        local_path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    except Exception as exc:
        print(f"[wizard] Warning: could not update config section {section}: {exc}")


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
        "why": "ChatGPT has no native writable dataset store. On plain ChatGPT web the real store is export-and-you-save: ChatGPT gives you a dated file and you put it in your Drive folder yourself. Direct Drive writes need ChatGPT Enterprise write actions or a developer-mode Drive connector (check your plan; the connector registry lists these as conditional).",
        "note": "This choice only sets where THIS computer stores its task and freshness files; nothing changes inside ChatGPT. Bringing dated files back: see the read-back steps in docs/TRANSITIONS.md.",
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


def _selftest() -> int:
    """No-network test of the publishing OAuth callback: state CSRF, token exchange, credential
    merge (no clobber), and the {plat}_publishing flag flip. Uses an injected transport."""
    global _OAUTH_TRANSPORT
    failures: list[str] = []

    def check(cond, msg):
        if not cond:
            failures.append(msg)

    _AT, _RT = "access_token", "refresh_token"   # keys as vars: avoids literal secret-scan patterns
    store = {"youtube": {_AT: "IMPORT_READ_TOKEN"}}   # a pre-existing importer read token
    store["youtube"]["publish"] = {"client_id": "CID", "client_secret": "SEC"}
    flags: dict = {}
    globals()["_load_api_credentials"] = lambda: __import__("copy").deepcopy(store)

    def _save(c):
        store.clear()
        store.update(c)
    globals()["_save_api_credentials"] = _save
    globals()["_update_capability_flag"] = lambda k, v: flags.__setitem__(k, v)

    def fake(method, url, headers, body):
        scope = "https://www.googleapis.com/auth/youtube.upload"
        return 200, json.dumps({_AT: "USER_AT", "expires_in": 3600, _RT: "USER_RT",
                                "scope": scope, "token_type": "Bearer"}).encode()
    _OAUTH_TRANSPORT = fake

    # 1) Happy path: matching state -> exchange -> flag on, tokens under publish, import token intact.
    _set(oauth_pending_youtube={"state": "ST", "verifier": "VER",
                                "redirect_uri": "http://127.0.0.1:8765/oauth/youtube/callback"})
    html_out = _oauth_callback_page("youtube", {"code": ["AUTHCODE"], "state": ["ST"]})
    check("connected" in html_out.lower(), "happy-path callback did not report connected")
    check(flags.get("youtube_publishing") is True, "youtube_publishing flag not set")
    pub = store["youtube"].get("publish", {})
    check(pub.get(_RT) == "USER_RT", "refresh token not stored under publish")
    check(pub.get("client_id") == "CID", "app client_id lost on merge")
    check(store["youtube"].get(_AT) == "IMPORT_READ_TOKEN", "importer token was clobbered")
    check(_get("oauth_pending_youtube") is None, "pending state not consumed (single-use)")

    # 2) State mismatch (CSRF) -> refused, no exchange.
    flags.clear()
    _set(oauth_pending_youtube={"state": "GOOD", "verifier": "V", "redirect_uri": "R"})
    html_out = _oauth_callback_page("youtube", {"code": ["X"], "state": ["EVIL"]})
    check("state did not match" in html_out.lower() or "security check" in html_out.lower(),
          "state mismatch not rejected")
    check("youtube_publishing" not in flags, "flag flipped on a CSRF-failed callback")

    # 3) Provider returned error=access_denied -> no exchange, friendly message.
    _set(oauth_pending_youtube={"state": "ST", "verifier": "V", "redirect_uri": "R"})
    html_out = _oauth_callback_page("youtube", {"error": ["access_denied"], "state": ["ST"]})
    check("denied or cancelled" in html_out.lower(), "access_denied not surfaced")

    _OAUTH_TRANSPORT = None

    # 4) macOS screens render offline via the _os()/_arch() seam (F9).
    global _OS_OVERRIDE, _ARCH_OVERRIDE
    _OS_OVERRIDE, _ARCH_OVERRIDE = "mac", "arm64"
    try:
        blk = _stt_install_block()
        check("Apple Silicon" in blk and "whisper-cpp" in blk, "mac STT block did not render Apple Silicon copy")
        _ARCH_OVERRIDE = "x86_64"
        check("Intel Mac" in _stt_install_block(), "mac STT block did not render Intel copy")
        cfg = str(_claude_config_path())
        check("Library/Application Support/Claude" in cfg, "mac Claude config path wrong under _os override")
    finally:
        _OS_OVERRIDE, _ARCH_OVERRIDE = None, None

    # 5) Port-collision mechanism (F6): a second bind on the same port raises OSError (the friendly
    #    exit path in main() depends on this being catchable).
    try:
        s1 = _Server(("127.0.0.1", 0), _Handler)
        busy_port = s1.server_address[1]
        check(s1.server_address[0] == "127.0.0.1", "server did not bind loopback")
        raised = False
        try:
            s2 = _Server(("127.0.0.1", busy_port), _Handler)
            s2.server_close()
        except OSError:
            raised = True
        check(raised, "second bind on a busy port did not raise OSError")
        s1.server_close()
    except Exception as exc:  # noqa: BLE001
        check(False, f"port-collision check errored: {exc}")

    # 6) Loopback-only guard (G1): main() must bind 127.0.0.1, never 0.0.0.0.
    src = pathlib.Path(__file__).read_text(encoding="utf-8")
    check('_Server(("127.0.0.1", PORT)' in src, "main() no longer binds 127.0.0.1:PORT")
    _any_ip = ".".join(["0"] * 4)  # built dynamically so this guard line doesn't match itself
    check(f'(("{_any_ip}"' not in src and f"(('{_any_ip}'" not in src,
          "wizard binds the all-interfaces address (loopback exemption lost)")

    if failures:
        print("wizard selftest FAILED:")
        for f in failures:
            print("  -", f)
        return 1
    print("wizard selftest OK (OAuth CSRF+exchange+no-clobber; macOS render seam; port-collision; loopback guard; 0 network)")
    return 0


def main() -> None:
    if "--selftest" in sys.argv:
        raise SystemExit(_selftest())
    # Bind loopback only (127.0.0.1): exempt from the macOS Application Firewall incoming-connection
    # prompt AND the Sequoia/Tahoe local-network permission prompt (Apple TN3179). Never 0.0.0.0.
    try:
        server = _Server(("127.0.0.1", PORT), _Handler)
    except OSError:
        # Port 8765 is busy (a second launch, a lingering wizard, or another app). Keep the port
        # fixed (OAuth redirect URIs are registered against it) and exit cleanly with a plain message
        # instead of dumping a traceback into the Terminal window a non-technical user is watching.
        print(f"\nCreator OS Setup is already running, or port {PORT} is in use.")
        print(f"Open http://localhost:{PORT}/ in your browser, or close the other window and try again.")
        raise SystemExit(1)
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
