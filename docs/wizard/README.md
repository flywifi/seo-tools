# Wizard Screenshots and Demo Assets

This directory holds screenshots and animated GIFs for the Creator OS setup wizard
(`tools/wizard.py`). These assets are used in `docs/WIZARD.md` and any tutorial content
about the setup flow.

## File naming convention

Screenshots are named by screen, OS variant (where relevant), and state:

- `wizard-welcome-mac.png` -- welcome screen on macOS
- `wizard-welcome-windows.png` -- welcome screen on Windows
- `wizard-claudeai.png` -- claude.ai path (same on all platforms)
- `wizard-desktop.png` -- Claude Desktop path (platform picker)
- `wizard-google.png` -- Google credentials form
- `wizard-google-done.png` -- Google connected (green checkmark)
- `wizard-microsoft.png` -- Microsoft connection screen
- `wizard-microsoft-node-missing.png` -- Node.js not found warning
- `wizard-microsoft-done.png` -- Microsoft connected (green checkmark)
- `wizard-done.png` -- done screen with example prompts

GIFs (full flow demos):

- `wizard-full-mac.gif` -- complete Mac flow: welcome to done
- `wizard-google-connect.gif` -- just the Google OAuth flow
- `wizard-microsoft-connect.gif` -- just the Microsoft device code flow

## How to capture

Run `python3 tools/wizard.py` on the target platform and take screenshots at each screen.
For GIFs, use QuickTime (Mac), Xbox Game Bar (Windows), or Peek (Linux) to record the
browser window.

Target browser window size: 1200 x 900 px (the wizard is responsive but captures best at
this size). The wizard colors are warm/moody to match the brand: off-white background
(#faf7f4), burgundy progress bar (#7c2d2d), dark text (#2c1810).

Actual image files are created during QA on a real Mac and Windows machine and added here
before the first public release. Until then, this directory holds this README only.
