#!/usr/bin/env python3
"""Creator OS scoop cache, L2: optional offline semantic recall.

Off by default. It activates only when the optional backend (a local vector index) is installed and
the user has granted consent. Absent or declined, it transparently falls back to the L1 keyword cache
and reports the gap; it never fabricates a paraphrase match. Keyword search is always available.

Usage:
  python3 shared/cache/semantic.py --status
  python3 shared/cache/semantic.py --search "adding character to a rental" --k 5
"""
import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def backend_available():
    try:
        import sqlite_vec  # noqa: F401

        return True
    except Exception:
        return False


def consent_granted():
    # Consent is recorded out of band (a future profile wizard). Default is off.
    flag = HERE / "semantic-consent.local"
    return flag.exists()


def status():
    print(f"L2 backend installed: {'yes' if backend_available() else 'no'}")
    print(f"consent granted:      {'yes' if consent_granted() else 'no'}")
    if not (backend_available() and consent_granted()):
        print("L2 is inactive; semantic.search() falls back to L1 keyword search and says so.")
    return 0


def search(q, k):
    if backend_available() and consent_granted():
        print("L2 active path is not built in this scaffold; falling back to L1.")
    print("L2 inactive: falling back to L1 keyword search. Run:")
    print(f'  python3 shared/cache/cache.py --query "{q}" --limit {k}')
    return 0


def main(argv):
    ap = argparse.ArgumentParser(description="Creator OS scoop cache L2 (optional)")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--search")
    ap.add_argument("--k", type=int, default=5)
    args = ap.parse_args(argv)
    if args.status:
        return status()
    if args.search:
        return search(args.search, args.k)
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
