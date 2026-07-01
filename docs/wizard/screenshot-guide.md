# Screenshot Guide

Each wizard screen, what it shows, and which file to capture it as.

---

## Screen 1 -- Welcome (`/`)

**What it shows:** Creator OS logo text, brief tagline, OS auto-detected and shown in small text
below the heading, two large buttons side by side: "I use Claude at claude.ai" and "I use Claude
Desktop on this computer," and a third smaller link "Just check what's connected."

**Capture variants:**
- `wizard-welcome-mac.png` -- the detected OS line should read "Mac detected"
- `wizard-welcome-windows.png` -- "Windows detected"
- `wizard-welcome-linux.png` -- "Linux detected"

**Key detail to show:** the OS detection line beneath the heading -- this demonstrates that the
wizard knows where to write config files without asking.

---

## Screen 2 -- claude.ai path (`/claudeai`)

**What it shows:** A step-by-step guide (numbered, large type) explaining how to connect Google
Workspace in claude.ai Settings > Integrations. No form, no inputs -- just instructions with a
note that Microsoft is not yet available on claude.ai.

**Capture variants:**
- `wizard-claudeai.png` (one capture, platform-independent)

**Key detail to show:** the "No downloads, no terminal needed" confirmation at the top.

---

## Screen 3 -- Claude Desktop path (`/desktop`)

**What it shows:** Two service tiles side by side with checkboxes -- Google Workspace and
Microsoft 365 -- each with a short description of what it connects (Gmail/Calendar/Drive and
Outlook/Calendar/Excel/OneDrive). A "Continue" button at the bottom.

**Capture variants:**
- `wizard-desktop.png` (one capture, platform-independent)

**Key detail to show:** the friendly service descriptions in plain English, not technical terms.

---

## Screen 4 -- Google credentials (`/google`)

**What it shows:** A 6-step numbered guide for getting a Google Client ID and Secret from
Google Cloud Console, with a credentials form at the bottom (two text inputs: Client ID,
Client Secret) and a "Connect Google" button.

**Capture variants:**
- `wizard-google.png`
- `wizard-google-submitting.png` -- "Connecting..." state (button disabled, spinner shown)

**Key detail to show:** the instructional steps above the form -- emphasize that the wizard
walks you through what would otherwise be an opaque developer task.

---

## Screen 5 -- Google done (`/google-done`)

**What it shows:** Green checkmark, "Google Workspace Connected" heading, a bullet list of what
is now accessible (Gmail, Calendar, Drive/Docs/Sheets), and a "Continue to Microsoft" button
plus a "Skip" link.

**Capture variants:**
- `wizard-google-done.png`

**Key detail to show:** the green checkmark and the plain-English capability summary.

---

## Screen 6 -- Microsoft connection (`/microsoft`)

**What it shows:** Single large "Connect Microsoft 365" button with a short description:
"Outlook, Calendar, Excel, and OneDrive." Below the button, small text: "Requires Node.js 20+.
The wizard will check." A note explains the device code flow: "You will visit a Microsoft URL
and enter a short code -- no password is shared with Creator OS."

**Capture variants:**
- `wizard-microsoft.png`
- `wizard-microsoft-submitting.png` -- "Adding to config..." state

---

## Screen 7 -- Node.js missing (`/node-missing`)

**What it shows:** A yellow warning box: "Node.js 20 or later is required for Microsoft 365."
Below it, OS-specific install instructions:
- Mac: `brew install node` with a "Copy command" button
- Windows: "Download from nodejs.org" with a link
- Linux: distro-appropriate command with a "Copy command" button

A "Check again" button and a "Skip Microsoft for now" link.

**Capture variants:**
- `wizard-microsoft-node-missing-mac.png`
- `wizard-microsoft-node-missing-windows.png`
- `wizard-microsoft-node-missing-linux.png`

**Key detail to show:** the copy button and the plain-language explanation of why Node.js is
needed -- avoid making this feel like a developer error page.

---

## Screen 8 -- Microsoft done (`/microsoft-done`)

**What it shows:** Green checkmark, "Microsoft 365 Added" heading, note that the first time
you use Claude Desktop a one-time sign-in prompt will appear (device code flow explained in
one sentence), and a "Continue" button.

**Capture variants:**
- `wizard-microsoft-done.png`

---

## Screen 9 -- Done (`/done`)

**What it shows:** "You are all set." heading. Two sections:
- "What to do now" -- restart Claude Desktop (large, prominent)
- "What you can try" -- 4 to 6 example prompts in a card grid ("Read my brand emails from
  this week," "What's on my content calendar?", "Import my analytics from Sheets," etc.)

A "Close this window" button at the bottom.

**Capture variants:**
- `wizard-done-google-only.png` -- only Google connected
- `wizard-done-microsoft-only.png` -- only Microsoft connected
- `wizard-done-both.png` -- both connected

**Key detail to show:** the example prompts -- these translate abstract "connected" state into
concrete things Alex can immediately try. This is the emotional payoff of the wizard flow.

---

## GIF guide

### `wizard-full-mac.gif`
Full flow from terminal launch through done screen on Mac. Include:
1. `python3 tools/wizard.py` in terminal, browser opening
2. Welcome screen (OS detected as Mac)
3. Clicking "Claude Desktop"
4. Selecting both Google and Microsoft
5. Google credentials form + connecting
6. Google done screen
7. Microsoft connection
8. Microsoft done screen
9. Done screen with example prompts

Target length: 60 to 90 seconds playback at 1x speed; export as GIF at 10 fps for file size.

### `wizard-google-connect.gif`
Just the Google credentials form through the done checkmark. 15 to 20 seconds.

### `wizard-microsoft-connect.gif`
Just the Microsoft button through the done checkmark, including the device code explanation
note. 10 to 15 seconds.
