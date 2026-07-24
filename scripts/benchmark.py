"""benchmark.py - the paper-grade number.

Runs bioclaim over a LABELED file of answers (JSONL with an `answer` string and
a `fabricated` list of the IDs that are truly invented) and reports how well it
catches fabrications: precision, recall, F1, plus answer-level hallucination
detection. This is the headline result you post and put in the paper.

Usage:
    python scripts/benchmark.py                          # uses the sample set
    python scripts/benchmark.py data/benchmark_large.jsonl
"""
import sys
import json
import csv
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from bioclaim import scan

FLAGGED = {"NOT_FOUND", "INVALID_FORMAT"}


def load(path):
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def main(path):
    rows = load(path)
    tp = fp = fn = 0
    unverified = 0
    ans_with_fake = ans_flagged = 0
    report_rows = []

    for row in rows:
        verdicts = scan(row["answer"], online=True)
        truth = set(row.get("fabricated", []))
        predicted = {v.curie for v in verdicts if v.status in FLAGGED}
        unverified += sum(1 for v in verdicts if v.status == "UNVERIFIED")

        tp += len(predicted & truth)
        fp += len(predicted - truth)
        fn += len(truth - predicted)

        if truth:
            ans_with_fake += 1
        if predicted:
            ans_flagged += 1

        for v in verdicts:
            report_rows.append({
                "answer_id": row.get("id"),
                "curie": v.curie, "prefix": v.prefix,
                "status": v.status,
                "is_truly_fabricated": v.curie in truth,
            })

    precision = tp / (tp + fp) if (tp + fp) else 1.0
    recall = tp / (tp + fn) if (tp + fn) else 1.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0

    out = "benchmark_report.csv"
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(report_rows[0].keys()))
        w.writeheader()
        w.writerows(report_rows)

    print("=" * 56)
    print(f"  bioclaim benchmark  -  {len(rows)} answers")
    print("=" * 56)
    print(f"  fabricated IDs caught (recall):   {recall:6.1%}  ({tp}/{tp+fn})")
    print(f"  flagged that were truly fake (precision): {precision:6.1%}")
    print(f"  F1 score:                          {f1:6.3f}")
    print(f"  false accusations (real flagged):  {fp}")
    print(f"  could not verify (network):        {unverified}")
    print("-" * 56)
    print(f"  answers containing a fabrication:  {ans_with_fake}/{len(rows)}")
    print(f"  answers bioclaim flagged:          {ans_flagged}/{len(rows)}")
    print("=" * 56)
    print(f"\nHeadline: caught {tp}/{tp+fn} fabricated identifiers "
          f"with {fp} false accusation(s).")
    print(f"Per-ID breakdown saved to {out}")


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "data/sample_answers.jsonl"
    main(path)
