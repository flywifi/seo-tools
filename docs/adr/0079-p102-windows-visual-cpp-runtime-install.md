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
loading, and (on Windows) not loading with `msvcp140.dll` missing from `%SystemRoot%\System32`
(`probe_faster_whisper`, `vc_runtime_missing`). Python for Windows ships the other two runtime
libraries beside `python.exe`, so `msvcp140.dll` is the one that decides the load
(`transcribe.VC_RUNTIME_DECISIVE`). For that state it names the runtime as a machine-wide install,
with the wizard's button and the manual routes, instead of asking for `--install-deps` again.
`transcribe run` (`select_backend`) says the same.

## Decision 2: the wizard runs Microsoft's installer when the person asks

The wizard's Check my setup screen shows an offer only on Windows on x64 or ARM64 when the check
reports faster-whisper installed, not loading, and `msvcp140.dll` missing. The offer's heading
says "machine-wide: affects the whole computer"; it links Microsoft's license terms, says Windows
asks for administrator permission, keeps the manual route (Microsoft's download, or
`winget install --exact --id Microsoft.VCRedist.2015+.x64`, machine-wide), and has a confirmation
box. `POST /api/install-vc-runtime` refuses without the ticked box and refuses when a fresh check
does not offer the install; otherwise it starts a background job (`transcribe.install_vc_runtime`):

1. Download Microsoft's machine-wide installer, `https://aka.ms/vc14/vc_redist.x64.exe` (Microsoft's
   permalink; the x64 package "contains both ARM64 and X64 binaries"), into a new temporary folder.
2. Ask Windows PowerShell for the file's Authenticode status, its signer, and the root of its
   certificate chain (reported only when the chain built, or failed on time flags alone). The file
   runs only when the status is `Valid`, the signer has one organization and it is `Microsoft
   Corporation`, and the root is "Microsoft Root Certificate Authority 2011" with thumbprint
   `8F43288AD272F3103B6FB1428485EA3014C0BCFE`.
3. Run it with `/install /passive /norestart`, the command Microsoft Learn documents, plus `/log`
   into the temporary folder. Windows shows its own administrator prompt: the installer's manifest,
   read from the downloaded file on 2026-10-10, asks for `asInvoker`, so it elevates itself.
4. Read the exit code: 0 installed, 3010 installed with a restart pending, 1638 a newer version
   already present (or, with `msvcp140.dll` still missing, a registration that needs repair), 1602
   and 1223 cancelled, 1307, 1925 and 5 read as needing an administrator, anything else a failure
   shown with its code.
5. Delete the temporary folder when the job returns or raises, and show the check again in a new
   process. While the job runs, the wizard's quit link waits, so the folder is not left behind; a
   process killed mid-install leaves it.

## Consequences

- Creator OS can now start one install outside the home folder. It is labeled, confirmed by the
  person, gated on Microsoft's signature, and listed in the exceptions register of
  `docs/INSTALL-SCOPE.md` and in `CLAUDE.md`.
- Drift invariant 59 gains a `windows-installer` branch for machine-wide Windows installs, read in
  any letter case: `winget install` or `upgrade` (not with `--scope user`), Chocolatey, an `msiexec`
  install, an installer `.exe` run with an install or silent switch, the `vc_redist` package by name,
  and `wsl --install`. Those instructions need the label too.
- What is tested: the download, the signature verdict, the run, the exit codes and the folder
  deletion run on every system with stand-ins for Windows; the PowerShell call runs for real only on
  Windows, where the selftest checks that an unsigned file is refused and that Windows PowerShell's
  own executable reads as Valid from Microsoft Corporation. The tests do not run Microsoft's
  installer itself.
- If Microsoft changes the permalink's signer or root, the check refuses and deletes the file, and
  the manual route stays on the screen. Updating the pinned root is a code change.
- The install is not a command-line verb; an agent asked to fix transcription points the person to
  the wizard's screen or the manual route.
- On an account without administrator rights, Windows asks for an administrator's password; exit
  codes 1307, 1925 and 5 show a message that an administrator is needed.

```sources
[
  {"id": "ms-vc-redist-latest", "name": "Microsoft Visual C++ Redistributable latest supported downloads (Microsoft Learn)", "url": "https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist", "category": "software-dependency", "tier": "T1"},
  {"id": "ms-vc-redist-troubleshoot", "name": "Troubleshoot Visual C++ Redistributable installation problems (Microsoft Learn)", "url": "https://learn.microsoft.com/en-us/cpp/windows/troubleshoot-vc-redistributable-installation-issues", "category": "software-dependency", "tier": "T1"},
  {"id": "ms-vc-redist-command-line", "name": "Redistribute Visual C++ files, command-line options (Microsoft Learn)", "url": "https://learn.microsoft.com/en-us/cpp/windows/redistributing-visual-cpp-files", "category": "software-dependency", "tier": "T1"},
  {"id": "ms-windows-installer-errors", "name": "Windows Installer error messages (Microsoft Learn)", "url": "https://learn.microsoft.com/en-us/windows/win32/msi/windows-installer-error-messages", "category": "software-dependency", "tier": "T1"}
]
```
