#!/usr/bin/env python3
"""Deterministic Quality Gates scorer for Creator OS.

The per-dimension judgment (0 to 5 each) is the model's. This script makes the verdict reproducible
by applying the arithmetic and thresholds from protocols/quality-gates.md:
  - release requires no dimension below 3,
  - Integrity and Safety each 4 or higher,
  - composite average 4.0 or higher,
  - Integrity or Safety at 0 to 1 is a hard fail regardless of composite.

Usage:
  echo '{"integrity":5,...,"safety":5}' | python3 scripts/score.py
  python3 scripts/score.py --demo
"""
import json
import sys

DIMENSIONS = [
    "integrity",
    "accuracy",
    "brand_alignment",
    "audience_fit",
    "governance",
    "user_intent",
    "accessibility",
    "professional_quality",
    "safety",
]
CRITICAL = ["integrity", "safety"]


def evaluate(scores):
    missing = [d for d in DIMENSIONS if d not in scores]
    if missing:
        return {"error": f"missing dimensions: {missing}"}
    unknown = sorted(k for k in scores if k not in DIMENSIONS)
    if unknown:
        return {"error": f"unknown dimensions: {unknown}; the nine dimensions are defined in "
                         "protocols/quality-gates.md"}
    try:
        vals = {d: int(scores[d]) for d in DIMENSIONS}
    except (TypeError, ValueError):
        return {"error": "all scores must be integers 0 to 5"}
    if any(v < 0 or v > 5 for v in vals.values()):
        return {"error": "all scores must be in the range 0 to 5"}

    composite = round(sum(vals.values()) / len(DIMENSIONS), 2)
    below_three = [d for d, v in vals.items() if v < 3]
    critical_floor = [d for d in CRITICAL if vals[d] < 4]
    hard_fail = [d for d in CRITICAL if vals[d] <= 1]

    reasons = []
    if hard_fail:
        reasons.append(f"critical-failure override: {', '.join(hard_fail)} scored 0 to 1")
    if below_three:
        reasons.append(f"below the floor (3): {', '.join(below_three)}")
    if critical_floor:
        reasons.append(f"Integrity/Safety below 4: {', '.join(critical_floor)}")
    if composite < 4.0:
        reasons.append(f"composite {composite} below 4.0")

    released = not reasons
    return {
        "scores": vals,
        "composite": composite,
        "released": released,
        "hard_fail": bool(hard_fail),
        "verdict": "Released" if released else "Not released",
        "reasons": reasons or ["all thresholds met"],
    }


def main(argv):
    if "--demo" in argv:
        sample = {
            "integrity": 5,
            "accuracy": 4,
            "brand_alignment": 5,
            "audience_fit": 4,
            "governance": 5,
            "user_intent": 4,
            "accessibility": 4,
            "professional_quality": 4,
            "safety": 5,
        }
        print(json.dumps(evaluate(sample), indent=2))
        return 0
    raw = sys.stdin.read().strip()
    if not raw:
        print(__doc__)
        return 2
    try:
        scores = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(json.dumps({"error": f"invalid JSON: {exc}"}))
        return 2
    result = evaluate(scores)
    print(json.dumps(result, indent=2))
    return 0 if result.get("released") else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
