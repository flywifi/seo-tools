#!/usr/bin/env python3
"""Shared interpreter/PATH helpers for a Mac-friendly launch and install.

Two macOS realities drive this module (see docs/SETUP_MAC.md and docs/MACOS-MAINTENANCE.md):

1. The "private toolbox": dependencies install into a repo-local ``.venv`` so a Homebrew Python
   (which follows PEP 668 and refuses global package installs) is never touched. The app's heavy
   tools then run under that venv interpreter. ``app_python()`` returns the venv python when it
   exists and otherwise the current interpreter, so a machine without a ``.venv`` behaves exactly
   as before (no regression).

2. GUI-launch PATH: a double-clicked ``.command`` runs a non-login, non-interactive zsh that
   sources only ``~/.zshenv``, so neither the user's own bin dirs nor Homebrew's
   ``/opt/homebrew/bin`` (Apple Silicon) / ``/usr/local/bin`` (Intel) are on PATH.
   ``which()`` prepends both families so the tools are found even under a double-click.
   P93: the USER-SCOPED dirs come first, because user-scoped is the default install target
   (docs/INSTALL-SCOPE.md). A tool the docs tell someone to install user-only has to be
   findable afterwards, or the recommended route dead-ends: ``uv python install 3.12`` puts
   ``python3.12`` in ``~/.local/bin`` (uv docs, "Installing Python"), and nvm keeps node at
   ``$NVM_DIR/versions/node/<version>/bin`` (nvm.sh ``nvm_version_path``) and is sourced per
   shell, so neither is on a double-click PATH.

Stdlib only. Pure and injectable so the selftest can simulate a macOS PATH with no real hardware.
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # repo root (tools/..)

# Homebrew bin dirs. /opt/homebrew (Apple Silicon) and /usr/local (Intel). Both are listed and
# harmless when absent; we never assume one architecture.
BREW_PREFIXES = ("/opt/homebrew/bin", "/usr/local/bin")

# P93: the user-scoped bin dirs, searched BEFORE the machine-wide ones. ~/.local/bin is where the
# uv installer puts uv and where `uv python install` puts pythonX.Y; nvm keeps each node under
# $NVM_DIR/versions/node/<version>/bin. Both are per-user by design and neither is on a
# double-click PATH. See docs/INSTALL-SCOPE.md.
USER_BIN = ".local/bin"
NVM_NODE_SUBDIR = "versions/node"

PYTHON_FLOOR = (3, 12)   # THE floor. tools/setup.py imports it; the launcher's probe string embeds it
                         # P91: validated THROUGH 3.14 (battery 13/13 on 3.12/3.13/3.14); the floor
                         # stays 3.12 for the Resolve live-control lane (vendor cap, ADR 0064).
                         # (asserted by _selftest); docs are swept against it by drift invariant 48 (P81).


def repo_root() -> Path:
    return ROOT


def venv_python(root=None):
    """The repo ``.venv`` interpreter if it exists, RUNS, and meets PYTHON_FLOOR; else None (P81).
    P80 taught the launcher to refuse an old venv; this function still handed every heavy tool to it,
    so a 3.11 venv produced a wizard on system 3.12 spawning tools on 3.11 that setup.py then refused."""
    base = Path(root) if root is not None else ROOT
    for c in (
        base / ".venv" / "bin" / "python3",
        base / ".venv" / "bin" / "python",
        base / ".venv" / "Scripts" / "python.exe",  # Windows
    ):
        if not c.exists():
            continue
        try:
            r = subprocess.run([str(c), "-c", f"import sys; sys.exit(0 if sys.version_info[:2] >= {PYTHON_FLOOR} else 1)"],
                               capture_output=True, timeout=20)
        except (OSError, subprocess.SubprocessError):
            return None          # exists but does not run (relocated framework): same as absent
        return c if r.returncode == 0 else None
    return None


def app_python(root=None) -> str:
    """The interpreter the app's heavy tools should run under: the ``.venv`` python when present,
    else the current interpreter (today's behavior, so no ``.venv`` == no change)."""
    vp = venv_python(root)
    return str(vp) if vp else sys.executable


def brew_prefixes() -> list:
    return list(BREW_PREFIXES)


def _nvm_dir(home: Path, env=None) -> Path:
    """nvm's directory: $NVM_DIR when set (nvm.sh honors it), else ~/.nvm (its README's default)."""
    env = env if env is not None else os.environ
    raw = (env.get("NVM_DIR") or "").strip()
    return Path(raw) if raw else home / ".nvm"


def user_prefixes(home=None, env=None) -> list:
    """The user-scoped bin dirs that exist, newest node first. P93: these are searched before the
    machine-wide prefixes, so a tool installed by the route this repo recommends (uv into
    ``~/.local/bin``, node via nvm) is found even under a bare double-click PATH. Returns only
    directories that actually exist, so a machine without them is unaffected. Pure/injectable:
    ``home`` and ``env`` are overridable for the selftest (no real HOME needed)."""
    env = env if env is not None else os.environ
    if home is not None:
        home = Path(home)
    else:
        raw = env.get("HOME") or env.get("USERPROFILE") or ""
        if not raw:
            return []
        home = Path(raw)
    out = []
    local_bin = home / USER_BIN
    if local_bin.is_dir():
        out.append(str(local_bin))
    node_root = _nvm_dir(home, env) / NVM_NODE_SUBDIR
    try:
        versions = [d for d in node_root.iterdir() if (d / "bin").is_dir()]
    except OSError:
        versions = []
    for d in sorted(versions, key=lambda p: _version_key(p.name), reverse=True):
        out.append(str(d / "bin"))
    return out


def _version_key(name: str) -> tuple:
    """Sort key for an nvm version dir name ('v20.11.1'), so the newest node wins. Non-numeric
    parts sort low rather than raising, since nvm also keeps aliases like 'system'."""
    parts = []
    for chunk in name.lstrip("vV").split("."):
        digits = ""
        for ch in chunk:
            if not ch.isdigit():
                break
            digits += ch
        parts.append(int(digits) if digits else -1)
    while len(parts) < 3:
        parts.append(-1)
    return tuple(parts[:3])


def augmented_path(base=None, home=None, env=None) -> str:
    """PATH string with the user-scoped bin dirs prepended FIRST and the Homebrew prefixes after,
    so ``which()`` finds both under a GUI (double-click) launch that has a bare PATH. User-scoped
    leads because user-scoped is the install default (docs/INSTALL-SCOPE.md); brew stays so an
    existing machine-wide install keeps working (using what exists is allowed, adding is not).
    ``base`` defaults to the current ``$PATH``."""
    base = base if base is not None else os.environ.get("PATH", "")
    parts = user_prefixes(home=home, env=env) + list(BREW_PREFIXES)
    if base:
        parts.append(base)
    return os.pathsep.join(parts)


def which(name, path=None):
    """``shutil.which`` with the Homebrew prefixes prepended; falls back to the bare lookup so a
    tool already on PATH is still found. Returns the resolved path string or None."""
    p = path if path is not None else augmented_path()
    return shutil.which(name, path=p) or shutil.which(name)


# Folders a desktop sync client keeps in step with the cloud: Google Drive, OneDrive and Dropbox
# for desktop on macOS 12.1+ (File Provider, under ~/Library/CloudStorage), iCloud Drive (under
# ~/Library/Mobile Documents on macOS; P101: ~/iCloud Drive, the iCloud for Windows default, or
# ~/iCloudDrive, the name earlier versions used) and a classic ~/Dropbox folder.
CLOUD_SYNCED_DIRS = (("Library", "CloudStorage"), ("Library", "Mobile Documents"), ("Dropbox",),
                     ("iCloud Drive",), ("iCloudDrive",))
# P101: OneDrive on Windows names the folder it syncs in the OneDrive environment variable; the
# variables for a personal and for a work or school account are read as well.
ONEDRIVE_ENV_VARS = ("OneDrive", "OneDriveConsumer", "OneDriveCommercial")
# P101: Google Drive for desktop on Windows serves its files on a virtual drive (G: unless another
# letter or a folder was chosen); these hidden folders sit at that drive's root.
DRIVEFS_MARKERS = (".shortcut-targets-by-id", ".file-revisions-by-id")


def _volume_root(target, ismount):
    """The mount point `target` is on: the nearest of target and its parents that ismount accepts,
    or None."""
    for candidate in (target, *target.parents):
        try:
            if ismount(candidate):
                return candidate
        except (OSError, ValueError):
            return None
    return None


def cloud_synced_root(path, home=None, env=None, ismount=None):
    """The cloud-synced folder `path` sits under, or None: one of CLOUD_SYNCED_DIRS joined to
    `home`, an absolute folder named by one of ONEDRIVE_ENV_VARS in `env` (default os.environ), or
    the root of the volume `path` is on when that root holds one of DRIVEFS_MARKERS (`ismount`,
    default os.path.ismount, finds it). The repo keeps its credential files in pipeline/user-context/, so a
    repo under one of these folders would sync them; setup and the wizard warn and point to
    tools/profile_mirror.py, which copies only the context files into the Drive hub. Paths are
    compared after resolving symlinks."""
    home = Path(home) if home is not None else Path.home()
    env = os.environ if env is None else env
    ismount = os.path.ismount if ismount is None else ismount
    try:
        target = Path(path).expanduser().resolve()
    except (OSError, RuntimeError):
        return None
    bases = [home.joinpath(*parts) for parts in CLOUD_SYNCED_DIRS]
    bases += [Path(env[name]) for name in ONEDRIVE_ENV_VARS
              if env.get(name) and Path(env[name]).is_absolute()]
    for base in bases:
        try:
            base = base.resolve()
        except (OSError, RuntimeError):
            pass
        if target == base or base in target.parents:
            return str(base)
    volume = _volume_root(target, ismount)
    if volume is not None and any(os.path.isdir(volume / name) for name in DRIVEFS_MARKERS):
        return str(volume)
    return None


def _os_name() -> str:
    """os.name, read through one function so the selftest can stand in another system."""
    return os.name


def windows_outside_home(path, home=None, osname=None) -> bool:
    """True on Windows when `path` is outside the home folder (%USERPROFILE%). A folder under the
    profile takes the profile's permissions (the user, SYSTEM and Administrators); one created
    elsewhere, such as C:\\repos, takes the drive's, which by default let the computer's other
    accounts read its files, the credential files in pipeline/user-context/ among them (os.chmod
    there sets only the read-only flag). False on other systems, and when a path cannot be
    resolved. Paths are compared after resolving symlinks, with os.path.normcase."""
    if osname is None:
        osname = _os_name()
    if osname != "nt":
        return False
    home = Path(home) if home is not None else Path.home()
    try:
        target = os.path.normcase(str(Path(path).expanduser().resolve()))
        base = os.path.normcase(str(home.resolve())).rstrip("\\/")
    except (OSError, RuntimeError):
        return False
    return not (target == base or target.startswith(base + os.sep))


def python_command(osname=None, which=None) -> str:
    """The command a person types to run this repo's scripts: on Windows `py -3` when the py
    launcher is installed (Start Creator OS Setup.bat tries it first, since `python` can be missing
    or the Microsoft Store alias), else `python`; `python3` elsewhere."""
    osname = _os_name() if osname is None else osname
    if osname != "nt":
        return "python3"
    which = shutil.which if which is None else which
    return "py -3" if which("py") else "python"


def local_commands(text: str, osname=None, which=None) -> str:
    """`text` with each `python3 tools/...` and `python3 shared/...` command written with the
    command this computer runs the repo's scripts with (python_command): `py -3` or `python` on
    Windows, where `python3` can be the Microsoft Store alias; unchanged elsewhere. A `python3`
    that is part of a longer name or path (python3.12, venv/bin/python3) is left as written."""
    command = python_command() if osname is None and which is None else python_command(osname, which)
    if command == "python3":
        return text
    import re
    return re.sub(r"(?<![\w./\\-])python3 (?=(?:tools|shared)/)", command + " ", text)



def tool_env(base=None) -> dict:
    """The environment for a Python tool of this repo whose output a caller reads: `base` (default
    os.environ) with PYTHONUTF8=1 and PYTHONIOENCODING=utf-8. On Windows a child's piped stdout
    otherwise uses the ANSI code page (often cp1252), so a title with an emoji stops the tool with
    UnicodeEncodeError; UTF-8 mode also makes that child's own pipes and default file encoding
    UTF-8. `base` is not changed."""
    env = dict(os.environ if base is None else base)
    env.update(PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    return env


def tool_io(base=None) -> dict:
    """subprocess keyword arguments for running a Python tool of this repo and reading its output
    as text: env=tool_env(base), encoding="utf-8", errors="replace". Pass them instead of
    text=True, which decodes with the locale's code page."""
    return {"env": tool_env(base), "encoding": "utf-8", "errors": "replace"}


def utf8_stdio(streams=None) -> None:
    """Write this process's stdout and stderr as UTF-8 when they are not a terminal, so a redirect
    (`> file`) or a pipe receives text with an emoji instead of a UnicodeEncodeError (on Windows
    they otherwise use the ANSI code page). A terminal is left as it is (Python writes the Windows
    console as UTF-16), and so is a stream without reconfigure (one a caller replaced).
    `streams` (default sys.stdout and sys.stderr) is for the selftest."""
    for stream in (sys.stdout, sys.stderr) if streams is None else streams:
        try:
            if stream is not None and hasattr(stream, "reconfigure") and not stream.isatty():
                stream.reconfigure(encoding="utf-8", errors="replace")
        except (OSError, ValueError, AttributeError):
            pass

# Set by the child process of the symlink control below, which must not run that control again.
_SYMLINK_CHILD = False


def _selftest() -> int:
    import tempfile
    import stat

    checks = []

    def ok(cond, msg):
        checks.append((bool(cond), msg))

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        # No .venv yet -> venv_python None, app_python is the current interpreter.
        ok(venv_python(root) is None, "venv_python None when no .venv")
        ok(app_python(root) == sys.executable, "app_python falls back to sys.executable")

        # P81: a venv is selected only when it RUNS and meets PYTHON_FLOOR.
        vbin = root / ".venv" / "bin"
        vbin.mkdir(parents=True)
        vpy = vbin / "python3"
        vpy.write_text("#!/bin/sh\nexit 127\n")   # exists but does not run usefully
        vpy.chmod(vpy.stat().st_mode | stat.S_IEXEC)
        ok(venv_python(root) is None, "a broken venv interpreter is rejected (P81 B-5)")
        vpy.unlink()

        def link_interpreter():
            try:
                vpy.symlink_to(sys.executable)     # a real interpreter
                return True
            except OSError:   # P101: Windows without Developer Mode or admin rights refuses a symlink
                return False

        real_link = Path.symlink_to

        def _refuse(self, *a, **k):
            raise OSError(1314, "A required privilege is not held by the client")
        Path.symlink_to = _refuse
        try:
            refused = link_interpreter()
        finally:
            Path.symlink_to = real_link
        ok(refused is False and not vpy.exists(), "a refused symlink to the interpreter is reported as not made")
        linked = link_interpreter()
        if not linked:
            print("  [skip] venv selection: this system cannot create a symlink to the interpreter")
        ok(linked or os.name == "nt", "the symlink to the interpreter is made (skipped on Windows only)")
        if linked and sys.version_info[:2] >= PYTHON_FLOOR:
            ok(venv_python(root) == vpy, "venv_python finds a floor-meeting .venv interpreter")
            ok(app_python(root) == str(vpy), "app_python returns .venv interpreter when present")
        elif linked:
            ok(venv_python(root) is None, "a below-floor venv interpreter is rejected (P81 B-5)")
            ok(app_python(root) == sys.executable, "app_python falls back below the floor")
        launcher = ROOT / "Start Creator OS Setup.command"
        if launcher.exists():
            ok(f"sys.version_info[:2] >= {PYTHON_FLOOR}" in launcher.read_text(encoding="utf-8"),
               "the launcher probe embeds PYTHON_FLOOR")

        # augmented_path prepends the brew prefixes ahead of the base. Injected empty home, so a
        # machine with no user-scoped dirs behaves exactly as before P93 (no regression).
        empty_home = root / "emptyhome"
        empty_home.mkdir()
        ap = augmented_path("/usr/bin:/bin", home=empty_home, env={})
        ok(ap.startswith("/opt/homebrew/bin"), "augmented_path prepends Apple-Silicon brew prefix")
        ok("/usr/local/bin" in ap and ap.endswith("/usr/bin:/bin"), "augmented_path keeps base last")
        ok(user_prefixes(home=empty_home, env={}) == [], "no user-scoped dirs -> empty prefix list")

        # P93: the user-scoped dirs this repo tells people to install into must be SEARCHED, or the
        # recommended route dead-ends (the wizard would report an nvm-installed node as missing).
        # This pin fails against the pre-P93 augmented_path, which knew only the brew prefixes.
        uhome = root / "userhome"
        (uhome / USER_BIN).mkdir(parents=True)                       # uv + uv's pythonX.Y land here
        for v in ("v18.20.4", "v20.11.1", "v9.0.0"):                 # nvm layout: versions/node/<v>/bin
            (uhome / ".nvm" / NVM_NODE_SUBDIR / v / "bin").mkdir(parents=True)
        ups = user_prefixes(home=uhome, env={})
        ok(ups and ups[0] == str(uhome / USER_BIN), "user_prefixes leads with ~/.local/bin")
        ok(Path(ups[1]).parts[-2:] == ("v20.11.1", "bin"), "user_prefixes orders nvm nodes newest first")
        ok(len(ups) == 4, "user_prefixes lists ~/.local/bin + every nvm node bin")
        uap = augmented_path("/usr/bin:/bin", home=uhome, env={})
        ok(uap.startswith(str(uhome / USER_BIN)), "augmented_path puts user-scoped dirs FIRST")
        ok(uap.index(str(uhome / USER_BIN)) < uap.index("/opt/homebrew/bin"),
           "user-scoped dirs outrank the machine-wide prefixes")
        # $NVM_DIR wins over ~/.nvm, the way nvm.sh itself resolves it.
        alt = root / "altnvm"
        (alt / NVM_NODE_SUBDIR / "v22.1.0" / "bin").mkdir(parents=True)
        alt_ups = user_prefixes(home=uhome, env={"NVM_DIR": str(alt)})
        ok(any(Path(p).parts[-2:] == ("v22.1.0", "bin") for p in alt_ups), "user_prefixes honors $NVM_DIR")
        ok(not any(".nvm" in p for p in alt_ups), "$NVM_DIR replaces the ~/.nvm default")
        # The functional pin: a node installed the user-only way is findable under a bare PATH.
        # P101: Windows finds a program by a PATHEXT suffix (.exe), not by a shebang and exec bit.
        exe = ".exe" if os.name == "nt" else ""
        same = lambda a, b: a is not None and os.path.normcase(a) == os.path.normcase(str(b))  # noqa: E731
        fake_node = uhome / ".nvm" / NVM_NODE_SUBDIR / "v20.11.1" / "bin" / ("node" + exe)
        fake_node.write_text("#!/bin/sh\n")
        fake_node.chmod(fake_node.stat().st_mode | stat.S_IEXEC)
        ok(same(which("node", path=augmented_path("", home=uhome, env={})), fake_node),
           "which() finds an nvm-installed node (the route the wizard recommends)")

        # which() finds a tool via an injected path, and via augmented_path when the tool sits in a
        # prefix-like dir we inject as base.
        fakebin = root / "fakebin"
        fakebin.mkdir()
        tool = fakebin / ("faketool" + exe)
        tool.write_text("#!/bin/sh\n")
        tool.chmod(tool.stat().st_mode | stat.S_IEXEC)
        ok(same(which("faketool", path=str(fakebin)), tool), "which() resolves via injected path")
        ok(which("definitely_not_a_real_tool_xyz") is None, "which() None for a missing tool")

    # cloud_synced_root: each synced family is named, a plain home path is not, and a folder that
    # only starts with the same letters (~/Dropbox-notes) is not inside ~/Dropbox.
    # An absolute, resolved base (on Windows a bare "/x" resolves onto the current drive).
    fake_home = Path(tempfile.gettempdir()).resolve() / "nonexistent-home-for-selftest"
    ok(all(cloud_synced_root(fake_home.joinpath(*p, "x", "repo"), home=fake_home, env={})
           == str(fake_home.joinpath(*p)) for p in CLOUD_SYNCED_DIRS),
       "cloud_synced_root names Google Drive/OneDrive (CloudStorage), iCloud Drive and Dropbox")
    ok(all(cloud_synced_root(fake_home / name / "repo", home=fake_home, env={}) == str(fake_home / name)
           for name in ("iCloud Drive", "iCloudDrive")),
       "cloud_synced_root names the iCloud for Windows folder, under its current and earlier name")
    ok(cloud_synced_root(fake_home / "CreatorOS", home=fake_home, env={}) is None
       and cloud_synced_root(fake_home / "Dropbox-notes" / "repo", home=fake_home, env={}) is None,
       "cloud_synced_root is None for a home-folder path and for a look-alike folder name")
    # P101, Windows: the folder each OneDrive variable names (the variables are read on any OS,
    # so this runs here too); a variable that is unset, empty or not an absolute path names none.
    od = fake_home / "OneDrive - Fictional School"
    ok(all(cloud_synced_root(od / "repo", home=fake_home, env={name: str(od)}) == str(od)
           for name in ("OneDrive", "OneDriveConsumer", "OneDriveCommercial")),
       "cloud_synced_root names the folder in OneDrive, OneDriveConsumer and OneDriveCommercial")
    ok(cloud_synced_root(od / "repo", home=fake_home, env={}) is None
       and cloud_synced_root(Path.cwd() / "repo", home=fake_home, env={"OneDrive": ""},
                             ismount=lambda p: False) is None
       and cloud_synced_root(Path.cwd() / "repo", home=fake_home, env={"OneDrive": "."},
                             ismount=lambda p: False) is None
       and cloud_synced_root(fake_home / "CreatorOS", home=fake_home, env={"OneDrive": str(od)}) is None,
       "cloud_synced_root names no OneDrive folder for an unset, empty or relative variable, or "
       "for a path outside the folder")
    saved_od = os.environ.get("OneDrive")
    os.environ["OneDrive"] = str(od)
    try:
        from_environ = cloud_synced_root(od / "repo", home=fake_home)
    finally:
        if saved_od is None:
            os.environ.pop("OneDrive", None)
        else:
            os.environ["OneDrive"] = saved_od
    ok(from_environ == str(od), "cloud_synced_root reads the OneDrive variables from os.environ by default")
    # P101, Windows: the root of the volume a path is on, when it holds one of Google Drive for
    # desktop's hidden folders. The mount points are stood in for; the folders are real.
    ok(DRIVEFS_MARKERS == (".shortcut-targets-by-id", ".file-revisions-by-id"),
       "DRIVEFS_MARKERS names Drive for desktop's two hidden root folders")
    with tempfile.TemporaryDirectory() as td:
        base = Path(td).resolve()
        vol = base / "G"
        (vol / "My Drive" / "Creator OS").mkdir(parents=True)
        (vol / ".shortcut-targets-by-id").mkdir()
        vol2 = base / "V2"
        (vol2 / "Work").mkdir(parents=True)
        (vol2 / ".file-revisions-by-id").mkdir()
        plain = base / "D"
        (plain / "Work").mkdir(parents=True)
        for name in (".shortcut-targets-by-id", ".file-revisions-by-id"):
            (plain / name).write_text("a file, not the folder")
        mounts = {vol, vol2, plain}
        at = lambda p: p in mounts  # noqa: E731
        repo_on_g = vol / "My Drive" / "Creator OS" / "seo-tools"
        ok(cloud_synced_root(repo_on_g, home=fake_home, env={}, ismount=at) == str(vol)
           and cloud_synced_root(vol2 / "Work" / "seo-tools", home=fake_home, env={}, ismount=at) == str(vol2),
           "cloud_synced_root names the root of a volume that holds either Drive marker folder")
        ok(cloud_synced_root(plain / "Work" / "seo-tools", home=fake_home, env={}, ismount=at) is None
           and cloud_synced_root(repo_on_g, home=fake_home, env={}, ismount=lambda p: False) is None,
           "cloud_synced_root names no volume whose root lacks the marker folders, or when no mount "
           "point is found")
        mounts.add(vol / "My Drive")
        ok(cloud_synced_root(repo_on_g, home=fake_home, env={}, ismount=at) is None,
           "cloud_synced_root reads the markers at the nearest mount point only")
        mounts.discard(vol / "My Drive")
        raised = []
        for exc in (OSError("volume path"), ValueError("embedded null")):
            def failing(p, exc=exc):
                if p == repo_on_g:
                    raise exc
                return p in mounts
            try:
                raised.append(cloud_synced_root(repo_on_g, home=fake_home, env={}, ismount=failing))
            except (OSError, ValueError) as err:
                raised.append(repr(err))
        ok(raised == [None, None],
           f"a mount check that raises OSError or ValueError names no folder and does not raise: {raised}")
        real_ismount = os.path.ismount
        os.path.ismount = at
        try:
            from_default = cloud_synced_root(repo_on_g, home=fake_home, env={})
        finally:
            os.path.ismount = real_ismount
        ok(from_default == str(vol), "cloud_synced_root finds mount points with os.path.ismount by default")
    # The command a person types to run the scripts: py -3 or python on Windows, python3 elsewhere.
    ok(python_command("posix", which=lambda n: "/x/py") == "python3"
       and python_command("nt", which=lambda n: "C:\\py.exe" if n == "py" else None) == "py -3"
       and python_command("nt", which=lambda n: None) == "python",
       "python_command is py -3 with the py launcher on Windows, else python; python3 elsewhere")
    sample = ("run python3 tools/setup.py, then python3 shared/cache/cache.py --build; python3.12 tools/x.py, "
              "venv/bin/python3 tools/x.py, C:\\Py\\python3 tools/x.py, my-python3 tools/x.py and python3 -m pip stay")
    with_py = lambda n: "C:\\py.exe" if n == "py" else None  # noqa: E731
    ok(local_commands(sample, "nt", with_py)
       == ("run py -3 tools/setup.py, then py -3 shared/cache/cache.py --build; python3.12 tools/x.py, "
           "venv/bin/python3 tools/x.py, C:\\Py\\python3 tools/x.py, my-python3 tools/x.py and python3 -m pip stay")
       and local_commands(sample, "nt", lambda n: None).count("python tools/") == 1
       and local_commands(sample, "posix", with_py) == sample,
       "local_commands writes python3 tools/ and shared/ commands as py -3 or python on Windows only")
    real_os_lc, real_which_lc = globals()["_os_name"], shutil.which
    globals()["_os_name"] = lambda: "nt"
    shutil.which = lambda name, *a, **k: "C:\\py.exe" if name == "py" else None
    try:
        lc_default = local_commands("run python3 tools/setup.py")
    finally:
        globals()["_os_name"], shutil.which = real_os_lc, real_which_lc
    ok(lc_default == "run py -3 tools/setup.py",
       "with no system given, local_commands reads this computer's system and its py launcher")
    real_which, real_os_name = shutil.which, globals()["_os_name"]
    shutil.which = lambda name, *a, **k: "C:\\py.exe" if name == "py" else None
    try:
        default_which = python_command("nt")
        globals()["_os_name"] = lambda: "nt"
        default_nt = python_command()
        globals()["_os_name"] = lambda: "posix"
        default_posix = python_command()
    finally:
        shutil.which, globals()["_os_name"] = real_which, real_os_name
    ok(default_which == "py -3" and default_nt == "py -3" and default_posix == "python3"
       and _os_name() == os.name
       and python_command() == ("python3" if os.name != "nt" else ("py -3" if shutil.which("py") else "python")),
       "python_command reads os.name (through _os_name) and shutil.which by default")

    # control: run in a child process with symlinks refused, this selftest fails its symlink gate
    # under a POSIX os and skips venv selection under Windows. The child skips this control.
    if not _SYMLINK_CHILD:
        child = ("import pathlib, sys\n"
                 f"sys.path.insert(0, {str(Path(__file__).resolve().parent)!r})\n"
                 "import env_paths\n"
                 "env_paths._SYMLINK_CHILD = True\n"
                 "def refuse(self, *a, **k):\n"
                 "    raise OSError(1314, 'A required privilege is not held by the client')\n"
                 "pathlib.Path.symlink_to = refuse\n"
                 "sys.exit(env_paths._selftest())\n")
        r = subprocess.run([sys.executable, "-c", child], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=120)
        gate_failed = "[FAIL] the symlink to the interpreter is made" in r.stdout
        ok(gate_failed == (os.name != "nt") and "[skip] venv selection" in r.stdout,
           "with symlinks refused, the symlink gate fails off Windows and skips on Windows")


    # P102: a repo outside the home folder on Windows takes the drive's permissions.
    with tempfile.TemporaryDirectory() as td:
        h = Path(td).resolve() / "home"
        (h / "CreatorOS").mkdir(parents=True)
        (Path(td) / "repos" / "CreatorOS").mkdir(parents=True)
        (Path(td) / "home-other").mkdir()
        ok(windows_outside_home(Path(td) / "repos" / "CreatorOS", home=h, osname="nt") is True
           and windows_outside_home(Path(td) / "home-other", home=h, osname="nt") is True,
           "on Windows a repo outside the home folder is reported, also beside it with a shared prefix")
        ok(windows_outside_home(h / "CreatorOS", home=h, osname="nt") is False
           and windows_outside_home(h, home=h, osname="nt") is False,
           "on Windows the home folder and a repo under it are not reported")
        ok(windows_outside_home(Path(td) / "repos" / "CreatorOS", home=h, osname="posix") is False,
           "on another system a repo outside the home folder is not reported")
        real_os = globals()["_os_name"]
        globals()["_os_name"] = lambda: "nt"
        try:
            read_os = windows_outside_home(Path(td) / "repos", home=h)
        finally:
            globals()["_os_name"] = real_os
        ok(read_os is True, "windows_outside_home reads _os_name() when no system is given")
    # P102: a child that prints an emoji to a pipe, with the parent's codec forced to cp1252 (what a
    # Windows pipe uses): tool_io and utf8_stdio each keep it running; without them it stops.
    text = "Restoring an armoire \U0001f3a5 (before \u2192 after, caf\u00e9)"
    cp1252 = dict(os.environ, PYTHONIOENCODING="cp1252")
    cp1252.pop("PYTHONUTF8", None)
    show = [sys.executable, "-c", "import sys; print(sys.argv[1])", text]
    env_kept = tool_env(cp1252)
    ok(env_kept["PYTHONUTF8"] == "1" and env_kept["PYTHONIOENCODING"] == "utf-8"
       and cp1252["PYTHONIOENCODING"] == "cp1252" and env_kept.get("PATH") == cp1252.get("PATH")
       and tool_io(cp1252) == {"env": env_kept, "encoding": "utf-8", "errors": "replace"},
       "tool_env sets UTF-8 over the base environment without changing it; tool_io adds the decoding")
    with_io = subprocess.run(show, capture_output=True, timeout=60, **tool_io(cp1252))
    without = subprocess.run(show, capture_output=True, timeout=60, env=cp1252, encoding="utf-8",
                             errors="replace")
    ok(with_io.returncode == 0 and with_io.stdout.strip() == text
       and without.returncode != 0 and "UnicodeEncodeError" in without.stderr,
       "with tool_io a child prints an emoji to a cp1252 pipe intact; without it the child stops "
       f"({with_io.returncode}, {without.returncode})")
    here = str(Path(__file__).resolve().parent)
    stdio = [sys.executable, "-c", "import sys; sys.path.insert(0, sys.argv[2]); import env_paths; "
             "env_paths.utf8_stdio(); print(sys.argv[1])", text, here]
    plain = [sys.executable, "-c", "import sys; print(sys.argv[1])", text]
    r_on = subprocess.run(stdio, capture_output=True, timeout=60, env=cp1252)
    r_off = subprocess.run(plain, capture_output=True, timeout=60, env=cp1252)
    ok(r_on.returncode == 0 and r_on.stdout.decode("utf-8").strip() == text and r_off.returncode != 0,
       "utf8_stdio makes a redirected stdout UTF-8, so a cp1252 pipe gets the emoji intact")

    class _Stream:
        def __init__(self, tty):
            self.tty, self.calls = tty, []

        def isatty(self):
            return self.tty

        def reconfigure(self, **kw):
            self.calls.append(kw)
    term, piped = _Stream(True), _Stream(False)
    utf8_stdio([term, piped, None, object()])
    ok(term.calls == [] and piped.calls == [{"encoding": "utf-8", "errors": "replace"}],
       "utf8_stdio leaves a terminal and a stream without reconfigure alone")
    passed = sum(1 for c, _ in checks if c)
    for c, m in checks:
        if not c:
            print(f"  [FAIL] {m}")
    print(f"env_paths selftest: {passed}/{len(checks)} checks passed")
    return 0 if passed == len(checks) else 1


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        raise SystemExit(_selftest())
    # Plain run: report what this machine resolves (handy for debugging a Mac).
    import json
    print(json.dumps({
        "sys_executable": sys.executable,
        "venv_python": str(venv_python()) if venv_python() else None,
        "app_python": app_python(),
        "brew_prefixes": brew_prefixes(),
        "which_node": which("node"),
        "which_uv": which("uv"),
    }, indent=2))
