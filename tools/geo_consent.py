#!/usr/bin/env python3
"""geo_consent.py -- unified live-network consent policy for jurisdictional overlays (P38).

Live GIS / geocoding calls (FEMA flood via geo_fetch, address geocoding via geo_geocode) are
DEFAULT-ON but ASK-FIRST, once per session. The first live call in a session surfaces a consent
prompt; NOTHING is fetched until a human grants it; a grant covers the rest of that session; a
denial -- or no interactive prompt available at all (e.g. headless / cron) -- falls back with NO
network call. This preserves the "never a surprise network call" guarantee while letting the
feature default on.

Two config keys drive it:
  capabilities.jurisdictional_overlay        -- the master feature switch (must be on for any live call)
  capabilities.jurisdictional_overlay_live   -- the live consent policy:
      {"enabled": false}                        -> mode 'never'  (explicit off: refuse, never ask)
      {"enabled": true, "mode": "ask",
       "cadence": "per_session"}                -> ask-first (the shipped default)
      {"mode": "always"}                        -> proceed without asking (deployments that opt in)

The caller owns the per-session grant: pass the SAME mutable `session` dict across calls in a
session and gate() records the grant into it, so the human is asked at most once per session.
"""
from __future__ import annotations

ASK, ALWAYS, NEVER = "ask", "always", "never"


def master_on(config):
    """True if the master feature switch capabilities.jurisdictional_overlay is enabled."""
    caps = (config or {}).get("capabilities", {})
    v = caps.get("jurisdictional_overlay")
    if isinstance(v, dict):
        return bool(v.get("enabled"))
    return bool(v)


def live_policy(config):
    """Return the normalized live consent policy {mode, cadence} from config.

    Absent key -> ask/per_session (default-on, ask-first). A bare bool or a legacy {enabled: bool}
    maps true->always, false->never so pre-P38 configs and tests keep working. An explicit mode
    always wins."""
    caps = (config or {}).get("capabilities", {})
    lv = caps.get("jurisdictional_overlay_live")
    if lv is None:
        return {"mode": ASK, "cadence": "per_session"}
    if isinstance(lv, bool):
        return {"mode": ALWAYS if lv else NEVER, "cadence": "per_session"}
    if isinstance(lv, dict):
        if lv.get("mode"):
            return {"mode": lv.get("mode"), "cadence": lv.get("cadence", "per_session")}
        if "enabled" in lv:
            return {"mode": ALWAYS if lv.get("enabled") else NEVER,
                    "cadence": lv.get("cadence", "per_session")}
    return {"mode": ASK, "cadence": "per_session"}


def consent_prompt(purpose, service):
    """The human-facing consent question. Discloses that data leaves the machine to a public .gov
    service and that nothing is stored or sent to GitHub."""
    return (f"Allow a one-time online lookup for {purpose} this session? Your "
            f"{('address' if 'geocod' in purpose else 'location')} is sent to a public government "
            f"service ({service}); nothing is stored or sent to GitHub. (yes / no)")


def gate(config, purpose, service="a public .gov service", session=None, asker=None):
    """Decide whether a live network call for `purpose` may proceed.

    session : caller-owned mutable dict tracking per-session grants; gate() sets session['granted_live']
              on a successful ask so the human is asked at most once per session.
    asker   : optional callable(prompt:str)->bool that obtains human consent. None means no
              interactive prompt is available (headless): gate refuses with 'consent_required' and
              makes no call.

    Returns {proceed, code, reason, asked, prompt}. code is one of:
      feature_off | policy_off | consent_required | declined | ok
    Only code == 'ok' with proceed True permits a network call."""
    if not master_on(config):
        return {"proceed": False, "code": "feature_off", "asked": False,
                "reason": "jurisdictional_overlay is off; enable the feature to use live lookups"}
    pol = live_policy(config)
    if pol["mode"] == NEVER:
        return {"proceed": False, "code": "policy_off", "asked": False,
                "reason": "live network is off (jurisdictional_overlay_live); using cached / "
                          "user-supplied data only, nothing fetched"}
    if pol["mode"] == ALWAYS:
        return {"proceed": True, "code": "ok", "asked": False,
                "reason": "live policy: always (consent pre-granted by config)"}
    # mode == ASK
    sess = session if session is not None else {}
    if pol["cadence"] == "per_session" and sess.get("granted_live"):
        return {"proceed": True, "code": "ok", "asked": False,
                "reason": "live consent already granted this session"}
    prompt = consent_prompt(purpose, service)
    if asker is None:
        return {"proceed": False, "code": "consent_required", "asked": False, "prompt": prompt,
                "reason": "live consent required and no interactive prompt is available; grant "
                          "consent or supply coordinates / cached data. Nothing was fetched."}
    try:
        granted = bool(asker(prompt))
    except Exception:  # noqa: BLE001  -- a failed prompt is treated as a refusal, never a call
        granted = False
    if granted and pol["cadence"] == "per_session":
        sess["granted_live"] = True
    return {"proceed": granted, "code": "ok" if granted else "declined", "asked": True,
            "prompt": prompt, "reason": "consent granted" if granted else "consent declined"}


# ---- selftest ----------------------------------------------------------------
def selftest():
    checks = []

    def ok(name, cond):
        checks.append((name, bool(cond)))

    ON = {"capabilities": {"jurisdictional_overlay": {"enabled": True}}}
    OFF = {"capabilities": {"jurisdictional_overlay": {"enabled": False}}}

    # master off -> feature_off, never proceeds
    d = gate(OFF, "a flood lookup", session={}, asker=lambda p: True)
    ok("master off -> feature_off, no proceed", d["code"] == "feature_off" and d["proceed"] is False)

    # policy never (legacy enabled:false) -> policy_off, no ask
    cfg_never = {"capabilities": {"jurisdictional_overlay": {"enabled": True},
                                  "jurisdictional_overlay_live": {"enabled": False}}}
    d = gate(cfg_never, "a flood lookup", session={}, asker=lambda p: (_ for _ in ()).throw(AssertionError("must not ask")))
    ok("policy never -> policy_off, never asks", d["code"] == "policy_off" and d["asked"] is False)

    # ask + no asker (headless) -> consent_required, no proceed, carries prompt
    d = gate(ON, "address geocoding", session={}, asker=None)
    ok("ask + no asker -> consent_required, no proceed", d["code"] == "consent_required" and d["proceed"] is False)
    ok("consent_required carries a prompt", isinstance(d.get("prompt"), str) and "yes / no" in d["prompt"])

    # ask + asker declines -> declined, no grant recorded
    sess = {}
    d = gate(ON, "a flood lookup", session=sess, asker=lambda p: False)
    ok("ask + decline -> declined, no proceed", d["code"] == "declined" and d["proceed"] is False)
    ok("decline records no session grant", sess.get("granted_live") is None)

    # ask + asker grants -> ok, and grant is recorded for the session
    sess = {}
    d = gate(ON, "a flood lookup", session=sess, asker=lambda p: True)
    ok("ask + grant -> ok, proceeds", d["code"] == "ok" and d["proceed"] is True and d["asked"] is True)
    ok("grant recorded in session", sess.get("granted_live") is True)

    # second call same session -> proceeds WITHOUT asking again (asker would raise if called)
    d = gate(ON, "a flood lookup", session=sess, asker=lambda p: (_ for _ in ()).throw(AssertionError("must not re-ask")))
    ok("granted session -> proceeds without re-asking", d["proceed"] is True and d["asked"] is False)

    # mode always -> proceeds with no ask
    cfg_always = {"capabilities": {"jurisdictional_overlay": {"enabled": True},
                                   "jurisdictional_overlay_live": {"mode": "always"}}}
    d = gate(cfg_always, "a flood lookup", session={}, asker=lambda p: (_ for _ in ()).throw(AssertionError("must not ask")))
    ok("mode always -> ok, no ask", d["code"] == "ok" and d["proceed"] is True and d["asked"] is False)

    # policy normalization
    ok("default policy is ask/per_session", live_policy({}) == {"mode": "ask", "cadence": "per_session"})
    ok("legacy enabled:true -> always", live_policy(
        {"capabilities": {"jurisdictional_overlay_live": {"enabled": True}}})["mode"] == "always")

    passed = sum(1 for _, c in checks if c)
    for name, c in checks:
        print(f"  [{'ok' if c else 'FAIL'}] {name}")
    total = len(checks)
    print(f"selftest: {'PASS' if passed == total else 'FAIL'} ({passed} of {total} checks)")
    return 0 if passed == total else 1


def main(argv):
    if "--selftest" in argv:
        return selftest()
    print(__doc__)
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main(sys.argv[1:]))
