#!/usr/bin/env python3
"""
Creator OS construction library fetcher (user-run, fuller crawling permissions).

Downloads ONLY clearly public-domain or open-licensed construction assets (DOE Building America, OSHA
via eCFR, FEMA, CPSC, NIST/USDA-FPL, energycodes.gov, NREL BSD-3 data, Wikimedia/Wikidata) into the
gitignored local library pipeline/construction-library/, writing a per-file license manifest. It
STRUCTURALLY REFUSES copyrighted hosts (ICC, NFPA, AWC, APA, ACCA, UpCodes, and other trade-association
sources): a request to any host not on the public-domain allowlist raises PermissionError, so the tool
can never bundle copyrighted code text or figures. The offline dictionary cites those by section and
links their free viewer instead.

Network is stdlib urllib honoring the env proxy + CA bundle (mirrors tools/dependency_currency.py). It
does not write the source registry directly (that is only tools/source_currency.py); after a fetch it
prints the source_ids to mark checked.

Usage:
  python3 tools/construction_fetch.py --selftest      # offline: proves host refusal + manifest shape
  python3 tools/construction_fetch.py --list          # show the fetch plan (no network)
  python3 tools/construction_fetch.py                 # fetch all public-domain/open assets
  python3 tools/construction_fetch.py --dry-run       # check hosts + plan, no download
"""
import argparse
import hashlib
import json
import os
import ssl
import sys
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
LIBRARY = ROOT / "pipeline" / "construction-library"
CA_BUNDLE = os.environ.get("REQUESTS_CA_BUNDLE") or "/root/.ccr/ca-bundle.crt"
USER_AGENT = "creator-os-construction-fetch/1.0 (public-domain construction assets)"

# Hosts whose content is public domain or openly licensed and MAY be downloaded and cached.
ALLOWED_PD_HOSTS = {
    "basc.pnnl.gov", "www.energycodes.gov", "energycodes.gov", "www.osti.gov", "osti.gov",
    "www.ecfr.gov", "ecfr.gov", "www.osha.gov", "osha.gov", "www.fema.gov", "fema.gov",
    "www.cpsc.gov", "cpsc.gov", "www.huduser.gov", "huduser.gov", "www.fpl.fs.usda.gov",
    "fpl.fs.usda.gov", "commons.wikimedia.org", "upload.wikimedia.org", "www.wikidata.org",
    "wikidata.org", "query.wikidata.org", "raw.githubusercontent.com", "github.com",
    "www.fdacs.gov", "fdacs.gov",
}

# Hosts whose content is copyrighted (cite-and-link-only). NEVER downloaded. Refused structurally.
REFUSED_COPYRIGHT_HOSTS = {
    "codes.iccsafe.org", "up.codes", "www.nfpa.org", "nfpa.org", "awc.org", "www.awc.org",
    "apawood.org", "www.apawood.org", "acca.org", "www.acca.org", "gypsum.org", "www.gypsum.org",
    "tcnatile.com", "gobrick.com", "buildingscience.com", "www.buildingscience.com",
    "floridabuilding.org", "www.floridabuilding.org",
}

# The public-domain / open fetch plan. Each entry maps to a registered source_id for reconciliation.
FETCH_PLAN = [
    {"id": "nrel-cbes-materials", "source_id": "nrel-openstudio-standards", "license": "BSD-3",
     "filename": "nrel-cbes-materials.json",
     "url": "https://raw.githubusercontent.com/NREL/openstudio-standards/master/lib/openstudio-standards/standards/cbes/data/cbes.materials.json"},
    {"id": "nrel-cbes-constructions", "source_id": "nrel-openstudio-standards", "license": "BSD-3",
     "filename": "nrel-cbes-constructions.json",
     "url": "https://raw.githubusercontent.com/NREL/openstudio-standards/master/lib/openstudio-standards/standards/cbes/data/cbes.constructions.json"},
    {"id": "nrel-climate-zone-sets", "source_id": "nrel-openstudio-standards", "license": "BSD-3",
     "filename": "nrel-ashrae-climate-zone-sets.json",
     "url": "https://raw.githubusercontent.com/NREL/openstudio-standards/master/lib/openstudio-standards/standards/ashrae_90_1/data/ashrae_90_1.climate_zone_sets.json"},
    {"id": "doe-county-climate-zone", "source_id": "doe-energycodes-county-zone", "license": "public-domain",
     "filename": "pnnl-county-climate-zone-iecc-2021.pdf",
     "url": "https://www.osti.gov/servlets/purl/1893981"},
    {"id": "basc-insulation-by-zone", "source_id": "doe-basc-insulation-table", "license": "public-domain",
     "filename": "basc-minimum-insulation-by-zone.html",
     "url": "https://basc.pnnl.gov/information/2009-2021-iecc-and-irc-minimum-insulation-requirements-new-homes"},
]


class RefusedHostError(PermissionError):
    """Raised when a fetch targets a copyrighted or non-allowlisted host."""


def _host(url):
    return (urlparse(url).hostname or "").lower()


def check_allowed(url):
    """Structural gate: allow only public-domain/open hosts; refuse copyrighted and unknown hosts.
    Mirrors the finance._csv_rows refusal pattern so the tool cannot bundle copyrighted material."""
    host = _host(url)
    if host in REFUSED_COPYRIGHT_HOSTS:
        raise RefusedHostError(
            f"refused: {host} is a copyrighted (cite-only) source; its text and figures are never "
            f"downloaded. Cite the section and link the free viewer instead."
        )
    if host not in ALLOWED_PD_HOSTS:
        raise RefusedHostError(
            f"refused: {host} is not on the public-domain/open allowlist; only clearly PD or "
            f"open-licensed hosts may be fetched. Add it to ALLOWED_PD_HOSTS only after verifying the license."
        )
    return host


def _http_get_bytes(url, timeout=20):
    ctx = ssl.create_default_context()
    if os.path.exists(CA_BUNDLE):
        try:
            ctx.load_verify_locations(CA_BUNDLE)
        except Exception:  # noqa: BLE001
            pass
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
        return r.read()


def fetch_one(entry, getter=_http_get_bytes, write=True):
    """Fetch a single plan entry after the structural host check. Returns a manifest record."""
    check_allowed(entry["url"])  # raises RefusedHostError for copyrighted/unknown hosts
    data = getter(entry["url"])
    rec = {
        "id": entry["id"],
        "source_id": entry["source_id"],
        "license": entry["license"],
        "url": entry["url"],
        "filename": entry["filename"],
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }
    if write:
        LIBRARY.mkdir(parents=True, exist_ok=True)
        (LIBRARY / entry["filename"]).write_bytes(data)
    return rec


def fetch_all(getter=_http_get_bytes, write=True):
    manifest = {"library": str(LIBRARY.relative_to(ROOT)), "files": [], "errors": []}
    for entry in FETCH_PLAN:
        try:
            manifest["files"].append(fetch_one(entry, getter=getter, write=write))
        except RefusedHostError as exc:
            manifest["errors"].append({"id": entry["id"], "refused": True, "reason": str(exc)})
        except Exception as exc:  # noqa: BLE001
            manifest["errors"].append({"id": entry["id"], "error": f"{type(exc).__name__}: {str(exc)[:160]}"})
    if write:
        LIBRARY.mkdir(parents=True, exist_ok=True)
        (LIBRARY / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def selftest():
    failures = []

    def check(name, cond):
        if not cond:
            failures.append(name)

    # copyrighted hosts are refused structurally
    for url in ("https://codes.iccsafe.org/content/IRC2021P1",
                "https://awc.org/wp-content/uploads/AWC-DCA6.pdf",
                "https://www.nfpa.org/codes/70", "https://up.codes/codes/florida",
                "https://www.apawood.org/publications", "https://www.floridabuilding.org/bc/"):
        try:
            check_allowed(url)
            failures.append(f"not-refused:{_host(url)}")
        except RefusedHostError:
            pass

    # public-domain / open hosts pass the gate
    for url in (FETCH_PLAN[0]["url"], FETCH_PLAN[3]["url"], FETCH_PLAN[4]["url"],
                "https://commons.wikimedia.org/wiki/File:Stud_wall.svg"):
        try:
            check_allowed(url)
        except RefusedHostError:
            failures.append(f"wrongly-refused:{_host(url)}")

    # an unknown host is refused (fail closed)
    try:
        check_allowed("https://example.com/whatever.pdf")
        failures.append("unknown-host-not-refused")
    except RefusedHostError:
        pass

    # a fetch through an injected getter produces a manifest record with a license, no network, no write
    fake = fetch_one(FETCH_PLAN[0], getter=lambda u, timeout=20: b'{"materials": []}', write=False)
    check("manifest-has-license", fake.get("license") == "BSD-3")
    check("manifest-has-sha", len(fake.get("sha256", "")) == 64)
    check("manifest-has-source-id", fake.get("source_id") == "nrel-openstudio-standards")

    # fetch_all with a copyrighted entry injected is refused, not downloaded
    poisoned = list(FETCH_PLAN) + [{"id": "poison", "source_id": "x", "license": "cite-only",
                                    "filename": "poison.pdf", "url": "https://codes.iccsafe.org/x"}]
    saved = FETCH_PLAN[:]
    try:
        FETCH_PLAN.clear(); FETCH_PLAN.extend(poisoned)
        m = fetch_all(getter=lambda u, timeout=20: b"ok", write=False)
        check("poison-refused", any(e.get("id") == "poison" and e.get("refused") for e in m["errors"]))
    finally:
        FETCH_PLAN.clear(); FETCH_PLAN.extend(saved)

    n = 12
    print(f"selftest: {'PASS' if not failures else 'FAIL'} ({n - len(failures)} of {n} checks)")
    if failures:
        print("failed:", ", ".join(failures))
        return 1
    return 0


def main(argv):
    ap = argparse.ArgumentParser(description="Fetch public-domain/open construction assets (user-run)")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--list", action="store_true", help="show the fetch plan, no network")
    ap.add_argument("--dry-run", action="store_true", help="check hosts and plan without downloading")
    args = ap.parse_args(argv)

    if args.selftest:
        return selftest()
    if args.list:
        print(json.dumps({"plan": FETCH_PLAN, "library": str(LIBRARY.relative_to(ROOT)),
                          "allowed_hosts": sorted(ALLOWED_PD_HOSTS),
                          "refused_hosts": sorted(REFUSED_COPYRIGHT_HOSTS)}, indent=2))
        return 0
    if args.dry_run:
        out = []
        for e in FETCH_PLAN:
            try:
                out.append({"id": e["id"], "host": check_allowed(e["url"]), "ok": True})
            except RefusedHostError as exc:
                out.append({"id": e["id"], "ok": False, "reason": str(exc)})
        print(json.dumps({"dry_run": out}, indent=2))
        return 0

    manifest = fetch_all()
    fetched_sources = sorted({f["source_id"] for f in manifest["files"]})
    print(json.dumps(manifest, indent=2))
    if fetched_sources:
        print("\nReconcile currency (run the sanctioned writer):", file=sys.stderr)
        for sid in fetched_sources:
            print(f"  python3 tools/source_currency.py mark-checked {sid}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
