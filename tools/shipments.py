#!/usr/bin/env python3
"""
Creator OS shipment tracking (P35).

Turns a tracking number into a normalized shipment status + a delivered_at anchor that starts a deal's
backwards-planning clock, or accepts the same record entered manually. Live tracking is an OPTIONAL,
flag-gated aggregator connector (EasyPost default, Ship24 alternative): the API key is read from the
environment only (never persisted or logged), the fetch is a stdlib urllib poll honoring the env proxy +
CA bundle (no webhook, no inbound surface). Manual entry uses the identical schema, so the planning clock
reads delivered_at the same way regardless of source. See shared/tasks-engine.md.

Usage:
  python3 tools/shipments.py --selftest
  python3 tools/shipments.py fetch --tracking 1Z... [--carrier ups] [--provider easypost|ship24]
  python3 tools/shipments.py manual --tracking 1Z... --carrier ups --status delivered --delivered-at 2026-08-03
"""
import argparse
import base64
import json
import os
import ssl
import sys
import urllib.request
from pathlib import Path

ROOT = Path(os.environ.get("CREATOR_OS_ROOT", str(Path(__file__).resolve().parent.parent)))
CA_BUNDLE = os.environ.get("REQUESTS_CA_BUNDLE") or "/root/.ccr/ca-bundle.crt"
USER_AGENT = "creator-os-shipments/1.0"

BOUNDARY = ("SHIPMENT STATUS FROM THE CARRIER OR YOUR ENTRY. The delivered date anchors backwards-planning; "
            "verify it against the actual product receipt. Nothing is billed or scheduled automatically.")

# Canonical status enum (EasyPost's vocabulary; every other aggregator maps onto it).
CANONICAL = {"pre_transit", "in_transit", "out_for_delivery", "delivered", "available_for_pickup",
             "returned", "exception", "cancelled", "unknown"}

_EASYPOST_MAP = {
    "pre_transit": "pre_transit", "in_transit": "in_transit", "out_for_delivery": "out_for_delivery",
    "delivered": "delivered", "available_for_pickup": "available_for_pickup",
    "return_to_sender": "returned", "failure": "exception", "error": "exception",
    "cancelled": "cancelled", "unknown": "unknown",
}
_SHIP24_MAP = {
    "InfoReceived": "pre_transit", "InTransit": "in_transit", "OutForDelivery": "out_for_delivery",
    "Delivered": "delivered", "AvailableForPickup": "available_for_pickup", "Exception": "exception",
    "FailedAttempt": "exception", "Expired": "exception", "Pending": "unknown",
}


def normalize_status(raw, provider="easypost"):
    if not raw:
        return "unknown"
    mapping = _EASYPOST_MAP if provider == "easypost" else _SHIP24_MAP
    return mapping.get(raw, mapping.get(str(raw).lower(), "unknown"))


def _delivered_anchor(checkpoints):
    """delivered_at comes ONLY from the delivered checkpoint's timestamp, never from est_delivery."""
    for c in checkpoints:
        if c.get("status") == "delivered" and c.get("timestamp"):
            return c["timestamp"]
    return None


def parse_easypost(payload, tracking_number):
    tracker = payload.get("tracker", payload)
    checkpoints = []
    for d in tracker.get("tracking_details", []) or []:
        loc = d.get("tracking_location") or {}
        checkpoints.append({
            "status": normalize_status(d.get("status"), "easypost"),
            "status_detail": d.get("status_detail"), "message": d.get("message"),
            "timestamp": d.get("datetime"),
            "location": {"city": loc.get("city"), "state": loc.get("state"),
                         "country": loc.get("country"), "zip": loc.get("zip")},
            "source": "carrier",
        })
    return {
        "tracking_number": tracking_number, "carrier": tracker.get("carrier"),
        "carrier_detected": tracker.get("carrier") is not None,
        "status": normalize_status(tracker.get("status"), "easypost"),
        "status_detail": tracker.get("status_detail"),
        "est_delivery": tracker.get("est_delivery_date"),
        "delivered_at": _delivered_anchor(checkpoints), "checkpoints": checkpoints,
        "source": "easypost", "source_ref": tracker.get("id"), "raw_last_synced_at": None,
    }


def parse_ship24(payload, tracking_number):
    data = (payload.get("data") or {}).get("trackings") or []
    node = data[0] if data else {}
    shipment = node.get("shipment") or {}
    tracker = node.get("tracker") or {}
    checkpoints = []
    for e in node.get("events", []) or []:
        loc = {"city": e.get("location"), "state": None, "country": e.get("courierCode"), "zip": None}
        checkpoints.append({
            "status": normalize_status(e.get("statusMilestone"), "ship24"),
            "status_detail": e.get("statusCode"), "message": e.get("status"),
            "timestamp": e.get("occurrenceDatetime"), "location": loc, "source": "carrier",
        })
    return {
        "tracking_number": tracking_number, "carrier": tracker.get("courierCode"),
        "carrier_detected": bool(tracker.get("courierCode")),
        "status": normalize_status(shipment.get("statusMilestone"), "ship24"),
        "status_detail": shipment.get("statusCode"),
        "est_delivery": (shipment.get("delivery") or {}).get("estimatedDeliveryDate"),
        "delivered_at": _delivered_anchor(checkpoints), "checkpoints": checkpoints,
        "source": "ship24", "source_ref": tracker.get("trackerId"), "raw_last_synced_at": None,
    }


def manual_shipment(tracking_number=None, carrier=None, status="unknown", delivered_at=None,
                    est_delivery=None, note=None, source_ref=None, deal_id=None):
    if status not in CANONICAL:
        return {"error": f"status '{status}' not one of {sorted(CANONICAL)}"}
    checkpoints = []
    if note or status:
        checkpoints.append({"status": status, "status_detail": None, "message": note,
                            "timestamp": delivered_at or est_delivery,
                            "location": {"city": None, "state": None, "country": None, "zip": None},
                            "source": "manual"})
    return {
        "tracking_number": tracking_number, "carrier": carrier, "carrier_detected": False,
        "status": status, "status_detail": None, "est_delivery": est_delivery,
        "delivered_at": delivered_at if status == "delivered" else None,
        "checkpoints": checkpoints, "source": "manual",
        "source_ref": source_ref, "raw_last_synced_at": None, "deal_id": deal_id,
    }


def planning_anchor(shipment):
    """The immutable backwards-planning anchor. delivered_at once delivered; otherwise a clearly-labeled
    provisional estimate off est_delivery (never confused with the real event)."""
    if shipment.get("delivered_at"):
        return {"anchor": shipment["delivered_at"], "provisional": False, "basis": "delivered_checkpoint"}
    if shipment.get("est_delivery"):
        return {"anchor": None, "provisional": True, "estimate": shipment["est_delivery"],
                "note": "estimated only; the clock starts when the product is actually received"}
    return {"anchor": None, "provisional": True, "estimate": None, "note": "no delivery signal yet"}


# ── live fetch (poll; stdlib urllib honoring env proxy + CA bundle; key from env only) ──
def _http_get_json(url, headers, data=None, timeout=15):
    ctx = ssl.create_default_context()
    if os.path.exists(CA_BUNDLE):
        try:
            ctx.load_verify_locations(CA_BUNDLE)
        except Exception:  # noqa: BLE001
            pass
    body = json.dumps(data).encode("utf-8") if data is not None else None
    req = urllib.request.Request(url, data=body, headers=headers, method="POST" if body else "GET")
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
        return json.loads(r.read().decode("utf-8"))


def _live_get(provider, tracking_number, carrier, key):
    if provider == "easypost":
        auth = base64.b64encode((key + ":").encode()).decode()
        headers = {"Authorization": "Basic " + auth, "Content-Type": "application/json",
                   "User-Agent": USER_AGENT}
        tracker = {"tracking_code": tracking_number}
        if carrier:
            tracker["carrier"] = carrier
        return _http_get_json("https://api.easypost.com/v2/trackers", headers, {"tracker": tracker})
    headers = {"Authorization": "Bearer " + key, "Content-Type": "application/json", "User-Agent": USER_AGENT}
    payload = {"trackingNumber": tracking_number}
    if carrier:
        payload["courierCode"] = [carrier]
    return _http_get_json("https://api.ship24.com/public/v1/trackers/track", headers, payload)


def _env_key(provider):
    return os.environ.get("EASYPOST_API_KEY" if provider == "easypost" else "SHIP24_API_KEY")


def fetch(tracking_number, carrier=None, provider="easypost", getter=None):
    """Poll the aggregator and return a normalized shipment. The key is read from the environment only. With
    no key and no injected getter, returns a config gap (and points to manual entry), never a network call."""
    getter = getter or _live_get
    live = getter is _live_get
    key = _env_key(provider) if live else "test"
    if live and not key:
        env = "EASYPOST_API_KEY" if provider == "easypost" else "SHIP24_API_KEY"
        return {"shipment": None, "error": f"no {provider} API key",
                "hint": f"set {env} in the environment, or enter the shipment manually", "boundary": BOUNDARY}
    try:
        payload = getter(provider, tracking_number, carrier, key)
    except Exception as exc:  # noqa: BLE001
        return {"shipment": None, "error": f"{type(exc).__name__}: {str(exc)[:160]}", "boundary": BOUNDARY}
    ship = parse_easypost(payload, tracking_number) if provider == "easypost" else parse_ship24(payload, tracking_number)
    return {"shipment": ship, "boundary": BOUNDARY}


def selftest():
    failures = []

    ran = [0]
    def check(name, cond):
        ran[0] += 1
        if not cond:
            failures.append(name)

    check("norm-ep-return", normalize_status("return_to_sender", "easypost") == "returned")
    check("norm-ep-failure", normalize_status("failure", "easypost") == "exception")
    check("norm-ship24-info", normalize_status("InfoReceived", "ship24") == "pre_transit")
    check("norm-unknown", normalize_status("weird thing", "easypost") == "unknown")

    ep_payload = {"tracker": {
        "id": "trk_1", "carrier": "USPS", "status": "delivered", "est_delivery_date": "2026-08-05",
        "tracking_details": [
            {"status": "in_transit", "datetime": "2026-08-03T14:00:00Z",
             "tracking_location": {"city": "Portland", "state": "OR", "country": "US", "zip": "97218"}},
            {"status": "delivered", "datetime": "2026-08-04T10:12:00Z",
             "tracking_location": {"city": "Seattle", "state": "WA", "country": "US", "zip": "98101"}},
        ]}}
    ship = parse_easypost(ep_payload, "9400110898825022579493")
    check("ep-status", ship["status"] == "delivered")
    check("ep-delivered-anchor", ship["delivered_at"] == "2026-08-04T10:12:00Z")
    check("ep-anchor-not-est", ship["delivered_at"] != ship["est_delivery"])
    check("ep-checkpoints", len(ship["checkpoints"]) == 2 and ship["checkpoints"][0]["status"] == "in_transit")

    anchor = planning_anchor(ship)
    check("anchor-delivered", anchor["anchor"] == "2026-08-04T10:12:00Z" and anchor["provisional"] is False)
    in_transit = {"delivered_at": None, "est_delivery": "2026-08-09"}
    check("anchor-provisional", planning_anchor(in_transit)["provisional"] is True)

    man = manual_shipment(tracking_number="1Z999", carrier="ups", status="delivered",
                          delivered_at="2026-08-03", note="left at front desk")
    check("manual-delivered", man["delivered_at"] == "2026-08-03" and man["source"] == "manual")
    check("manual-not-delivered-no-anchor", manual_shipment(status="in_transit", est_delivery="2026-08-09")["delivered_at"] is None)
    check("manual-bad-status", "error" in manual_shipment(status="teleported"))

    # injected getter (no network): fetch returns a normalized shipment
    got = fetch("9400110898825022579493", provider="easypost",
                getter=lambda p, tn, c, k: ep_payload)
    check("fetch-injected", got["shipment"]["status"] == "delivered")

    # no-key live path returns a config gap, never a network call (only when the env key is absent)
    if not _env_key("easypost"):
        res = fetch("1Z999", provider="easypost")
        check("fetch-no-key", res["shipment"] is None and "error" in res)
    else:
        check("fetch-no-key", True)

    n = ran[0]
    print(f"selftest: {'PASS' if not failures else 'FAIL'} ({n - len(failures)} of {n} checks)")
    if failures:
        print("failed:", ", ".join(failures))
        return 1
    return 0


def main(argv):
    ap = argparse.ArgumentParser(description="Creator OS shipment tracking")
    ap.add_argument("--selftest", action="store_true")
    sub = ap.add_subparsers(dest="cmd")
    p = sub.add_parser("fetch")
    p.add_argument("--tracking", required=True); p.add_argument("--carrier")
    p.add_argument("--provider", default="easypost", choices=["easypost", "ship24"])
    p = sub.add_parser("manual")
    p.add_argument("--tracking"); p.add_argument("--carrier"); p.add_argument("--status", default="unknown")
    p.add_argument("--delivered-at"); p.add_argument("--est-delivery"); p.add_argument("--note")
    args = ap.parse_args(argv)
    if args.selftest:
        return selftest()
    if args.cmd == "fetch":
        print(json.dumps(fetch(args.tracking, args.carrier, args.provider), indent=2))
        return 0
    if args.cmd == "manual":
        print(json.dumps(manual_shipment(args.tracking, args.carrier, args.status,
                                         args.delivered_at, args.est_delivery, args.note), indent=2))
        return 0
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
