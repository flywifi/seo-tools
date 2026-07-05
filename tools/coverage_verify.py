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


# ── coverage verification (FEVER-style claim check; extractive-cited; abstains) ─
_STOPWORDS = set("a an the of to in on and or for with is are was were be been that this it its as at by "
                 "from he she they we you i about into over under also then finally clearly".split())
SATISFIED_THRESHOLD = 0.8
PARTIAL_THRESHOLD = 0.5


def _content_words(text):
    return [w for w in _wer.normalize(text).split() if w not in _STOPWORDS]


def _sentences(text, segments=None):
    if segments:
        return [{"text": s.get("text", ""), "start": s.get("start"), "end": s.get("end")}
                for s in segments if (s.get("text") or "").strip()]
    import re
    return [{"text": p.strip(), "start": None, "end": None}
            for p in re.split(r"(?<=[.!?])\s+", text) if p.strip()]


def _best_sentence(claim, sentences):
    pw = set(_content_words(claim))
    best, best_score = None, 0.0
    for s in sentences:
        sw = set(_content_words(s["text"]))
        overlap = (len(pw & sw) / len(pw)) if pw else 0.0
        ratio = difflib.SequenceMatcher(None, _wer.normalize(claim), _wer.normalize(s["text"])).ratio()
        score = max(overlap, ratio * 0.9)
        if score > best_score:
            best, best_score = s, score
    return best, best_score


def _split_subclaims(point):
    import re
    parts = re.split(r"\s*(?:,|;|\band\b)\s*", point)
    return [p.strip() for p in parts if p.strip()] or [point]


def verify_point(point, sentences, judge=None):
    """Verify one required point against the canonical sentences. Compound points decompose into atomic
    sub-claims. Coverage is asserted only when a specific sentence supports the claim (extractive quote,
    verified present); otherwise the tool abstains (missing, routed to human), never inferring. An optional
    semantic/NLI `judge(claim, sentence)->{verdict, abstained}` refines the middle band when available."""
    subs = _split_subclaims(point if isinstance(point, str) else point.get("text", ""))
    results = []
    for sub in subs:
        best, score = _best_sentence(sub, sentences)
        quote = best["text"] if best else None
        if score >= SATISFIED_THRESHOLD:
            verdict, abstained = "satisfied", False
        elif judge is not None:
            jr = judge(sub, quote or "")
            verdict, abstained = jr.get("verdict", "missing"), jr.get("abstained", False)
        elif score >= PARTIAL_THRESHOLD:
            verdict, abstained = "partial", True   # lexical partial, not confident -> abstain to human
        else:
            verdict, abstained = "missing", True
        results.append({
            "sub_claim": sub, "verdict": verdict, "abstained": abstained,
            "supporting_quote": quote if verdict in ("satisfied", "partial") else None,
            "timestamp": [best.get("start"), best.get("end")] if best and verdict in ("satisfied", "partial") else None,
            "score": round(score, 3),
        })
    verds = [r["verdict"] for r in results]
    verdict = "satisfied" if all(v == "satisfied" for v in verds) else ("partial" if any(v == "satisfied" or v == "partial" for v in verds) else "missing")
    return {"verdict": verdict, "abstained": any(r["abstained"] for r in results), "sub_claims": results}


def verify_coverage(canonical_text, required_points, segments=None, reconciliation=None, judge=None):
    """Per required point: {verdict, supporting_quote (extractive), timestamp, source_citations, abstained}.
    Shaped like the verification envelope; conflicts from reconciliation flow into minority_report; every
    quote is verified present in the canonical text (never fabricated). Always human_review_required."""
    sentences = _sentences(canonical_text, segments)
    points = []
    for i, p in enumerate(required_points):
        pid = p.get("id", i) if isinstance(p, dict) else i
        ptext = p.get("text") if isinstance(p, dict) else p
        r = verify_point(p, sentences, judge=judge)
        citations = [{"quote": sc["supporting_quote"], "timestamp": sc["timestamp"]}
                     for sc in r["sub_claims"] if sc.get("supporting_quote")]
        # extractive guarantee: drop any quote not actually present in the canonical text
        norm_canon = _wer.normalize(canonical_text)
        citations = [c for c in citations if _wer.normalize(c["quote"]) in norm_canon]
        points.append({"point_id": pid, "point": ptext, "verdict": r["verdict"],
                       "abstained": r["abstained"], "sub_claims": r["sub_claims"],
                       "source_citations": citations})
    summary = {
        "total": len(points),
        "satisfied": sum(1 for p in points if p["verdict"] == "satisfied"),
        "partial": sum(1 for p in points if p["verdict"] == "partial"),
        "missing": sum(1 for p in points if p["verdict"] == "missing"),
        "abstained": sum(1 for p in points if p["abstained"]),
    }
    return {
        "boundary": BOUNDARY,
        "points": points,
        "summary": summary,
        "minority_report": (reconciliation or {}).get("conflicts", []),
        "confidence_evidence": {"method": "lexical overlap + optional semantic/NLI judge; abstains when unsure",
                                "semantic_tier_used": judge is not None},
        "human_review_required": True,
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

    # coverage verification against required talking points
    canon = ("The reviewer talked about the durability of the paint. She explained the warranty terms. "
             "The price point was affordable. The modern design was praised.")
    cov = verify_coverage(canon, ["durability", "warranty terms", "price", "design"])
    check("cov-all-satisfied", cov["summary"]["satisfied"] == 4)
    check("cov-extractive", all(_wer.normalize(c["quote"]) in _wer.normalize(canon)
                                for p in cov["points"] for c in p["source_citations"]))
    check("cov-has-citations", all(p["source_citations"] for p in cov["points"]))
    miss = verify_coverage(canon, ["sustainability"])
    check("cov-missing-abstains", miss["points"][0]["verdict"] == "missing" and miss["points"][0]["abstained"] is True)
    comp = verify_coverage(canon, ["durability and design"])
    check("cov-compound-satisfied", comp["points"][0]["verdict"] == "satisfied")
    part = verify_coverage(canon, ["durability and sustainability"])
    check("cov-compound-partial", part["points"][0]["verdict"] == "partial" and part["points"][0]["abstained"] is True)
    check("cov-human-review", cov["human_review_required"] is True)
    cov5 = verify_coverage(canon, ["price"], reconciliation=diff)
    check("cov-minority-passthrough", len(cov5["minority_report"]) >= 1)

    n = 18
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
    p = sub.add_parser("coverage")
    p.add_argument("--files", nargs="+", required=True)
    p.add_argument("--points", nargs="+", required=True)
    args = ap.parse_args(argv)
    if args.selftest:
        return selftest()
    if args.cmd == "reconcile":
        sources = [_load_source(f) for f in args.files]
        print(json.dumps(reconcile(sources), indent=2))
        return 0
    if args.cmd == "coverage":
        sources = [_load_source(f) for f in args.files]
        rec = reconcile(sources)
        canonical = rec.get("canonical_text", "")
        # cite against the richest source's segments when available for timestamps
        segs = sources[0].get("segments") if len(sources) == 1 else None
        print(json.dumps(verify_coverage(canonical, args.points, segments=segs, reconciliation=rec), indent=2))
        return 0
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
