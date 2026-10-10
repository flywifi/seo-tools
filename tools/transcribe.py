#!/usr/bin/env python3
"""transcribe.py -- OS/backend-aware LOCAL speech-to-text runner (P45 completion layer).

The missing bridge between the media the creator already downloaded and the transcript that no
platform will hand back (off-YouTube: none; YouTube ASR: undownloadable 403). Runs entirely
on-device: zero cloud, zero tokens, no audio bytes leave the machine (shared/transcription-engine.md).

It never fabricates. If no STT backend is installed it returns the engine's `run_local_stt` gap with
the OS-correct install command, never a fake transcript. Backend selection follows the routing matrix
in the P45 plan (Appendix / section 6b):

  Apple Silicon (Darwin + arm64) -> whisper.cpp (Metal) first, faster-whisper (CPU) fallback
  Intel Mac                       -> whisper.cpp (CPU/AVX) first, faster-whisper (CPU int8) fallback
  Windows/Linux + NVIDIA          -> faster-whisper (CUDA)
  Windows/Linux CPU               -> faster-whisper (CPU int8) first, whisper.cpp fallback

openai-whisper is never selected by default (PyTorch MPS is unstable on Apple hardware).

Usage:
  python3 tools/transcribe.py status
  python3 tools/transcribe.py run <media> [--model small] [--out-dir DIR] [--initial-prompt TEXT]
  python3 tools/transcribe.py --selftest
"""
import argparse
import hashlib
import json
import os
import platform
import shutil
import ssl
import subprocess
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = Path(os.environ.get("CREATOR_OS_ROOT", str(HERE.parent)))
sys.path.insert(0, str(HERE.parent / "shared" / "docintel"))
sys.path.insert(0, str(HERE / "videoedit"))
import transcripts as _t  # noqa: E402
import mediaprobe as _mp  # noqa: E402

SUBPROCESS_TIMEOUT = 3600  # a long video can take a while; STT is the bottleneck, not the wall clock.
CA_BUNDLE = os.environ.get("REQUESTS_CA_BUNDLE") or "/root/.ccr/ca-bundle.crt"
MODEL_ALLOWLIST = ROOT / "canonical-sources" / "whisper-models.json"

# whisper.cpp's CLI has been renamed across versions; probe all three.
_WHISPER_CPP_BINS = ("whisper-cli", "whisper-cpp", "main")

# Niche vocabulary that generic ASR mis-hears; seeds faster-whisper/whisper.cpp initial_prompt.
# Kept here as a floor; the caller layers in the video's own tags/title + shared/brand-engine.md.
_NICHE_SEED = ("armoire", "patina", "wainscoting", "decoupage", "sconcing", "vignette", "tartan")


# ── backend detection + selection (pure where it matters; the selftest pins select_backend) ──

# On Windows, faster-whisper's ctranslate2 loads these Microsoft Visual C++ runtime libraries, which a
# fresh Windows lacks and pip cannot install (P102). Their installer is machine-wide (it affects the
# whole computer), so Creator OS runs it from the setup wizard on request. Microsoft's x64 package
# also carries the ARM64 libraries ("The X64 Redistributable package contains both ARM64 and X64
# binaries", Microsoft Learn, "Microsoft Visual C++ Redistributable latest supported downloads"), so
# it serves both machines.
VC_RUNTIME_DLLS = ("msvcp140.dll", "vcruntime140.dll", "vcruntime140_1.dll")
VC_RUNTIME_URL = "https://aka.ms/vc14/vc_redist.x64.exe"
# The one of those that decides the load: Python for Windows ships vcruntime140.dll and
# vcruntime140_1.dll beside python.exe, and Windows finds them there, but not msvcp140.dll. So a
# computer with only an older runtime (vcruntime140_1.dll absent from System32) still loads
# faster-whisper, and the runtime is named only when msvcp140.dll is absent.
VC_RUNTIME_DECISIVE = "msvcp140.dll"


def probe_faster_whisper(find_spec=None, importer=None):
    """{"installed", "loads", "error"} for faster-whisper in this interpreter: installed when importlib
    finds the package without importing it, loads when importing it succeeds, and error the first line
    of the exception when it does not (on Windows a missing Visual C++ runtime raises FileNotFoundError
    from ctranslate2's DLL). Never raises."""
    import importlib
    import importlib.util
    find_spec = importlib.util.find_spec if find_spec is None else find_spec
    importer = importlib.import_module if importer is None else importer
    try:
        installed = find_spec("faster_whisper") is not None
    except (ImportError, ValueError):
        installed = False
    if not installed:
        return {"installed": False, "loads": False, "error": ""}
    try:
        importer("faster_whisper")
    except Exception as exc:  # noqa: BLE001 -- any failure to load is reported, never raised
        return {"installed": True, "loads": False,
                "error": (f"{type(exc).__name__}: {exc}".splitlines() or [""])[0][:300]}
    return {"installed": True, "loads": True, "error": ""}


def vc_runtime_missing(system_root=None, exists=None):
    """The VC_RUNTIME_DLLS absent from %SystemRoot%\\System32. Callers ask on Windows only;
    system_root and exists stand in for the system's in the selftest."""
    import ntpath
    root = system_root or os.environ.get("SystemRoot") or "C:\\Windows"
    exists = os.path.exists if exists is None else exists
    return [d for d in VC_RUNTIME_DLLS if not exists(ntpath.join(root, "System32", d))]


def vc_runtime_remedy():
    """What to do on Windows when faster-whisper is installed but the Visual C++ runtime is missing."""
    return ("Install the Microsoft Visual C++ Redistributable (machine-wide: affects the whole computer). "
            "Use the Install button on the setup wizard's Check my setup screen, or install it yourself "
            f"from Microsoft ({VC_RUNTIME_URL}) or with: winget install --exact --id Microsoft.VCRedist.2015+.x64")


# The install the setup wizard runs on request (P102, ADR 0079). It is machine-wide (affects the whole
# computer), so the wizard asks first. Microsoft Learn's troubleshooting page: "Never install a Visual
# C++ Redistributable installer that wasn't downloaded from a Microsoft site. Never install a Visual C++
# Redistributable installer that Microsoft didn't sign." So the file comes from VC_RUNTIME_URL, and it
# runs after Windows reports a Valid Authenticode signature whose signer's organization is Microsoft
# Corporation and whose chain ends at Microsoft's code-signing root, pinned by thumbprint.
VC_RUNTIME_LICENSE_URL = "https://aka.ms/VCRedistLicense"
VC_RUNTIME_SIGNER_ORG = "Microsoft Corporation"
VC_RUNTIME_ROOT_CN = "Microsoft Root Certificate Authority 2011"
VC_RUNTIME_ROOT_THUMBPRINT = "8F43288AD272F3103B6FB1428485EA3014C0BCFE"
# Microsoft Learn, "Redistribute Visual C++ files": /passive "shows a progress bar ... but doesn't
# otherwise require user interaction"; /norestart "suppresses any attempts to restart"; and "/log
# filename.txt to log to a specific file" (install_vc_runtime puts it in its temporary folder, so it is
# deleted with the installer instead of staying in %TEMP%).
VC_RUNTIME_ARGS = ("/install", "/passive", "/norestart")
VC_RUNTIME_ARCHES = ("amd64", "x86_64", "arm64", "aarch64")
VC_RUNTIME_TIMEOUT = 1800
# Windows system error codes the installer returns: 3010 ERROR_SUCCESS_REBOOT_REQUIRED, 1638
# ERROR_PRODUCT_VERSION (another version is already installed), 1602 ERROR_INSTALL_USEREXIT and
# 1223 ERROR_CANCELLED (the person declined). Read as needing an administrator: 1307
# ERROR_INVALID_OWNER (the installer could not elevate), 1925 (Windows Installer: "You do not have
# sufficient privileges to complete this installation for all users of the machine") and 5
# ERROR_ACCESS_DENIED (Microsoft Learn's troubleshooting page also names security software and group
# policy for it).
VC_RUNTIME_EXIT = {
    0: (True, "installed", "The Microsoft Visual C++ Redistributable is installed."),
    3010: (True, "restart", "The Microsoft Visual C++ Redistributable is installed. Restart Windows "
                            "when convenient to finish it."),
    1638: (True, "newer", "A newer Microsoft Visual C++ Redistributable is already installed, so the "
                          "installer changed nothing."),
    1602: (False, "cancelled", "The install was cancelled, so nothing was installed."),
    1223: (False, "cancelled", "The install was cancelled at the Windows administrator prompt, so nothing "
                               "was installed."),
    1307: (False, "needs_admin", "Installing the Visual C++ runtime needs an administrator of this computer "
                                 "(exit code 1307). Ask whoever manages it, or use the manual route on this "
                                 "screen."),
    1925: (False, "needs_admin", "Installing the Visual C++ runtime needs an administrator of this computer "
                                 "(exit code 1925). Ask whoever manages it, or use the manual route on this "
                                 "screen."),
    5: (False, "needs_admin", "Windows denied the install (exit code 5, access denied). It needs an "
                              "administrator of this computer, and security software or a work policy can "
                              "also block it. Ask whoever manages it, or use the manual route on this screen."),
}

# Windows PowerShell: the file's Authenticode verdict, its signer, and the root its chain ends at. The
# certificates inside the signature go into the chain's extra store, so the chain builds without a
# download; revocation is not checked here because Get-AuthenticodeSignature's Valid already covers trust.
# The root is reported only from a chain that built, or one whose only faults are time flags (the
# signing certificate expires before the timestamped signature does); otherwise it is left empty and
# vc_signature_verdict refuses. Output is UTF-8, so a localized error message decodes.
_VC_SIGNATURE_PS = r"""
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$f = $env:CREATOR_OS_VC_FILE
$s = Get-AuthenticodeSignature -LiteralPath $f
$c = $s.SignerCertificate
$root = $null
if ($c) {
  $chain = New-Object System.Security.Cryptography.X509Certificates.X509Chain
  $chain.ChainPolicy.RevocationMode = 'NoCheck'
  $extra = New-Object System.Security.Cryptography.X509Certificates.X509Certificate2Collection
  try { $extra.Import($f) } catch { }
  [void]$chain.ChainPolicy.ExtraStore.AddRange($extra)
  $built = $chain.Build($c)
  $flags = @($chain.ChainStatus | ForEach-Object { [string]$_.Status })
  $other = @($flags | Where-Object { $_ -notin @('NotTimeValid', 'NotTimeNested') })
  $n = $chain.ChainElements.Count
  if (($built -or $other.Count -eq 0) -and $n -gt 0) { $root = $chain.ChainElements[$n - 1].Certificate }
}
$signer = ''
if ($c) { $signer = $c.Subject }
$rootThumb = ''
$rootSubject = ''
if ($root) { $rootThumb = $root.Thumbprint; $rootSubject = $root.Subject }
$chainStatus = ''
if ($c) { $chainStatus = ($flags -join ',') }
[pscustomobject]@{ status = [string]$s.Status; signer = $signer; root_thumbprint = $rootThumb; root_subject = $rootSubject; chain_status = $chainStatus } | ConvertTo-Json -Compress
"""


def _dn_values(subject, key):
    """The values of attribute `key` (O, CN) in an X.500 subject such as
    'CN=Microsoft Corporation, O=Microsoft Corporation, L=Redmond, S=Washington, C=US'. The subject is
    split at the commas outside double quotes, so a quoted value (CN="x, O=y") carries no attribute."""
    parts, cur, quoted = [], "", False
    for ch in str(subject or ""):
        if ch == '"':
            quoted = not quoted
        if ch == "," and not quoted:
            parts.append(cur)
            cur = ""
        else:
            cur += ch
    parts.append(cur)
    out = []
    for part in parts:
        name, sep, value = part.strip().partition("=")
        if sep and name.strip() == key:
            value = value.strip()
            out.append(value[1:-1] if len(value) >= 2 and value[0] == value[-1] == '"' else value)
    return out


def vc_signature_verdict(info):
    """(ok, reason) for the facts _VC_SIGNATURE_PS reports: ok when the status is Valid, the signer
    has one organization (O) and it is Microsoft Corporation, and the chain's root has the pinned
    thumbprint and one common name (CN), Microsoft Root Certificate Authority 2011. Anything else, a
    missing field or an error included, is refused."""
    if not isinstance(info, dict) or info.get("error"):
        why = info.get("error") if isinstance(info, dict) else None
        return False, f"Windows could not check the signature ({why or 'no result'})"
    status = str(info.get("status") or "")
    if status != "Valid":
        return False, f"Windows reports the signature as {status or 'missing'}, not Valid"
    if _dn_values(info.get("signer"), "O") != [VC_RUNTIME_SIGNER_ORG]:
        return False, f"it is signed by {info.get('signer') or 'nobody'}, not Microsoft Corporation"
    if str(info.get("root_thumbprint") or "").upper() != VC_RUNTIME_ROOT_THUMBPRINT:
        return False, (f"its signature chains to a root whose thumbprint "
                       f"({info.get('root_thumbprint') or 'none reported'}) is not {VC_RUNTIME_ROOT_CN}'s")
    if _dn_values(info.get("root_subject"), "CN") != [VC_RUNTIME_ROOT_CN]:
        return False, (f"its signature chains to {info.get('root_subject') or 'an unknown root'}, not "
                       f"{VC_RUNTIME_ROOT_CN}")
    return True, f"signed by Microsoft Corporation, chained to {VC_RUNTIME_ROOT_CN}"


def vc_signature_info(path, run=None, system_root=None):
    """The signature facts for `path` from Windows PowerShell (by its full path under %SystemRoot%), as
    a dict, or {"error": ...}. The file path travels in an environment variable and the script as
    -EncodedCommand, so neither is parsed by a shell. `run` stands in for subprocess.run."""
    import base64
    import ntpath
    run = subprocess.run if run is None else run
    root = system_root or os.environ.get("SystemRoot") or "C:\\Windows"
    ps = ntpath.join(root, "System32", "WindowsPowerShell", "v1.0", "powershell.exe")
    script = base64.b64encode(_VC_SIGNATURE_PS.encode("utf-16-le")).decode("ascii")
    # PSModulePath is left out so Windows PowerShell builds its own: one inherited from PowerShell 7
    # can stop it loading the module that provides Get-AuthenticodeSignature (PowerShell issue 18530).
    env = {k: v for k, v in os.environ.items() if k.upper() != "PSMODULEPATH"}
    env["CREATOR_OS_VC_FILE"] = str(path)
    try:
        r = run([ps, "-NoProfile", "-NonInteractive", "-EncodedCommand", script],
                capture_output=True, encoding="utf-8", errors="replace", timeout=120, env=env)
    except (OSError, subprocess.SubprocessError) as exc:
        return {"error": f"{type(exc).__name__}: {str(exc)[:160]}"}
    try:
        info = json.loads((r.stdout or "").strip().splitlines()[-1])
    except (IndexError, ValueError):
        return {"error": (r.stderr or r.stdout or f"exit code {r.returncode}").strip()[:200]}
    return info if isinstance(info, dict) else {"error": "the signature check printed no object"}


def vc_exit_meaning(code):
    """(ok, status, message) for the installer's exit code."""
    if code in VC_RUNTIME_EXIT:
        return VC_RUNTIME_EXIT[code]
    return False, "failed", (f"The installer stopped with exit code {code}. You can install it yourself "
                             f"from Microsoft: {VC_RUNTIME_URL}")


def _run_vc_installer(argv):
    """The installer's exit code; it raises Windows' administrator prompt itself (its manifest asks
    for asInvoker)."""
    return subprocess.run(list(argv), timeout=VC_RUNTIME_TIMEOUT).returncode


def install_vc_runtime(os_name=None, arch=None, download=None, verify=None, run=None, mkdtemp=None,
                       rmtree=None, missing=None):
    """Download Microsoft's x64 Visual C++ Redistributable into a new temporary folder, run it with
    VC_RUNTIME_ARGS and its log in that folder once vc_signature_verdict accepts its signature, and
    delete the folder when this function returns or raises (a process killed mid-install leaves it).
    Windows on x64 or ARM64 only (the x64 package carries the ARM64 libraries). Returns {"ok",
    "status", "message"} plus "exit_code" when the installer ran and "note" when the folder could not
    be deleted. Exit code 1638 (a newer version registered) with msvcp140.dll still absent reads as
    repair_needed. Each step is injectable: download(url, dest) -> error or None, verify(path) ->
    info dict, run(argv) -> exit code, missing() -> the absent runtime DLLs. The setup wizard calls
    this after the person ticks its confirmation box; it is not a command-line verb."""
    import tempfile
    os_name = (os_name if os_name is not None else sys.platform).lower()
    arch = (arch if arch is not None else platform.machine()).lower()
    if not os_name.startswith("win") or arch not in VC_RUNTIME_ARCHES:
        return {"ok": False, "status": "unsupported",
                "message": "The Microsoft Visual C++ Redistributable install runs on Windows on x64 or ARM64."}
    download = _stream_download if download is None else download
    verify = vc_signature_info if verify is None else verify
    run = _run_vc_installer if run is None else run
    mkdtemp = tempfile.mkdtemp if mkdtemp is None else mkdtemp
    rmtree = shutil.rmtree if rmtree is None else rmtree
    missing = vc_runtime_missing if missing is None else missing
    folder = mkdtemp(prefix="creator-os-vcredist-")
    try:
        dest = os.path.join(folder, VC_RUNTIME_URL.rsplit("/", 1)[-1])
        err = download(VC_RUNTIME_URL, dest)
        if err:
            res = {"ok": False, "status": "download_failed",
                   "message": f"The download from Microsoft did not finish: {err}"}
        else:
            ok, why = vc_signature_verdict(verify(dest))
            if not ok:
                res = {"ok": False, "status": "signature_refused",
                       "message": f"The downloaded installer was not run: {why}. It has been deleted."}
            else:
                try:
                    code = run([dest, *VC_RUNTIME_ARGS, "/log", os.path.join(folder, "vc_redist.log")])
                except subprocess.TimeoutExpired:
                    res = {"ok": False, "status": "timed_out",
                           "message": f"The installer did not finish within {VC_RUNTIME_TIMEOUT // 60} minutes."}
                except OSError as exc:
                    res = {"ok": False, "status": "failed",
                           "message": f"The installer could not start: {type(exc).__name__}: {str(exc)[:160]}"}
                else:
                    ok_code, status, message = vc_exit_meaning(code)
                    if code == 1638 and VC_RUNTIME_DECISIVE in missing():
                        ok_code, status, message = False, "repair_needed", (
                            "A newer Microsoft Visual C++ Redistributable is registered, but msvcp140.dll is "
                            "missing from System32. Repair it from Windows Settings (Apps, Installed apps, the "
                            "Microsoft Visual C++ Redistributable (x64) entry, Modify, Repair), or ask whoever "
                            "manages this computer.")
                    res = {"ok": ok_code, "status": status, "exit_code": code, "message": message}
    finally:
        rmtree(folder, ignore_errors=True)
    if os.path.exists(folder):
        res["note"] = f"The temporary folder {folder} could not be deleted; you can delete it yourself."
    return res


def whisper_cpp_bin(which=None, os_name=None):
    """The name of the first whisper.cpp CLI on PATH, or None. `which` is the lookup (default
    shutil.which, read when called) and `os_name` the system (sys.platform form; None reads this
    computer's). On Windows a match counts when it is a .exe: which() also returns the other PATHEXT
    types (.CPL, .BAT, .CMD, ...), and C:\\Windows\\System32\\main.cpl, the Mouse control panel, answers
    to "main" on a stock Windows computer (P102)."""
    which = which or shutil.which
    windows = str(os_name if os_name is not None else sys.platform).lower().startswith("win")
    for name in _WHISPER_CPP_BINS:
        found = which(name)
        if not found:
            continue
        if windows and not str(found).lower().endswith(".exe"):
            continue
        return name
    return None


def detect_backends(os_name=None):
    """What STT backends are actually installed on THIS machine. Detection only; runs nothing.
    os_name (sys.platform form) is the system the whisper.cpp lookup judges by (whisper_cpp_bin)."""
    cpp_bin = whisper_cpp_bin(os_name=os_name)
    try:
        import faster_whisper  # noqa: F401
        fw = True
    except Exception:  # noqa: BLE001
        fw = False
    return {"whisper_cpp": cpp_bin, "faster_whisper": fw}


def _local(text, os_name=None):
    """text with its `python3 tools/...` commands as the computer runs them (env_paths.local_commands:
    `py -3` or `python` on Windows). os_name is the system the doctor reports on (sys.platform form),
    so a simulated system keeps its own wording; None reads this computer's."""
    sys.path.insert(0, str(HERE))
    import env_paths
    if os_name is None:
        return env_paths.local_commands(text)
    return env_paths.local_commands(text, osname="nt" if str(os_name).startswith("win") else "posix")


def _install_hint(os_name, arch):
    """The OS-correct one-liner a non-technical user runs to get a backend. P93: the default
    is always user-only (faster-whisper via the repo's .venv, docs/INSTALL-SCOPE.md); brew and
    apt routes are named as the machine-wide alternative."""
    return _local(_install_hint_text(os_name, arch), os_name)


def _install_hint_text(os_name, arch):
    if os_name == "darwin":
        return ("python3 tools/setup.py --install-deps   (user-only: faster-whisper in the "
                "repo .venv; machine-wide alternative: brew install whisper-cpp ffmpeg)")
    if os_name.startswith("win"):
        return ("python3 tools/setup.py --install-deps   (user-only: faster-whisper in the "
                "repo .venv)")
    return ("python3 tools/setup.py --install-deps   (user-only: faster-whisper in the repo "
            ".venv; machine-wide alternative: apt install whisper-cpp ffmpeg)")


def default_model(ram_gb=None):
    """Conservative RAM-tiered model floor (shared/transcription-engine.md tiers)."""
    if ram_gb is None:
        return "small"
    if ram_gb >= 32:
        return "large-v3"
    if ram_gb >= 16:
        return "medium"
    if ram_gb >= 8:
        return "small"
    return "base"


def _have_cuda():
    # Detection only; never raises. Presence of nvidia-smi is a cheap, dependency-free CUDA proxy.
    return bool(shutil.which("nvidia-smi"))


def select_backend(os_name=None, arch=None, have=None, cuda=None, fw_probe=None, vc_missing=None):
    """Pick the STT backend for a machine. Pure and fully injectable so the selftest can simulate
    any OS/arch/install combination with no real hardware.

    Returns {backend, device, reason, chain, install, ok}. `backend` is None when nothing is
    installed (ok False) and `install` then carries the OS-correct command. `chain` is the ordered
    preference actually considered for this machine. When nothing loads but faster-whisper is
    installed (probe_faster_whisper, run on this machine when `have` is not given, or `fw_probe`),
    the result says so (not_loading) and on Windows with msvcp140.dll absent (`vc_missing`, or
    vc_runtime_missing) `install` names the Visual C++ runtime instead of the package install."""
    detected = have is None
    os_name = (os_name if os_name is not None else sys.platform).lower()
    arch = (arch if arch is not None else platform.machine()).lower()
    have = have if have is not None else {k: bool(v) for k, v in detect_backends(os_name).items()}
    cuda = _have_cuda() if cuda is None else cuda
    is_mac = os_name == "darwin"
    is_apple_silicon = is_mac and arch in ("arm64", "aarch64")

    if is_mac:
        # Both Mac families prefer whisper.cpp: no Python needed, brew bottle avoids Gatekeeper,
        # Metal on Apple Silicon. faster-whisper (CPU, PyAV -> no system ffmpeg) is the fallback.
        chain = ["whisper_cpp", "faster_whisper"]
        note = "Apple Silicon: whisper.cpp uses Metal." if is_apple_silicon else "Intel Mac: whisper.cpp CPU/AVX."
    else:
        # Windows/Linux: faster-whisper first (fastest on both CPU and CUDA), whisper.cpp fallback.
        chain = ["faster_whisper", "whisper_cpp"]
        note = "CUDA available." if cuda else "CPU int8."

    for backend in chain:
        if have.get(backend):
            if backend == "faster_whisper":
                device = "cuda" if (cuda and not is_mac) else "cpu"
                return {"backend": "faster-whisper", "device": device, "reason": note,
                        "chain": chain, "install": None, "ok": True}
            return {"backend": "whisper.cpp",
                    "device": "metal" if is_apple_silicon else "cpu",
                    "reason": note, "chain": chain, "install": None, "ok": True}

    probe = fw_probe if fw_probe is not None else (probe_faster_whisper() if detected else None)
    if probe and probe.get("installed") and not probe.get("loads"):
        gone = ((vc_runtime_missing() if vc_missing is None else vc_missing)
                if os_name.startswith("win") else [])
        return {"backend": None, "device": None, "not_loading": True,
                "reason": f"faster-whisper is installed but could not load ({probe.get('error') or 'unknown error'})",
                "chain": chain, "ok": False,
                "install": vc_runtime_remedy() if VC_RUNTIME_DECISIVE in gone else _install_hint(os_name, arch)}
    return {"backend": None, "device": None,
            "reason": "no STT backend installed; returning run_local_stt gap (never a fabricated transcript)",
            "chain": chain, "install": _install_hint(os_name, arch), "ok": False}


# ── niche-vocab initial prompt ───────────────────────────────────────────────

def build_initial_prompt(tags=None, title=None, extra_terms=None):
    """Assemble a short niche-vocabulary prompt that boosts ASR recognition (faster-whisper's
    `initial_prompt`). Blends the video's own tags/title with the standing niche seed."""
    terms = []
    for t in (list(tags or []) + list(extra_terms or []) + list(_NICHE_SEED)):
        t = str(t).strip()
        if t and t.lower() not in {x.lower() for x in terms}:
            terms.append(t)
    lead = f"This video is titled '{str(title).strip()}'. " if title else ""
    return (lead + "Terms that may appear: " + ", ".join(terms[:24]) + ".").strip()


# ── the gap (no backend / bad media): honest, never a fake transcript ────────

def _gap(reason_code, detail, install=None, backend_chain=None):
    gap = {"gap_type": reason_code, "description": detail,
           "recommended_action": "run_local_stt",
           "impact": "no transcript produced (never fabricated)"}
    if install:
        gap["install"] = install
    return {"transcript_text": None, "srt": None, "json": None, "segments": [],
            "computed_by": None, "backend_chain": backend_chain or [], "gaps": [gap]}


# ── run STT locally (subprocess for whisper.cpp; in-process for faster-whisper) ──

def _run_whisper_cpp(bin_name, media_path, model, out_dir, initial_prompt):
    """Shell out to whisper.cpp -> SRT on disk. Requires a GGML model path via WHISPER_CPP_MODEL
    (a repo can't ship model weights). Returns (srt_path, error)."""
    model_path = os.environ.get("WHISPER_CPP_MODEL")
    if not model_path or not Path(model_path).exists():
        return None, ("whisper.cpp needs a GGML model file; set WHISPER_CPP_MODEL to a "
                      "ggml-<tier>.bin path (download once from the whisper.cpp repo).")
    out_base = str(Path(out_dir) / Path(media_path).stem)
    cmd = [bin_name, "-m", model_path, "-f", str(media_path), "-osrt", "-of", out_base]
    if initial_prompt:
        cmd += ["--prompt", initial_prompt]
    try:
        run = subprocess.run(cmd, capture_output=True, text=True, timeout=SUBPROCESS_TIMEOUT)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, f"whisper.cpp failed: {exc}"
    if run.returncode != 0:
        return None, f"whisper.cpp exited {run.returncode}: {run.stderr.strip()[-300:]}"
    srt = Path(out_base + ".srt")
    return (srt, None) if srt.exists() else (None, "whisper.cpp produced no SRT")


def _run_faster_whisper(media_path, model, out_dir, initial_prompt, device):
    """Transcribe in-process with faster-whisper -> normalized segment list. Returns (segments, error)."""
    try:
        from faster_whisper import WhisperModel
    except Exception as exc:  # noqa: BLE001
        return None, f"faster-whisper not importable: {exc}"
    try:
        wm = WhisperModel(model, device=device, compute_type="int8" if device == "cpu" else "float16")
        segs, _info = wm.transcribe(str(media_path), language=None, initial_prompt=initial_prompt or None)
        out = [{"start": round(float(s.start), 3), "end": round(float(s.end), 3),
                "text": s.text.strip()} for s in segs]
    except Exception as exc:  # noqa: BLE001
        return None, f"faster-whisper run failed: {exc}"
    return out, None


def transcribe(media_path, model=None, initial_prompt=None, out_dir=None,
               tags=None, title=None, os_name=None, arch=None, have=None, cuda=None,
               _selection=None):
    """Transcribe one media file on-device. Validates the file with mediaprobe first, picks the
    OS-correct backend, runs it, and normalizes the output through transcripts.py. Emits the
    videoedit provenance contract (computed_by, backend_chain, gaps[]). Never fabricates.

    `_selection` lets the selftest inject a chosen backend without touching real hardware."""
    media_path = Path(media_path)
    out_dir = Path(out_dir) if out_dir else media_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    if initial_prompt is None:
        initial_prompt = build_initial_prompt(tags=tags, title=title)

    sel = _selection or select_backend(os_name=os_name, arch=arch, have=have, cuda=cuda)
    chain = [{"backend": sel.get("backend"), "device": sel.get("device"), "reason": sel.get("reason")}]
    if not sel.get("ok"):
        return _gap("no_backend",
                    (f"{sel['reason']}. Follow the install step, then re-run (nothing is faked)."
                     if sel.get("not_loading") else
                     "No local STT backend is installed. Install one, then re-run (nothing is faked)."),
                    install=sel.get("install"), backend_chain=chain)

    # Validate the media before spending minutes on STT: zero-duration/corrupt -> honest gap.
    pr = _mp.probe(str(media_path))
    if not pr.get("ok"):
        dur = None
    else:
        try:
            dur = float(((pr.get("format") or {}).get("duration")) or 0.0)
        except (TypeError, ValueError):
            dur = None
    if pr.get("ok") and dur is not None and dur <= 0.0:
        return _gap("zero_duration", "ffprobe reports zero duration; the file is empty or corrupt.",
                    backend_chain=chain)
    # If ffprobe is simply absent we do NOT block STT (faster-whisper/PyAV needs no system ffmpeg).

    model = model or default_model()
    if sel["backend"] == "whisper.cpp":
        which = detect_backends(os_name).get("whisper_cpp") or "whisper-cli"
        srt_path, err = _run_whisper_cpp(which, media_path, model, out_dir, initial_prompt)
        if err:
            return _gap("backend_error", err, install=_install_hint((os_name or sys.platform).lower(),
                        (arch or platform.machine()).lower()), backend_chain=chain)
        parsed = _t.parse(str(srt_path))
        segments, computed_by, srt_out = parsed["segments"], f"whisper.cpp:{model}", str(srt_path)
    else:  # faster-whisper
        device = sel.get("device") or "cpu"
        segments, err = _run_faster_whisper(media_path, model, out_dir, initial_prompt, device)
        if err:
            return _gap("backend_error", err, backend_chain=chain)
        srt_out = str(out_dir / (media_path.stem + ".srt"))
        Path(srt_out).write_text(_t.emit(segments, "srt"), encoding="utf-8")
        computed_by = f"faster-whisper:{model}:{device}"

    word_count = sum(len(str(s.get("text", "")).split()) for s in segments)
    result = {
        "transcript_text": " ".join(s["text"] for s in segments).strip() or None,
        "srt": srt_out,
        "json": None,
        "segments": segments,
        "computed_by": computed_by,
        "backend_chain": chain,
        "parameters": {"model": model, "initial_prompt": initial_prompt},
        "word_count": word_count,
        "gaps": [],
    }
    if word_count < 50:  # engine's low-yield flag: real but low-confidence, still not fabricated.
        result["gaps"].append({"gap_type": "low_confidence", "word_count": word_count,
                               "description": "fewer than 50 words; silent audio or too-small a model",
                               "recommended_action": "re_run_with_larger_model"})
    return result


# ── model allowlist + auto-download with integrity check ─────────────────────

_HOMEBREW_INSTALL = '/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'


def load_model_allowlist(path=None):
    """The committed sha256/size allowlist for whisper.cpp GGML models (canonical-sources/
    whisper-models.json). Never raises; returns a minimal shape if absent."""
    p = Path(path or MODEL_ALLOWLIST)
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"models": {}, "url_prefix": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/"}


def model_dir(explicit=None):
    """Where downloaded whisper.cpp models live (gitignored, local). Overridable via WHISPER_MODEL_DIR."""
    if explicit:
        return Path(explicit)
    env = os.environ.get("WHISPER_MODEL_DIR")
    if env:
        return Path(env)
    return Path(os.environ.get("HOME") or str(HERE)) / ".creator-os" / "whisper-models"


def _sha256_file(path, chunk=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def _stream_download(url, dest, expected_size=None, progress=None, timeout=600):
    """Stream a large file to disk with stdlib urllib (env proxy + CA bundle). Returns an error
    string, or None on success. Writes to a .part temp then atomically renames; never raises."""
    ctx = ssl.create_default_context()
    if os.path.exists(CA_BUNDLE):
        try:
            ctx.load_verify_locations(CA_BUNDLE)
        except Exception:  # noqa: BLE001
            pass
    req = urllib.request.Request(url, headers={"User-Agent": "creator-os-stt-doctor"})
    tmp = Path(str(dest) + ".part")
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r, open(tmp, "wb") as f:
            done = 0
            while True:
                block = r.read(1 << 20)
                if not block:
                    break
                f.write(block)
                done += len(block)
                if progress:
                    progress(done, expected_size)
        tmp.replace(dest)
        return None
    except Exception as exc:  # noqa: BLE001
        try:
            tmp.unlink()
        except OSError:
            pass
        return f"{type(exc).__name__}: {str(exc)[:160]}"


def fetch_model(name, dest_dir=None, allowlist=None, downloader=None, progress=None):
    """Download a whisper.cpp GGML model and verify it against the committed sha256 allowlist.

    Returns {ok, path, model, verified, cached?, error?}. On a sha256 mismatch the partial file is
    deleted and ok is False (never a fabricated success). `downloader` is injectable so the selftest
    runs with no network. faster-whisper needs no manual model (it auto-downloads to the HF cache);
    this path is for the whisper.cpp backend only."""
    allowlist = allowlist or load_model_allowlist()
    models = allowlist.get("models", {})
    entry = models.get(name)
    if not entry:
        return {"ok": False, "model": name, "error": f"unknown model '{name}'; choices: {sorted(models)}"}
    dest = model_dir(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)
    out = dest / entry["file"]
    url = allowlist.get("url_prefix", "") + entry["file"]
    want = entry.get("sha256")
    if out.exists() and want and _sha256_file(out) == want:
        return {"ok": True, "path": str(out), "model": name, "verified": "sha256", "cached": True}
    dl = downloader or _stream_download
    err = dl(url, out, expected_size=entry.get("size_bytes"), progress=progress)
    if err:
        return {"ok": False, "model": name, "error": err, "install_hint": url}
    if want:
        got = _sha256_file(out)
        if got != want:
            try:
                out.unlink()
            except OSError:
                pass
            return {"ok": False, "model": name,
                    "error": f"sha256 mismatch (got {got[:12]}..., want {want[:12]}...); deleted the file"}
        return {"ok": True, "path": str(out), "model": name, "verified": "sha256"}
    # No published hash: fall back to a size check (weaker, but honest about which check ran).
    if entry.get("size_bytes") and out.stat().st_size != entry["size_bytes"]:
        return {"ok": False, "model": name, "error": "downloaded size does not match the expected size"}
    return {"ok": True, "path": str(out), "model": name, "verified": "size"}


# ── doctor: a guided, non-technical setup checklist with a single next action ──

def _find_whisper_cpp_model(explicit_dir=None):
    env = os.environ.get("WHISPER_CPP_MODEL")
    if env and Path(env).exists():
        return env
    d = model_dir(explicit_dir)
    if d.exists():
        found = sorted(d.glob("ggml-*.bin"))
        if found:
            return str(found[0])
    return None


def _verify_found_model(mp, allow):
    """P79 WP-G: a discovered model file must match its committed pin. Returns (ok, note). Before
    this, doctor accepted any file matching ggml-*.bin -- the selftest itself proved it with a
    one-byte fixture reported green -- so a corrupt or swapped model was invisible until whisper.cpp
    crashed or mis-transcribed. Streams the file in 1 MiB chunks (multi-hundred-MB models)."""
    name = os.path.basename(str(mp))
    entry = next((m for m in (allow.get("models") or {}).values() if m.get("file") == name), None)
    if entry is None:
        return False, f"{name} is not in the pinned allowlist (canonical-sources/whisper-models.json)"
    got = _sha256_file(mp)
    if got != entry.get("sha256"):
        return False, f"{name} sha256 mismatch vs its pin (have {got[:12]}..., pin {str(entry.get('sha256'))[:12]}...)"
    return True, f"{name} verified against its pin"


def doctor(os_name=None, arch=None, have=None, model_dir_override=None, brew_present=None, ram_gb=None,
           verify_model=False, allowlist_path=None, fw_probe=None, system_root=None, dll_exists=None):
    """A plain-language readiness check for on-device transcription. Each step reports {ok,
    what_it_is, next_command, why}; the result carries a green/amber/red verdict and the single next
    action. Pure and injectable so the wizard and the selftest can simulate any machine. With
    verify_model=True (the CLI path) a discovered whisper.cpp model is hashed against the committed
    pins; library callers keep the fast existence-only default."""
    os_name = (os_name if os_name is not None else sys.platform).lower()
    arch = (arch if arch is not None else platform.machine()).lower()
    real_machine = have is None
    have = have if have is not None else {k: bool(v) for k, v in detect_backends(os_name).items()}
    # P102: faster-whisper installed but not loading (a missing Visual C++ runtime on Windows) is told
    # apart from not installed, so the doctor never sends the person back to --install-deps for it.
    if fw_probe is None:
        fw_probe = (probe_faster_whisper() if real_machine else
                    {"installed": bool(have.get("faster_whisper")), "loads": bool(have.get("faster_whisper")),
                     "error": ""})
    fw_broken = fw_probe.get("installed") and not fw_probe.get("loads")
    vc_missing = vc_runtime_missing(system_root, dll_exists) if fw_broken and os_name.startswith("win") else []
    is_mac = os_name == "darwin"
    sel = select_backend(os_name=os_name, arch=arch, have=have)
    steps = []

    steps.append({"step": "computer", "ok": True,
                  "what_it_is": f"{'macOS' if is_mac else ('Windows' if os_name.startswith('win') else os_name)} "
                                f"({'Apple Silicon' if is_mac and arch in ('arm64', 'aarch64') else arch})",
                  "why": "picks the right transcription engine for your machine"})

    if sel["ok"]:
        steps.append({"step": "engine", "ok": True, "what_it_is": sel["backend"],
                      "why": "found a speech-to-text engine that runs on your computer"})
    elif VC_RUNTIME_DECISIVE in vc_missing:
        steps.append({"step": "engine", "ok": False,
                      "what_it_is": ("faster-whisper is installed, but Windows is missing the Microsoft Visual "
                                     f"C++ runtime it loads ({', '.join(vc_missing)})"),
                      "next_command": vc_runtime_remedy(),
                      "why": "pip cannot install this system library, so installing the Creator OS packages "
                             "again would not fix it"})
    elif fw_broken:
        steps.append({"step": "engine", "ok": False,
                      "what_it_is": f"faster-whisper is installed but could not load ({fw_probe.get('error') or 'unknown error'})",
                      "next_command": _install_hint(os_name, arch),
                      "why": "reinstalling the Creator OS packages replaces a broken faster-whisper install"})
    else:
        steps.append({"step": "engine", "ok": False,
                      "what_it_is": "a local speech-to-text engine (whisper.cpp or faster-whisper)",
                      "next_command": _install_hint(os_name, arch),
                      "why": "needed to turn your videos into transcripts on your own computer"})

    if is_mac and not sel["ok"]:
        hb = shutil.which("brew") is not None if brew_present is None else brew_present
        if not hb:
            steps.append({"step": "homebrew", "ok": False,
                          "what_it_is": "Homebrew, needed only for the machine-wide whisper.cpp alternative (affects the whole computer)",
                          "next_command": _HOMEBREW_INSTALL,
                          "why": "not needed for the user-only default (faster-whisper via --install-deps); notarized bottles, no Gatekeeper prompt, if you choose the whisper.cpp route"})

    # whisper.cpp needs a model FILE; faster-whisper auto-downloads its own on first run.
    if sel.get("backend") == "whisper.cpp":
        mp = _find_whisper_cpp_model(model_dir_override)
        tier = default_model(ram_gb)
        name = {"base": "base.en", "small": "small.en", "medium": "medium", "large-v3": "large-v3"}.get(tier, "small.en")
        if mp and verify_model:
            ok_m, note = _verify_found_model(mp, load_model_allowlist(allowlist_path))
            step = {"step": "model", "ok": ok_m, "what_it_is": f"speech model at {mp} ({note})",
                    "why": ("the model matches its committed integrity pin" if ok_m else
                            "a model that fails its integrity pin must not be transcribed with; re-fetch it")}
            if not ok_m:
                step["next_command"] = _local(f"python3 tools/transcribe.py doctor --fetch-model {name}", os_name)
            steps.append(step)
        elif mp:
            steps.append({"step": "model", "ok": True,
                          "what_it_is": f"speech model at {mp} (existence only; the CLI doctor verifies the hash)",
                          "why": "whisper.cpp has a model to transcribe with"})
        else:
            steps.append({"step": "model", "ok": False,
                          "what_it_is": "a one-time speech model download (a few hundred MB)",
                          "next_command": _local(f"python3 tools/transcribe.py doctor --fetch-model {name}", os_name),
                          "why": "whisper.cpp needs a model file; this downloads and verifies it for you"})
    elif sel.get("backend") == "faster-whisper":
        steps.append({"step": "model", "ok": True,
                      "what_it_is": "faster-whisper downloads its model automatically on first use",
                      "why": "no manual model step needed"})

    reds = [s for s in steps if not s["ok"]]
    if not reds:
        verdict = "green"
    elif any(s["step"] == "engine" for s in reds):
        verdict = "red"
    else:
        verdict = "amber"
    next_action = reds[0]["next_command"] if reds else None
    return {"os": os_name, "arch": arch, "verdict": verdict, "backend": sel.get("backend"),
            "steps": steps, "next_action": next_action, "faster_whisper": fw_probe,
            "vc_runtime_missing": vc_missing, "vc_runtime_needed": VC_RUNTIME_DECISIVE in vc_missing,
            "summary": {"green": "You are ready to transcribe on this computer.",
                        "amber": "Almost ready: one optional step remains (see next_action).",
                        "red": "Install a speech-to-text engine first (see next_action)."}[verdict]}


# ── selftest (no network, no real backend needed) ───────────────────────────

def selftest():
    checks = []

    def ok(name, cond):
        checks.append((name, bool(cond)))

    # select_backend: Apple Silicon prefers whisper.cpp when installed.
    s = select_backend(os_name="darwin", arch="arm64", have={"whisper_cpp": True, "faster_whisper": True}, cuda=False)
    ok("apple silicon -> whisper.cpp (metal)", s["backend"] == "whisper.cpp" and s["device"] == "metal")
    # Apple Silicon with only faster-whisper falls back to it.
    s = select_backend(os_name="darwin", arch="arm64", have={"whisper_cpp": False, "faster_whisper": True}, cuda=False)
    ok("apple silicon fallback -> faster-whisper cpu", s["backend"] == "faster-whisper" and s["device"] == "cpu")
    # Linux + CUDA prefers faster-whisper on the GPU.
    s = select_backend(os_name="linux", arch="x86_64", have={"whisper_cpp": True, "faster_whisper": True}, cuda=True)
    ok("linux+cuda -> faster-whisper cuda", s["backend"] == "faster-whisper" and s["device"] == "cuda")
    # Windows CPU-only, only whisper.cpp installed -> whisper.cpp cpu.
    s = select_backend(os_name="win32", arch="amd64", have={"whisper_cpp": True, "faster_whisper": False}, cuda=False)
    ok("windows cpu whisper.cpp fallback", s["backend"] == "whisper.cpp" and s["device"] == "cpu")
    # Nothing installed -> honest gap with an OS-correct install string.
    s = select_backend(os_name="darwin", arch="arm64", have={"whisper_cpp": False, "faster_whisper": False})
    ok("no backend -> ok False + mac hint is user-only-first (P93)",
       s["ok"] is False and "--install-deps" in (s["install"] or "")
       and "machine-wide alternative" in (s["install"] or ""))
    s = select_backend(os_name="linux", arch="x86_64", have={"whisper_cpp": False, "faster_whisper": False})
    ok("no backend on linux -> user-only .venv hint (P93)", "--install-deps" in (s["install"] or ""))

    # RAM-tiered model floor.
    ok("model floor 8GB -> small", default_model(8) == "small")
    ok("model floor 32GB -> large-v3", default_model(32) == "large-v3")
    ok("model floor unknown -> small", default_model() == "small")

    # niche prompt blends tags/title with the seed and dedupes.
    p = build_initial_prompt(tags=["armoire", "farmhouse"], title="Patina hardware")
    ok("initial_prompt mentions the title", "Patina hardware" in p)
    ok("initial_prompt carries niche + video tags", "farmhouse" in p and "armoire" in p and p.count("armoire") == 1)

    # transcribe with NO backend -> run_local_stt gap, never a fake transcript.
    r = transcribe("/nonexistent-p45.mp4", os_name="darwin", arch="arm64",
                   have={"whisper_cpp": False, "faster_whisper": False})
    ok("no-backend transcribe returns gap, no transcript", r["transcript_text"] is None and r["segments"] == [])
    ok("gap is run_local_stt with the user-only install hint (P93)",
       r["gaps"][0]["recommended_action"] == "run_local_stt"
       and "--install-deps" in r["gaps"][0].get("install", ""))

    # Normalization path: a canned SRT parses into segments (proves the transcripts.py wiring).
    import tempfile
    tmp = Path(tempfile.mkdtemp(prefix="transcribe_selftest_"))
    try:
        srt = tmp / "canned.srt"
        srt.write_text("1\n00:00:00,000 --> 00:00:03,000\nToday we restore an armoire.\n\n"
                       "2\n00:00:03,000 --> 00:00:07,000\nThen we add wainscoting.\n", encoding="utf-8")
        parsed = _t.parse(str(srt))
        ok("canned SRT normalizes to 2 segments", parsed["segment_count"] == 2)
        ok("normalized text carries niche word", "armoire" in parsed["plain_text"])

        # P46 doctor: verdicts for simulated machines (pure/injectable, no real hardware).
        d_none = doctor(os_name="darwin", arch="arm64", have={"whisper_cpp": False, "faster_whisper": False})
        ok("doctor red when no engine + mac install action", d_none["verdict"] == "red" and "machine-wide alternative: brew install whisper-cpp" in (d_none["next_action"] or ""))
        d_fw = doctor(os_name="linux", arch="x86_64", have={"whisper_cpp": False, "faster_whisper": True})
        ok("doctor green with faster-whisper (auto model)", d_fw["verdict"] == "green" and d_fw["next_action"] is None)
        d_cpp_nomodel = doctor(os_name="darwin", arch="arm64", have={"whisper_cpp": True, "faster_whisper": False},
                               model_dir_override=str(tmp / "empty-models"))
        ok("doctor amber when whisper.cpp present but no model", d_cpp_nomodel["verdict"] == "amber"
           and "--fetch-model" in (d_cpp_nomodel["next_action"] or ""))
        # P102: faster-whisper installed but not loading is told apart from not installed; on Windows
        # with the Visual C++ runtime absent the doctor names it, never the --install-deps loop.
        _dll_err = FileNotFoundError("Could not find module 'ctranslate2.dll' (or one of its dependencies)")

        def _raise_dll(_name):
            raise _dll_err

        def _no_spec(_name):
            raise ValueError("faster_whisper.__spec__ is None")
        _pr = [probe_faster_whisper(find_spec=lambda n: None),
               probe_faster_whisper(find_spec=lambda n: object(), importer=_raise_dll),
               probe_faster_whisper(find_spec=lambda n: object(), importer=lambda n: None),
               probe_faster_whisper(find_spec=_no_spec)]
        ok("probe_faster_whisper tells not installed, installed but not loading, and loading apart",
           _pr[0] == {"installed": False, "loads": False, "error": ""}
           and _pr[1]["installed"] is True and _pr[1]["loads"] is False
           and _pr[1]["error"].startswith("FileNotFoundError: Could not find module")
           and _pr[2] == {"installed": True, "loads": True, "error": ""}
           and _pr[3]["installed"] is False)
        _seen_dll = []
        _missing = vc_runtime_missing("C:\\Windows", exists=lambda p: _seen_dll.append(p) or p.endswith("msvcp140.dll"))
        ok("vc_runtime_missing lists the absent DLLs under System32",
           _missing == ["vcruntime140.dll", "vcruntime140_1.dll"]
           and _seen_dll[0] == "C:\\Windows\\System32\\msvcp140.dll"
           and vc_runtime_missing("C:\\Windows", exists=lambda p: True) == [])
        _none = {"whisper_cpp": False, "faster_whisper": False}
        _d_vc = doctor(os_name="win32", arch="amd64", have=_none, fw_probe=_pr[1],
                       system_root="C:\\Windows", dll_exists=lambda p: False)
        _d_dll_ok = doctor(os_name="win32", arch="amd64", have=_none, fw_probe=_pr[1],
                           system_root="C:\\Windows", dll_exists=lambda p: True)
        _d_mac = doctor(os_name="darwin", arch="arm64", have=_none, fw_probe=_pr[1], brew_present=True)
        _d_older = doctor(os_name="win32", arch="amd64", have=_none, fw_probe=_pr[1], system_root="C:\\Windows",
                          dll_exists=lambda p: not p.endswith("vcruntime140_1.dll"))
        _d_absent = doctor(os_name="win32", arch="amd64", have=_none, fw_probe=_pr[0],
                           system_root="C:\\Windows", dll_exists=lambda p: False)
        ok("on Windows with the runtime absent the doctor names the Visual C++ runtime, labeled machine-wide",
           _d_vc["verdict"] == "red" and _d_vc["next_action"] == vc_runtime_remedy()
           and "machine-wide: affects the whole computer" in _d_vc["next_action"]
           and "https://aka.ms/vc14/vc_redist.x64.exe" in _d_vc["next_action"]
           and "--install-deps" not in _d_vc["next_action"]
           and _d_vc["vc_runtime_missing"] == list(VC_RUNTIME_DLLS) and _d_vc["vc_runtime_needed"] is True
           and "Visual C++" in _d_vc["steps"][1]["what_it_is"])
        _sb = {k: select_backend(os_name="win32", arch="amd64", have=_none, cuda=False, fw_probe=_pr[1], vc_missing=v)
               for k, v in (("runtime", ["msvcp140.dll"]), ("older", ["vcruntime140_1.dll"]))}
        _sb_mac = select_backend(os_name="darwin", arch="arm64", have=_none, cuda=False, fw_probe=_pr[1],
                                 vc_missing=["msvcp140.dll"])
        _sb_absent = select_backend(os_name="win32", arch="amd64", have=_none, cuda=False, fw_probe=_pr[0])
        _gap_nl = transcribe(tmp / "none.wav", out_dir=tmp, _selection=_sb["runtime"])
        ok("select_backend and transcribe tell installed but not loading apart, naming the runtime on Windows",
           _sb["runtime"]["not_loading"] is True and _sb["runtime"]["install"] == vc_runtime_remedy()
           and "could not load (FileNotFoundError" in _sb["runtime"]["reason"]
           and _sb["older"]["install"] == _install_hint("win32", "amd64")
           and _sb_mac["install"] == _install_hint("darwin", "arm64") and _sb_mac["not_loading"] is True
           and "not_loading" not in _sb_absent and _sb_absent["install"] == _install_hint("win32", "amd64")
           and "installed but could not load" in json.dumps(_gap_nl) and vc_runtime_remedy() in json.dumps(_gap_nl))
        # P102: on Windows the whisper.cpp lookup takes a .exe, so the Mouse control panel
        # (System32\\main.cpl, which which() returns for "main" through PATHEXT) is not an engine.
        _cpl = "C:\\WINDOWS\\system32\\main.CPL"

        def _paths(**found):
            return lambda name, *a, **k: found.get(name.replace("-", "_"))
        _wb = {
            "cpl": whisper_cpp_bin(_paths(main=_cpl), "win32"),
            "cli_and_cpl": whisper_cpp_bin(_paths(whisper_cli="C:\\tools\\whisper-cli.EXE", main=_cpl), "win32"),
            "main_exe": whisper_cpp_bin(_paths(main="C:\\tools\\MAIN.EXE"), "win32"),
            "main_bat": whisper_cpp_bin(_paths(main="C:\\tools\\main.bat"), "win32"),
            "mac": whisper_cpp_bin(_paths(whisper_cli="/opt/homebrew/bin/whisper-cli"), "darwin"),
            "linux": whisper_cpp_bin(_paths(main="/usr/local/bin/main"), "linux"),
            "none": whisper_cpp_bin(_paths(), "win32"),
        }
        ok("whisper_cpp_bin takes a .exe on Windows, so main.cpl or main.bat is not whisper.cpp, and any match elsewhere",
           _wb == {"cpl": None, "cli_and_cpl": "whisper-cli", "main_exe": "main", "main_bat": None,
                   "mac": "whisper-cli", "linux": "main", "none": None})
        _real_which = shutil.which
        shutil.which = lambda name, *a, **k: _cpl if name == "main" else None
        try:
            _det_w, _det_l = detect_backends("win32")["whisper_cpp"], detect_backends("linux")["whisper_cpp"]
            _d_cpl = doctor(os_name="win32", arch="amd64", fw_probe=_pr[1], system_root="C:\\Windows",
                            dll_exists=lambda p: False)
            _sb_cpl = select_backend(os_name="win32", arch="amd64", cuda=False, fw_probe=_pr[1],
                                     vc_missing=["msvcp140.dll"])
        finally:
            shutil.which = _real_which
        ok("with only main.cpl on a simulated Windows PATH, detection, the doctor and the selection skip whisper.cpp "
           "and the doctor names the Visual C++ runtime",
           _det_w is None and _det_l == "main" and _d_cpl["backend"] != "whisper.cpp"
           and _d_cpl["next_action"] == vc_runtime_remedy() and _sb_cpl["backend"] != "whisper.cpp"
           and _sb_cpl["install"] == vc_runtime_remedy())
        # The other direction, so a lookup that judges by the real system is caught on a Windows host
        # too: on a simulated Mac, a whisper-cli outside a .exe is the engine the doctor and the
        # selection pick.
        shutil.which = lambda name, *a, **k: "/opt/homebrew/bin/whisper-cli" if name == "whisper-cli" else None
        try:
            _d_mac_cli = doctor(os_name="darwin", arch="arm64", fw_probe=_pr[0], brew_present=True)
            _sb_mac_cli = select_backend(os_name="darwin", arch="arm64", cuda=False, fw_probe=_pr[0])
        finally:
            shutil.which = _real_which
        ok("on a simulated Mac with whisper-cli on PATH, the doctor and the selection pick whisper.cpp",
           _d_mac_cli["backend"] == "whisper.cpp" and _sb_mac_cli["backend"] == "whisper.cpp")
        ok("with msvcp140.dll present (an older runtime), a load failure points at a reinstall, not the runtime",
           _d_older["vc_runtime_missing"] == ["vcruntime140_1.dll"] and _d_older["vc_runtime_needed"] is False
           and "could not load" in _d_older["steps"][1]["what_it_is"]
           and "--install-deps" in (_d_older["next_action"] or ""))
        ok("installed but not loading for another reason, or off Windows, points at a reinstall",
           "could not load (FileNotFoundError" in _d_dll_ok["steps"][1]["what_it_is"]
           and "--install-deps" in (_d_dll_ok["next_action"] or "") and _d_dll_ok["vc_runtime_missing"] == []
           and "could not load" in _d_mac["steps"][1]["what_it_is"] and _d_mac["vc_runtime_missing"] == [])
        ok("not installed keeps the install hint and asks nothing about the runtime",
           "--install-deps" in (_d_absent["next_action"] or "") and _d_absent["vc_runtime_missing"] == []
           and _d_absent["steps"][1]["what_it_is"].startswith("a local speech-to-text engine"))
        # P102: the Visual C++ install the wizard runs on request. The signature verdict accepts only a
        # Valid signature from Microsoft Corporation chained to the pinned root.
        _ms = {"status": "Valid",
               "signer": "CN=Microsoft Corporation, O=Microsoft Corporation, L=Redmond, S=Washington, C=US",
               "root_thumbprint": VC_RUNTIME_ROOT_THUMBPRINT,
               "root_subject": "CN=Microsoft Root Certificate Authority 2011, O=Microsoft Corporation, "
                               "L=Redmond, S=Washington, C=US"}
        _verdicts = {
            "microsoft": vc_signature_verdict(_ms),
            "lowercase thumbprint": vc_signature_verdict(dict(_ms, root_thumbprint=VC_RUNTIME_ROOT_THUMBPRINT.lower())),
            "hash mismatch": vc_signature_verdict(dict(_ms, status="HashMismatch")),
            "not signed": vc_signature_verdict({"status": "NotSigned", "signer": "", "root_thumbprint": "",
                                                "root_subject": ""}),
            "other root": vc_signature_verdict(dict(_ms, root_thumbprint="0" * 40)),
            "root name": vc_signature_verdict(dict(_ms, root_subject="CN=Microsoft Root Certificate Authority 2010")),
            "signer org": vc_signature_verdict(dict(_ms, signer="CN=Microsoft Corporation, O=Contoso Ltd")),
            "lookalike org": vc_signature_verdict(dict(_ms, signer="CN=x, O=Microsoft Corporation Fake")),
            "org in CN only": vc_signature_verdict(dict(_ms, signer="CN=O=Microsoft Corporation")),
            "org inside a quoted CN": vc_signature_verdict(dict(
                _ms, signer='CN="Contoso, O=Microsoft Corporation", O=Contoso Ltd, C=US')),
            "org inside a quoted OU": vc_signature_verdict(dict(
                _ms, signer='CN=x, OU="Dev, O=Microsoft Corporation", O=Contoso Ltd')),
            "two organizations": vc_signature_verdict(dict(_ms, signer="CN=x, O=Contoso, O=Microsoft Corporation")),
            "root name inside a quoted O": vc_signature_verdict(dict(
                _ms, root_subject='CN=Other Root, O="x, CN=Microsoft Root Certificate Authority 2011"')),
            "error": vc_signature_verdict({"error": "powershell missing"}),
            "nothing": vc_signature_verdict(None),
        }
        ok("the signature verdict accepts Valid, signed by Microsoft Corporation, chained to the pinned root",
           _verdicts["microsoft"][0] is True and _verdicts["lowercase thumbprint"][0] is True)
        ok("the signature verdict refuses a bad hash, an unsigned file, another root or signer, and an error",
           all(_verdicts[k][0] is False for k in _verdicts if k not in ("microsoft", "lowercase thumbprint"))
           and "HashMismatch" in _verdicts["hash mismatch"][1]
           and "Contoso" in _verdicts["signer org"][1] and "2010" in _verdicts["root name"][1]
           and "thumbprint (0000" in _verdicts["other root"][1]
           and _dn_values('CN="a, b", O=Microsoft Corporation', "CN") == ["a, b"])
        # The PowerShell call: the full path under %SystemRoot%, the script as -EncodedCommand, the file
        # in the environment, and the last line of its output read as JSON.
        import base64 as _b64
        _ps_seen = []

        class _PsDone:
            def __init__(self, out, err="", code=0):
                self.stdout, self.stderr, self.returncode = out, err, code

        def _ps_run(argv, **kw):
            _ps_seen.append((argv, kw))
            return _PsDone("warming up\n" + json.dumps(_ms) + "\n")
        _saved_psm = os.environ.get("PSModulePath")
        os.environ["PSModulePath"] = "C:\\from-powershell-7"
        try:
            _info = vc_signature_info("C:\\Temp\\x y\\installer.exe", run=_ps_run, system_root="D:\\Win")
        finally:
            if _saved_psm is None:
                os.environ.pop("PSModulePath", None)
            else:
                os.environ["PSModulePath"] = _saved_psm
        _argv, _kw = _ps_seen[0]
        _script = _b64.b64decode(_argv[-1]).decode("utf-16-le")
        ok("vc_signature_info runs Windows PowerShell by its full path, with the file in the environment",
           _info == _ms
           and _argv[:-1] == ["D:\\Win\\System32\\WindowsPowerShell\\v1.0\\powershell.exe", "-NoProfile",
                              "-NonInteractive", "-EncodedCommand"]
           and "Get-AuthenticodeSignature -LiteralPath $f" in _script and "X509Chain" in _script
           and _kw["env"]["CREATOR_OS_VC_FILE"] == "C:\\Temp\\x y\\installer.exe"
           and "C:\\Temp" not in _argv[-1])
        ok("vc_signature_info drops PSModulePath, decodes UTF-8, and the script reports the chain only when it built",
           not any(k.upper() == "PSMODULEPATH" for k in _kw["env"]) and _kw.get("encoding") == "utf-8"
           and _kw.get("errors") == "replace" and "text" not in _kw
           and "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8" in _script
           and "$built = $chain.Build($c)" in _script and "if (($built -or $other.Count -eq 0)" in _script)
        # On Windows, the real Windows PowerShell call: an unsigned file is refused, and Windows
        # PowerShell's own executable reads as Valid from Microsoft Corporation.
        if os.name == "nt":
            _unsigned = tmp / "unsigned-stand-in.exe"
            _unsigned.write_bytes(b"MZ" + b"\0" * 510)
            _real_un = vc_signature_info(str(_unsigned))
            _ps_exe = Path(os.environ.get("SystemRoot") or "C:\\Windows") / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
            _real_ms = vc_signature_info(str(_ps_exe))
            ok("on Windows the real signature check refuses an unsigned file and reads powershell.exe as Valid "
               "from Microsoft Corporation",
               _real_un.get("status") not in (None, "", "Valid") and vc_signature_verdict(_real_un)[0] is False
               and _real_ms.get("status") == "Valid"
               and _dn_values(_real_ms.get("signer"), "O") == ["Microsoft Corporation"])
        else:
            print("  [skip] the real Windows PowerShell signature check runs on Windows only")

        def _ps_raise(argv, **kw):
            raise FileNotFoundError("powershell.exe")
        _bad = [vc_signature_info("f", run=lambda a, **k: _PsDone("", "Get-AuthenticodeSignature : no file", 1)),
                vc_signature_info("f", run=_ps_raise),
                vc_signature_info("f", run=lambda a, **k: _PsDone("[1, 2]\n"))]
        ok("vc_signature_info reports an error for text, a failed start or a non-object, never a verdict",
           all("error" in b and vc_signature_verdict(b)[0] is False for b in _bad)
           and "no file" in _bad[0]["error"] and "FileNotFoundError" in _bad[1]["error"])
        # install_vc_runtime with each step stood in: a real temporary folder under the selftest's.
        _vc_tmp = tmp / "vc"
        _vc_tmp.mkdir()

        def _vc(code=0, verdict=None, dl_err=None, os_name="win32", arch="amd64", run_exc=None, rmtree=None,
                still_missing=(), dl_exc=None):
            seen = {"download": [], "verify": [], "run": [], "folders": []}

            def _mk(prefix):
                d = tempfile.mkdtemp(prefix=prefix, dir=str(_vc_tmp))
                seen["folders"].append(d)
                return d

            def _dl(url, dest):
                seen["download"].append((url, dest))
                if dl_exc:
                    raise dl_exc
                if dl_err:
                    return dl_err
                Path(dest).write_bytes(b"MZ installer stand-in")
                return None

            def _ver(path):
                seen["verify"].append((path, Path(path).is_file()))
                return _ms if verdict is None else verdict

            def _run(argv):
                seen["run"].append(list(argv))
                if run_exc:
                    raise run_exc
                return code
            try:
                res = install_vc_runtime(os_name=os_name, arch=arch, download=_dl, verify=_ver, run=_run,
                                         mkdtemp=_mk, missing=lambda: list(still_missing),
                                         **({"rmtree": rmtree} if rmtree else {}))
            except Exception as exc:  # noqa: BLE001 -- a raising step is one of the cases
                res = {"raised": type(exc).__name__}
            return res, seen
        _codes = {c: _vc(code=c) for c in (0, 3010, 1638, 1602, 1223, 1307, 1925, 5, 1603)}
        _r0, _s0 = _codes[0]
        ok("install_vc_runtime downloads Microsoft's machine-wide x64 package into its own folder, checks "
           "it, then runs it",
           _s0["download"][0][0] == VC_RUNTIME_URL
           and Path(_s0["download"][0][1]).parent == Path(_s0["folders"][0])
           and Path(_s0["download"][0][1]).name == "vc_redist.x64.exe"
           and _s0["verify"] == [(_s0["download"][0][1], True)]
           and _s0["run"] == [[_s0["download"][0][1], "/install", "/passive", "/norestart", "/log",
                               os.path.join(_s0["folders"][0], "vc_redist.log")]]
           and _r0 == {"ok": True, "status": "installed", "exit_code": 0,
                       "message": VC_RUNTIME_EXIT[0][2]})
        ok("each installer exit code maps to its outcome",
           [(c, r["ok"], r["status"], r["exit_code"]) for c, (r, _s) in _codes.items()]
           == [(0, True, "installed", 0), (3010, True, "restart", 3010), (1638, True, "newer", 1638),
               (1602, False, "cancelled", 1602), (1223, False, "cancelled", 1223),
               (1307, False, "needs_admin", 1307), (1925, False, "needs_admin", 1925),
               (5, False, "needs_admin", 5), (1603, False, "failed", 1603)]
           and all("administrator" in _codes[c][0]["message"] and "manual route" in _codes[c][0]["message"]
                   for c in (1307, 1925, 5))
           and "exit code 1603" in _codes[1603][0]["message"] and VC_RUNTIME_URL in _codes[1603][0]["message"]
           and "Restart Windows" in _codes[3010][0]["message"])
        _refused = {k: _vc(verdict=v) for k, v in (
            ("hash", dict(_ms, status="HashMismatch")), ("root", dict(_ms, root_thumbprint="0" * 40)),
            ("signer", dict(_ms, signer="CN=x, O=Contoso Ltd")), ("error", {"error": "no powershell"}))}
        ok("a signature the verdict refuses stops the install before it runs, and says the file is deleted",
           all(r["status"] == "signature_refused" and r["ok"] is False and s["run"] == [] and "deleted" in r["message"]
               and "exit_code" not in r for r, s in _refused.values()))
        _dl_fail, _dl_seen = _vc(dl_err="URLError: offline")
        ok("a download error is reported and nothing is checked or run",
           _dl_fail["status"] == "download_failed" and "offline" in _dl_fail["message"]
           and _dl_seen["verify"] == [] and _dl_seen["run"] == [])
        _to, _ = _vc(run_exc=subprocess.TimeoutExpired("vc_redist", VC_RUNTIME_TIMEOUT))
        _nostart, _ = _vc(run_exc=OSError(740, "The requested operation requires elevation"))
        ok("an installer that times out or cannot start is reported, not mapped to an exit code",
           _to["status"] == "timed_out" and _nostart["status"] == "failed" and "elevation" in _nostart["message"]
           and "exit_code" not in _to and "exit_code" not in _nostart)
        _raised, _raised_seen = _vc(dl_exc=RuntimeError("download crashed"))
        _to_run = _vc(run_exc=subprocess.TimeoutExpired("vc_redist", VC_RUNTIME_TIMEOUT))
        _all_runs = (list(_codes.values()) + list(_refused.values())
                     + [(_dl_fail, _dl_seen), _vc(run_exc=OSError(5, "x")), _to_run])
        ok("a step that raises propagates, and its folder is deleted too",
           _raised == {"raised": "RuntimeError"} and len(_raised_seen["folders"]) == 1
           and not Path(_raised_seen["folders"][0]).exists())
        _repair, _ = _vc(code=1638, still_missing=("msvcp140.dll",))
        _newer_ok, _ = _vc(code=1638, still_missing=("vcruntime140_1.dll",))
        ok("exit code 1638 with msvcp140.dll still missing reads as repair needed, and with it present as newer",
           _repair["ok"] is False and _repair["status"] == "repair_needed" and "Repair" in _repair["message"]
           and _newer_ok["ok"] is True and _newer_ok["status"] == "newer")
        ok("the temporary folder is deleted in every outcome above",
           all(len(s["folders"]) == 1 and not Path(s["folders"][0]).exists() and "note" not in r
               for r, s in _all_runs))
        _kept, _kept_seen = _vc(rmtree=lambda path, ignore_errors=False: None)
        ok("a folder that could not be deleted is named in a note",
           _kept_seen["folders"][0] in _kept.get("note", "") and _kept["ok"] is True)
        _arm, _arm_seen = _vc(arch="ARM64")
        _off = {o: _vc(os_name=o) for o in ("darwin", "linux")}
        _x86, _x86_seen = _vc(arch="x86")
        ok("ARM64 Windows downloads the same x64 package; macOS, Linux and 32-bit Windows start nothing",
           _arm["ok"] is True and _arm_seen["download"][0][0] == VC_RUNTIME_URL
           and all(r["status"] == "unsupported" and s["folders"] == [] and s["download"] == []
                   for r, s in list(_off.values()) + [(_x86, _x86_seen)]))
        # P102: on a computer that runs the repo's scripts as py -3, the printed commands say so.
        import env_paths as _ep_w
        _real_pc_w = _ep_w.python_command
        _ep_w.python_command = lambda osname=None, which=None: (  # Windows runs the scripts as py -3
            "python3" if osname not in (None, "nt") else "py -3")
        try:
            _hint_w = _install_hint("win32", "amd64")
            _fetch_w = doctor(os_name="win32", arch="amd64", have={"whisper_cpp": True, "faster_whisper": False},
                              model_dir_override=str(tmp / "empty-models"))["next_action"] or ""
            _mac_w = _install_hint("darwin", "arm64")
        finally:
            _ep_w.python_command = _real_pc_w
        ok("the install hint and the model command are written as this computer runs the scripts",
           _hint_w.startswith("py -3 tools/setup.py --install-deps")
           and _fetch_w.startswith("py -3 tools/transcribe.py doctor --fetch-model")
           and "python3 tools/" not in _hint_w + _fetch_w and _mac_w.startswith("python3 tools/setup.py"))
        mdir = tmp / "models"
        mdir.mkdir()
        (mdir / "ggml-base.en.bin").write_bytes(b"x")
        d_cpp_model = doctor(os_name="darwin", arch="arm64", have={"whisper_cpp": True, "faster_whisper": False},
                             model_dir_override=str(mdir))
        ok("doctor green when whisper.cpp + a model file", d_cpp_model["verdict"] == "green")
        # P79 WP-G: the same one-byte fixture must FAIL once the hash is verified (the historical gap).
        d_fake = doctor(os_name="darwin", arch="arm64", have={"whisper_cpp": True, "faster_whisper": False},
                        model_dir_override=str(mdir), verify_model=True)
        m_step = next(s for s in d_fake["steps"] if s["step"] == "model")
        ok("doctor with verify_model flags a model that fails its pin (amber, re-fetch action)",
           d_fake["verdict"] == "amber" and m_step["ok"] is False and "--fetch-model" in (d_fake["next_action"] or ""))
        # a fixture whose bytes match a temp allowlist pin passes verification (never the committed pins)
        good = mdir / "ggml-small.en.bin"
        good.write_bytes(b"fixture-model-bytes")
        import hashlib as _h
        allow_p = tmp / "pins.json"
        allow_p.write_text(json.dumps({"models": {"small.en": {"file": "ggml-small.en.bin",
                           "sha256": _h.sha256(b"fixture-model-bytes").hexdigest(), "size_bytes": 19}}}))
        os.environ["WHISPER_CPP_MODEL"] = str(good)          # exercises the previously untested env branch
        try:
            d_good = doctor(os_name="darwin", arch="arm64", have={"whisper_cpp": True, "faster_whisper": False},
                            model_dir_override=str(mdir), verify_model=True, allowlist_path=str(allow_p))
        finally:
            os.environ.pop("WHISPER_CPP_MODEL", None)
        ok("doctor green when the discovered model matches its pin (via WHISPER_CPP_MODEL)",
           d_good["verdict"] == "green" and "verified against its pin" in
           next(s for s in d_good["steps"] if s["step"] == "model")["what_it_is"])

        # P46 fetch_model: injected downloader + sha256 verify (no network).
        payload = b"synthetic ggml model bytes"
        digest = hashlib.sha256(payload).hexdigest()
        allow = {"url_prefix": "https://example/", "models": {
            "tiny.test": {"file": "ggml-tiny.test.bin", "size_bytes": len(payload), "sha256": digest}}}

        def good_dl(url, dest, expected_size=None, progress=None):
            Path(dest).write_bytes(payload)
            return None
        res = fetch_model("tiny.test", dest_dir=str(tmp / "dl"), allowlist=allow, downloader=good_dl)
        ok("fetch_model verifies sha256", res["ok"] and res["verified"] == "sha256")
        res2 = fetch_model("tiny.test", dest_dir=str(tmp / "dl"), allowlist=allow, downloader=good_dl)
        ok("fetch_model uses the cached verified file", res2.get("cached") is True)

        def bad_dl(url, dest, expected_size=None, progress=None):
            Path(dest).write_bytes(b"corrupted bytes not matching the hash")
            return None
        res3 = fetch_model("tiny.test", dest_dir=str(tmp / "dl2"), allowlist=allow, downloader=bad_dl)
        ok("fetch_model rejects a sha256 mismatch + deletes the file",
           res3["ok"] is False and "mismatch" in res3["error"] and not (tmp / "dl2" / "ggml-tiny.test.bin").exists())
        res4 = fetch_model("does.not.exist", dest_dir=str(tmp / "dl3"), allowlist=allow, downloader=good_dl)
        ok("fetch_model errors on an unknown model", res4["ok"] is False and "unknown model" in res4["error"])

        # The committed allowlist loads and carries all six models with sha256 + size.
        real = load_model_allowlist()
        ok("committed allowlist has 6 models with sha256",
           len(real.get("models", {})) == 6 and all(m.get("sha256") and m.get("size_bytes") for m in real["models"].values()))
    finally:
        import shutil as _sh
        _sh.rmtree(tmp, ignore_errors=True)

    passed = sum(1 for _, c in checks if c)
    for name, c in checks:
        print(f"  [{'ok' if c else 'FAIL'}] {name}")
    print(f"selftest: {'PASS' if passed == len(checks) else 'FAIL'} ({passed} of {len(checks)} checks)")
    return 0 if passed == len(checks) else 1


def main(argv):
    ap = argparse.ArgumentParser(description="OS/backend-aware local STT runner (offline, zero-token).")
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("status")
    dp = sub.add_parser("doctor", help="guided setup check + optional model download")
    dp.add_argument("--fetch-model", help="download + verify a whisper.cpp model by name (e.g. base.en)")
    dp.add_argument("--model-dir")
    rp = sub.add_parser("run")
    rp.add_argument("media")
    rp.add_argument("--model")
    rp.add_argument("--out-dir")
    rp.add_argument("--initial-prompt")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)
    if args.selftest:
        return selftest()
    if args.cmd == "status":
        print(json.dumps({"backends": detect_backends(), "selection": select_backend()}, indent=2))
        return 0
    if args.cmd == "doctor":
        if args.fetch_model:
            def _bar(done, total):
                pct = (f"{100 * done // total}%" if total else f"{done // (1 << 20)} MB")
                print(f"\r  downloading {args.fetch_model}: {pct}", end="", file=sys.stderr, flush=True)
            res = fetch_model(args.fetch_model, dest_dir=args.model_dir, progress=_bar)
            print("", file=sys.stderr)
            print(json.dumps(res, indent=2))
            return 0 if res.get("ok") else 1
        print(json.dumps(doctor(model_dir_override=args.model_dir, verify_model=True), indent=2))
        return 0
    if args.cmd == "run":
        print(json.dumps(transcribe(args.media, model=args.model, out_dir=args.out_dir,
                                    initial_prompt=args.initial_prompt), indent=2, ensure_ascii=False))
        return 0
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
