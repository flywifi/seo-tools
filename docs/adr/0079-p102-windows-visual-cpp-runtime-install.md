# ADR 0079 — On Windows the setup wizard installs Microsoft's Visual C++ runtime on request, after a signature check

- Status: accepted
- Date: 2026-10-10
- Phase: P102

## Context

Local transcription's default engine, faster-whisper, runs on ctranslate2. On Windows,
`ctranslate2.dll` imports Microsoft's Visual C++ runtime libraries (`msvcp140.dll`,
`vcruntime140.dll`, `vcruntime140_1.dll`). A fresh Windows can lack them, pip does not install
system libraries, and importing faster-whisper then raises `FileNotFoundError` ("Could not find
module ... ctranslate2.dll (or one of its dependencies)"). Microsoft installs the runtime with the
Visual C++ Redistributable, which is machine-wide: it installs for the whole computer and needs
administrator rights.

Creator OS installs into the user's home folder by default (ADR 0065, `docs/INSTALL-SCOPE.md`), and
before this decision none of its tools started a machine-wide installer. Microsoft Learn's troubleshooting
page says: "Never install a Visual C++ Redistributable installer that wasn't downloaded from a
Microsoft site. Never install a Visual C++ Redistributable installer that Microsoft didn't sign."

## Decision 1: the readiness check names the runtime

`transcribe.doctor` tells three states apart: faster-whisper not installed, installed but not
loading, and (on Windows) not loading with runtime libraries missing from `%SystemRoot%\System32`
(`probe_faster_whisper`, `vc_runtime_missing`). For the last it names the runtime as a machine-wide
install, with the wizard's button and the manual routes, instead of asking for `--install-deps`
again.

## Decision 2: the wizard runs Microsoft's installer when the person asks

The wizard's Check my setup screen shows an offer only on Windows on x64 or ARM64 when the check
reports faster-whisper installed, not loading, and runtime libraries missing. The offer's heading
says "machine-wide: affects the whole computer"; it links Microsoft's license terms, says Windows
asks for administrator permission, keeps the manual route (Microsoft's download, or
`winget install --exact --id Microsoft.VCRedist.2015+.x64`, machine-wide), and has a confirmation
box. `POST /api/install-vc-runtime` refuses without the ticked box and refuses when a fresh check
does not offer the install; otherwise it starts a background job (`transcribe.install_vc_runtime`):

1. Download Microsoft's machine-wide installer, `https://aka.ms/vc14/vc_redist.x64.exe` (Microsoft's
   permalink; the x64 package "contains both ARM64 and X64 binaries"), into a new temporary folder.
2. Ask Windows PowerShell for the file's Authenticode status, its signer, and the root of its
   certificate chain. The file runs only when the status is `Valid`, the signer's organization is
   `Microsoft Corporation`, and the root is "Microsoft Root Certificate Authority 2011" with
   thumbprint `8F43288AD272F3103B6FB1428485EA3014C0BCFE`.
3. Run it with `/install /passive /norestart`, the command Microsoft Learn documents. Windows shows
   its own administrator prompt; the installer's manifest asks for `asInvoker`, so it elevates
   itself.
4. Read the exit code: 0 installed, 3010 installed with a restart pending, 1638 a newer version
   already present, 1602 and 1223 cancelled, 1307, 1925 and 5 an account without administrator
   rights, anything else a failure shown with its code.
5. Delete the temporary folder in every outcome, and show the check again in a new process.

## Consequences

- Creator OS can now start one install outside the home folder. It is labeled, confirmed by the
  person, gated on Microsoft's signature, and listed in the exceptions register of
  `docs/INSTALL-SCOPE.md` and in `CLAUDE.md`.
- Drift invariant 59 gains a `windows-installer` branch for machine-wide Windows installs
  (`winget install`, an `msiexec` install, an installer `.exe` run with an install switch, and the
  `vc_redist` package by name), so those instructions need the label too.
- If Microsoft changes the permalink's signer or root, the check refuses and deletes the file, and
  the manual route stays on the screen. Updating the pinned root is a code change.
- The install is not a command-line verb; an agent asked to fix transcription points the person to
  the wizard's screen or the manual route.
- On an account without administrator rights, Windows asks for an administrator's password. Where
  it cannot ask (User Account Control off, as in Windows Sandbox), the installer exits with 1307 and
  the screen says an administrator is needed.

```sources
[
  {"id": "ms-vc-redist-latest", "name": "Microsoft Visual C++ Redistributable latest supported downloads (Microsoft Learn)", "url": "https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist", "category": "software-dependency", "tier": "T1"},
  {"id": "ms-vc-redist-troubleshoot", "name": "Troubleshoot Visual C++ Redistributable installation problems (Microsoft Learn)", "url": "https://learn.microsoft.com/en-us/cpp/windows/troubleshoot-vc-redistributable-installation-issues", "category": "software-dependency", "tier": "T1"},
  {"id": "ms-vc-redist-command-line", "name": "Redistribute Visual C++ files, command-line options (Microsoft Learn)", "url": "https://learn.microsoft.com/en-us/cpp/windows/redistributing-visual-cpp-files", "category": "software-dependency", "tier": "T1"},
  {"id": "ms-windows-installer-errors", "name": "Windows Installer error messages (Microsoft Learn)", "url": "https://learn.microsoft.com/en-us/windows/win32/msi/windows-installer-error-messages", "category": "software-dependency", "tier": "T1"}
]
```
