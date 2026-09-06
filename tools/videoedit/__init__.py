"""Creator OS video-editing bridge (P22).

Two lanes over one neutral core (the edit-package, see shared/videoedit-engine.md):

  - Lane A, file interchange (universal, any OS, always available): fcpxml + otio_core. Building
    and parsing interchange files does not launch or script an app, so it works even while the
    master gate `video_editing_enabled` is off.
  - Lane B, live app control (gated): resolve / compressor / commandpost. Every live method is a
    stub that raises NotImplementedError until `video_editing_enabled` (+ the relevant feature/lane
    flag) is on and a real implementation lands. This mirrors tools/publishing/.

`dispatch(target, action, **kwargs)` routes an APP-DRIVING action to its adapter after checking the
gate; file operations (fcpxml.build/parse/validate, otio_core.normalize/merge) are imported and
called directly and are never gated.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from . import fcpxml, otio_core, preflight  # noqa: E402,F401
from . import resolve, compressor, commandpost  # noqa: E402

import videoedit_validate as gate  # noqa: E402

# App-driving targets and the feature flag each requires.
_TARGET_FEATURE = {
    "resolve": "resolve_scripting",
    "compressor": "compressor_presets",
    "commandpost": "commandpost_macros",
}
_TARGETS = {"resolve": resolve, "compressor": compressor, "commandpost": commandpost}


def dispatch(target: str, action: str, config: dict | None = None, **kwargs):
    """Run an app-driving action after the gate passes; raises with a clear reason otherwise."""
    feature = _TARGET_FEATURE.get(target)
    if feature is None:
        raise ValueError(f"Unknown app-driving target '{target}' (expected {sorted(_TARGET_FEATURE)})")
    ok, reason = gate.realization_allowed(feature, config)
    if not ok:
        raise PermissionError(reason)
    mod = _TARGETS[target]
    fn = getattr(mod, action, None)
    if fn is None:
        raise ValueError(f"{target} has no action '{action}'")
    return fn(**kwargs)
