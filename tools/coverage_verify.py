#!/usr/bin/env python3
"""
Creator OS deliverable coverage verification (P35).

Two jobs, both offline and citation-first: (1) reconcile several media transcripts of the same content into
a canonical truth, surfacing every disagreement as a conflict rather than silently picking (a ROVER-style
progressive alignment + confidence-weighted vote); (2) verify that a deliverable covered its required points,
citing the supporting sentence per point and abstaining when unsure (built in the next chunk). Reuses the
transcript parser and WER utility in shared/docintel. See shared/tasks-engine.md.

Usage:
  python3 tools/coverage_verify.py --selftest
  python3 tools/coverage_verify.py reconcile --files a.srt b.vtt c.json
"""
import argparse
import difflib
import json
import os
import sys
from pathlib import Path

ROOT = Path(os.environ.get("CREATOR_OS_ROOT", str(Path(__file__).resolve().parent.parent)))
sys.path.insert(0, str(ROOT / "shared" / "docintel"))
import wer as _wer  # type: ignore
import transcripts as _tx  # type: ignore

BOUNDARY = ("COVERAGE ANALYSIS FROM THE SOURCES YOU PROVIDED. Verdicts cite a specific sentence; when no "
            "sentence supports a point the tool abstains and routes to your review. Not compliance advice.")

NULL = "@"  # a source omitted this slot (deletion vote)
_COMPLETENESS = {"rich": 1.0, "partial": 0.7, "minimal": 0.5}
DISSENT_THRESHOLD = 0.30  # a credible minority (>= ~a third) is surfaced as a conflict, not silently dropped


def _reliability(src):
    if src.get("reliability") is not None:
        return float(src["reliability"])
    return _COMPLETENESS.get(src.get("artifact_completeness"), 1.0)


def _tokens(text):
    return _wer.normalize(text or "").split()


def reconcile(sources):
    """Progressive ROVER-style reconciliation. sources: list of {id, text, reliability?/artifact_completeness?}.
    Returns the canonical transcript, per-slot conflicts (with the disagreeing options, weights, and source
    ids), and a pairwise WER divergence matrix. Ties and credible dissents are always surfaced."""
    sources = [s for s in sources if (s.get("text") or "").strip()]
    if not sources:
        return {"error": "no non-empty sources", "boundary": BOUNDARY}
    if len(sources) == 1:
        toks = _tokens(sources[0]["text"])
        return {"canonical_text": " ".join(toks), "canonical_tokens": toks, "conflicts": [],
                "divergence_matrix": {sources[0]["id"]: {sources[0]["id"]: 0.0}},
                "sources": [sources[0]["id"]], "boundary": BOUNDARY, "human_review_required": False}

    base = sources[0]
    w0 = _reliability(base)
    slots = [{"votes": {t: w0}, "sources": {base["id"]}} for t in _tokens(base["text"])]

    for src in sources[1:]:
        w = _reliability(src)
        sid = src["id"]
        T = _tokens(src["text"])
        canonical_words = [max(s["votes"], key=s["votes"].get) for s in slots]
        sm = difflib.SequenceMatcher(a=canonical_words, b=T, autojunk=False)
        new = []
        for tag, a0, a1, b0, b1 in sm.get_opcodes():
            if tag == "equal":
                for k in range(a1 - a0):
                    s = slots[a0 + k]
                    s["votes"][T[b0 + k]] = s["votes"].get(T[b0 + k], 0) + w
                    s["sources"].add(sid)
                    new.append(s)
            elif tag == "replace":
                span_a, span_b = a1 - a0, b1 - b0
                for k in range(span_a):
                    s = slots[a0 + k]
                    word = T[b0 + k] if k < span_b else NULL
                    s["votes"][word] = s["votes"].get(word, 0) + w
                    s["sources"].add(sid)
                    new.append(s)
                for k in range(span_a, span_b):
                    new.append({"votes": {T[b0 + k]: w}, "sources": {sid}})
            elif tag == "delete":
                for k in range(a1 - a0):
                    s = slots[a0 + k]
                    s["votes"][NULL] = s["votes"].get(NULL, 0) + w
                    s["sources"].add(sid)
                    new.append(s)
            elif tag == "insert":
                for k in range(b1 - b0):
                    new.append({"votes": {T[b0 + k]: w}, "sources": {sid}})
        slots = new

    canonical_tokens, conflicts, credible_any = [], [], False
    for i, s in enumerate(slots):
        ranked = sorted(s["votes"].items(), key=lambda kv: kv[1], reverse=True)
        winner = ranked[0][0]
        if winner != NULL:
            canonical_tokens.append(winner)
        total = sum(v for _, v in ranked)
        # every multi-candidate slot is a retained dissent; only a credible one (>= threshold) forces review
        if len(ranked) > 1 and total > 0:
            credible = (ranked[1][1] / total) >= DISSENT_THRESHOLD
            credible_any = credible_any or credible
            conflicts.append({
                "position": i, "winner": winner, "credible": credible,
                "options": {k: round(v, 3) for k, v in ranked},
                "sources": sorted(s["sources"]),
            })

    ids = [s["id"] for s in sources]
    div = {a["id"]: {} for a in sources}
    for a in sources:
        for b in sources:
            div[a["id"]][b["id"]] = 0.0 if a["id"] == b["id"] else round(
                _wer.evaluate(a["text"], b["text"]).get("wer", 0.0), 3)

    return {
        "canonical_text": " ".join(canonical_tokens),
        "canonical_tokens": canonical_tokens,
        "conflicts": conflicts,
        "divergence_matrix": div,
        "sources": ids,
        "boundary": BOUNDARY,
        "human_review_required": credible_any,
    }


def _load_source(path):
    parsed = _tx.parse(path)
    return {"id": Path(path).name, "text": parsed.get("plain_text", ""),
            "segments": parsed.get("segments", []), "artifact_completeness": "rich"}


def selftest():
    failures = []

    def check(name, cond):
        if not cond:
            failures.append(name)

    # identical sources -> no conflicts
    same = reconcile([{"id": "a", "text": "the max riser height is seven inches"},
                      {"id": "b", "text": "the max riser height is seven inches"}])
    check("identical-no-conflict", same["conflicts"] == [] and "seven" in same["canonical_text"])

    # a one-word disagreement between two equal-weight sources -> a surfaced conflict, majority-free tie
    diff = reconcile([{"id": "a", "text": "riser height seven inches"},
                      {"id": "b", "text": "riser height eleven inches"}])
    check("conflict-surfaced", len(diff["conflicts"]) == 1)
    conf = diff["conflicts"][0]
    check("conflict-options", set(conf["options"]) >= {"seven", "eleven"})
    check("conflict-sources", conf["sources"] == ["a", "b"])

    # majority vote with a credible 1-of-3 dissent still surfaced
    maj = reconcile([{"id": "a", "text": "points a b c d"},
                     {"id": "b", "text": "points a b c d"},
                     {"id": "c", "text": "points a b x d"}])
    check("majority-canonical", "c" in maj["canonical_tokens"])
    check("minority-dissent-surfaced", any("x" in cf["options"] for cf in maj["conflicts"]))

    # reliability weighting: a high-reliability source outvotes a low one, but the dissent is retained
    rel = reconcile([{"id": "hi", "text": "riser seven inches", "reliability": 1.0},
                     {"id": "lo", "text": "riser eleven inches", "reliability": 0.3}])
    check("reliability-winner", "seven" in rel["canonical_text"])
    check("reliability-dissent-kept", len(rel["conflicts"]) == 1)

    # divergence matrix: diagonal zero, symmetric, non-zero off-diagonal for differing texts
    dm = diff["divergence_matrix"]
    check("divergence-diag", dm["a"]["a"] == 0.0 and dm["a"]["b"] > 0.0)

    # single source: no conflicts, no review needed
    one = reconcile([{"id": "only", "text": "just one transcript"}])
    check("single-source", one["conflicts"] == [] and one["human_review_required"] is False)

    n = 10
    print(f"selftest: {'PASS' if not failures else 'FAIL'} ({n - len(failures)} of {n} checks)")
    if failures:
        print("failed:", ", ".join(failures))
        return 1
    return 0


def main(argv):
    ap = argparse.ArgumentParser(description="Creator OS coverage verification")
    ap.add_argument("--selftest", action="store_true")
    sub = ap.add_subparsers(dest="cmd")
    p = sub.add_parser("reconcile"); p.add_argument("--files", nargs="+", required=True)
    args = ap.parse_args(argv)
    if args.selftest:
        return selftest()
    if args.cmd == "reconcile":
        sources = [_load_source(f) for f in args.files]
        print(json.dumps(reconcile(sources), indent=2))
        return 0
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
