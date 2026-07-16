"""Package entry point so the dispatch-gate selftest is runnable.

Run from the repo root with tools/ on the path:
    PYTHONPATH=tools python3 -m publishing --selftest

Exercises the P57 F2/F8 defense-in-depth gate in dispatch() (flag-off -> gated,
unconfirmed -> refused, unknown platform -> ValueError). Zero network.
"""
import sys

from publishing import _selftest

if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(_selftest())
    print("usage: PYTHONPATH=tools python3 -m publishing --selftest")
    sys.exit(2)
