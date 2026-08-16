#!/usr/bin/env python3
"""Creator OS version registry.

Keeps the ecosystem version consistent across VERSION, versions.json, and
.claude-plugin/plugin.json.

Usage:
  python3 tools/version.py --list     # show versions
  python3 tools/version.py --check    # exit 0 if consistent, 1 if drift
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def read_versions():
    version_file = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    versions_json = json.loads((ROOT / "versions.json").read_text(encoding="utf-8"))
    plugin = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    return version_file, versions_json, plugin


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    version_file, versions_json, plugin = read_versions()
    ecosystem = versions_json.get("ecosystem")
    if "--list" in argv:
        print(f"VERSION                       {version_file}")
        print(f"versions.json ecosystem       {ecosystem}")
        print(f".claude-plugin/plugin.json    {plugin.get('version')}")
        print(f"skills tracked                {len(versions_json.get('skills', {}))}")
        print(f"engines tracked               {len(versions_json.get('engines', {}))}")
        return 0
    if "--check" in argv:
        problems = []
        if version_file != ecosystem:
            problems.append(f"VERSION ({version_file}) != versions.json ecosystem ({ecosystem})")
        if plugin.get("version") != ecosystem:
            problems.append(
                f"plugin.json version ({plugin.get('version')}) != ecosystem ({ecosystem})"
            )
        # P74: this check reported "consistent" while marketplace.json disagreed in TWO places,
        # because it only ever read three of the five locations that carry the version. The drift
        # guard caught it, which means the two guards disagreed about what consistency means --
        # and the release preconditions trusted the narrower one.
        mkt_path = ROOT / ".claude-plugin" / "marketplace.json"
        if mkt_path.exists():
            try:
                mkt = json.loads(mkt_path.read_text(encoding="utf-8"))
            except ValueError as exc:
                problems.append(f"marketplace.json unreadable ({exc})")
            else:
                mkt_meta = (mkt.get("metadata") or {}).get("version")
                if mkt_meta != ecosystem:
                    problems.append(
                        f"marketplace.json metadata.version ({mkt_meta}) != ecosystem ({ecosystem})")
                for entry in mkt.get("plugins") or []:
                    if entry.get("version") != ecosystem:
                        problems.append(
                            f"marketplace.json plugin {entry.get('name')!r} version "
                            f"({entry.get('version')}) != ecosystem ({ecosystem})")
        if problems:
            print("VERSION CHECK: drift")
            for item in problems:
                print(f"  - {item}")
            return 1
        print(f"VERSION CHECK: consistent at {ecosystem}")
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
