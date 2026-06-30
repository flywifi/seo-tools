#!/usr/bin/env python3
"""Creator OS document intelligence: local, offline, zero-token transcript accuracy validator.

Computes Word Error Rate (WER) and Character Error Rate (CER) between a reference transcript and a
hypothesis transcript, the standard measure used to validate speech-to-text accuracy. Pure standard
library (a Levenshtein edit distance), so it runs on the client with no internet and no tokens. This
is the local equivalent of the jiwer library, for QA on any transcript or caption file.

Usage:
  python3 shared/docintel/wer.py --ref reference.txt --hyp whisper_output.txt
  python3 shared/docintel/wer.py --ref "the quick brown fox" --hyp "the quick fox" --json
"""
import argparse
import json
import re
import sys
from pathlib import Path


def load(value):
    p = Path(value)
    if p.exists() and p.is_file():
        return p.read_text(encoding="utf-8", errors="replace")
    return value


def normalize(text):
    text = text.lower()
    text = re.sub(r"[^\w\s']", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def edit_counts(ref_tokens, hyp_tokens):
    n, m = len(ref_tokens), len(hyp_tokens)
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        dp[i][0] = i
    for j in range(m + 1):
        dp[0][j] = j
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            if ref_tokens[i - 1] == hyp_tokens[j - 1]:
                dp[i][j] = dp[i - 1][j - 1]
            else:
                dp[i][j] = 1 + min(dp[i - 1][j], dp[i][j - 1], dp[i - 1][j - 1])
    # backtrack to label substitutions, deletions, insertions
    i, j = n, m
    sub = dele = ins = hit = 0
    while i > 0 or j > 0:
        if i > 0 and j > 0 and ref_tokens[i - 1] == hyp_tokens[j - 1]:
            hit += 1
            i, j = i - 1, j - 1
        elif i > 0 and j > 0 and dp[i][j] == dp[i - 1][j - 1] + 1:
            sub += 1
            i, j = i - 1, j - 1
        elif i > 0 and dp[i][j] == dp[i - 1][j] + 1:
            dele += 1
            i -= 1
        else:
            ins += 1
            j -= 1
    return {"hits": hit, "substitutions": sub, "deletions": dele, "insertions": ins}


def evaluate(ref, hyp):
    ref_words = normalize(ref).split()
    hyp_words = normalize(hyp).split()
    wc = edit_counts(ref_words, hyp_words)
    n = len(ref_words) or 1
    wer = (wc["substitutions"] + wc["deletions"] + wc["insertions"]) / n
    ref_chars = list(normalize(ref).replace(" ", ""))
    hyp_chars = list(normalize(hyp).replace(" ", ""))
    cc = edit_counts(ref_chars, hyp_chars)
    cn = len(ref_chars) or 1
    cer = (cc["substitutions"] + cc["deletions"] + cc["insertions"]) / cn
    return {
        "wer": round(wer, 4),
        "wer_percent": round(wer * 100, 2),
        "cer": round(cer, 4),
        "ref_words": len(ref_words),
        "hyp_words": len(hyp_words),
        "word_edits": wc,
        "accuracy_percent": round((1 - wer) * 100, 2),
        "ran_locally": True,
        "tokens_spent_on_validation": 0,
    }


def main(argv):
    ap = argparse.ArgumentParser(description="Creator OS offline WER/CER validator")
    ap.add_argument("--ref", required=True, help="reference text or file path")
    ap.add_argument("--hyp", required=True, help="hypothesis text or file path")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    result = evaluate(load(args.ref), load(args.hyp))
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"WER {result['wer_percent']}%  CER {result['cer']*100:.2f}%  "
              f"accuracy {result['accuracy_percent']}%  "
              f"({result['ref_words']} ref words, edits={result['word_edits']})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
