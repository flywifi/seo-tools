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

def detect_backends():
    """What STT backends are actually installed on THIS machine. Detection only; runs nothing."""
    cpp_bin = None
    for name in _WHISPER_CPP_BINS:
        if shutil.which(name):
            cpp_bin = name
            break
    try:
        import faster_whisper  # noqa: F401
        fw = True
    except Exception:  # noqa: BLE001
        fw = False
    return {"whisper_cpp": cpp_bin, "faster_whisper": fw}


def _install_hint(os_name, arch):
    """The OS-correct one-liner a non-technical user runs to get a backend."""
    if os_name == "darwin":
        # Homebrew bottles are notarized -> no Gatekeeper prompt; faster-whisper needs no system ffmpeg.
        return ("brew install whisper-cpp ffmpeg   "
                "(or: brew install python && pip3 install faster-whisper)")
    if os_name.startswith("win"):
        return "pip install faster-whisper   (install Python from python.org first)"
    return "pip install faster-whisper   (or your package manager: apt install whisper-cpp ffmpeg)"


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


def select_backend(os_name=None, arch=None, have=None, cuda=None):
    """Pick the STT backend for a machine. Pure and fully injectable so the selftest can simulate
    any OS/arch/install combination with no real hardware.

    Returns {backend, device, reason, chain, install, ok}. `backend` is None when nothing is
    installed (ok False) and `install` then carries the OS-correct command. `chain` is the ordered
    preference actually considered for this machine."""
    os_name = (os_name if os_name is not None else sys.platform).lower()
    arch = (arch if arch is not None else platform.machine()).lower()
    have = have if have is not None else {k: bool(v) for k, v in detect_backends().items()}
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
                    "No local STT backend is installed. Install one, then re-run (nothing is faked).",
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
        which = detect_backends().get("whisper_cpp") or "whisper-cli"
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


def doctor(os_name=None, arch=None, have=None, model_dir_override=None, brew_present=None, ram_gb=None):
    """A plain-language readiness check for on-device transcription. Each step reports {ok,
    what_it_is, next_command, why}; the result carries a green/amber/red verdict and the single next
    action. Pure and injectable so the wizard and the selftest can simulate any machine."""
    os_name = (os_name if os_name is not None else sys.platform).lower()
    arch = (arch if arch is not None else platform.machine()).lower()
    have = have if have is not None else {k: bool(v) for k, v in detect_backends().items()}
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
    else:
        steps.append({"step": "engine", "ok": False,
                      "what_it_is": "a local speech-to-text engine (whisper.cpp or faster-whisper)",
                      "next_command": _install_hint(os_name, arch),
                      "why": "needed to turn your videos into transcripts on your own computer"})

    if is_mac and not sel["ok"]:
        hb = shutil.which("brew") is not None if brew_present is None else brew_present
        if not hb:
            steps.append({"step": "homebrew", "ok": False,
                          "what_it_is": "Homebrew, the macOS installer used to add whisper.cpp",
                          "next_command": _HOMEBREW_INSTALL,
                          "why": "the easiest notarized way to install the engine (no Gatekeeper prompt)"})

    # whisper.cpp needs a model FILE; faster-whisper auto-downloads its own on first run.
    if sel.get("backend") == "whisper.cpp":
        mp = _find_whisper_cpp_model(model_dir_override)
        if mp:
            steps.append({"step": "model", "ok": True, "what_it_is": f"speech model at {mp}",
                          "why": "whisper.cpp has a model to transcribe with"})
        else:
            tier = default_model(ram_gb)
            name = {"base": "base.en", "small": "small.en", "medium": "medium", "large-v3": "large-v3"}.get(tier, "small.en")
            steps.append({"step": "model", "ok": False,
                          "what_it_is": "a one-time speech model download (a few hundred MB)",
                          "next_command": f"python3 tools/transcribe.py doctor --fetch-model {name}",
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
            "steps": steps, "next_action": next_action,
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
    ok("no backend -> ok False + mac install hint", s["ok"] is False and "brew install whisper-cpp" in (s["install"] or ""))
    s = select_backend(os_name="linux", arch="x86_64", have={"whisper_cpp": False, "faster_whisper": False})
    ok("no backend on linux -> pip install hint", "pip install faster-whisper" in (s["install"] or ""))

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
    ok("gap is run_local_stt with OS install", r["gaps"][0]["recommended_action"] == "run_local_stt" and "brew install" in r["gaps"][0].get("install", ""))

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
        ok("doctor red when no engine + mac install action", d_none["verdict"] == "red" and "brew install whisper-cpp" in (d_none["next_action"] or ""))
        d_fw = doctor(os_name="linux", arch="x86_64", have={"whisper_cpp": False, "faster_whisper": True})
        ok("doctor green with faster-whisper (auto model)", d_fw["verdict"] == "green" and d_fw["next_action"] is None)
        d_cpp_nomodel = doctor(os_name="darwin", arch="arm64", have={"whisper_cpp": True, "faster_whisper": False},
                               model_dir_override=str(tmp / "empty-models"))
        ok("doctor amber when whisper.cpp present but no model", d_cpp_nomodel["verdict"] == "amber"
           and "--fetch-model" in (d_cpp_nomodel["next_action"] or ""))
        mdir = tmp / "models"
        mdir.mkdir()
        (mdir / "ggml-base.en.bin").write_bytes(b"x")
        d_cpp_model = doctor(os_name="darwin", arch="arm64", have={"whisper_cpp": True, "faster_whisper": False},
                             model_dir_override=str(mdir))
        ok("doctor green when whisper.cpp + a model file", d_cpp_model["verdict"] == "green")

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
        print(json.dumps(doctor(model_dir_override=args.model_dir), indent=2))
        return 0
    if args.cmd == "run":
        print(json.dumps(transcribe(args.media, model=args.model, out_dir=args.out_dir,
                                    initial_prompt=args.initial_prompt), indent=2, ensure_ascii=False))
        return 0
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
