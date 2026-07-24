"""batch.py - run bioclaim over YOUR OWN AI answers (no labels needed).

Because every verdict is checked against an authoritative database, a NOT_FOUND
result is ground truth by construction: the identifier provably does not exist.
So even unlabeled real answers give a legitimate headline number.

Input: a .jsonl file (each line has an `answer` field) OR a plain .txt file
       (one answer per line).

Usage:
    python scripts/batch.py my_answers.jsonl
    python scripts/batch.py my_answers.txt
"""
import sys
import json
import csv
import pathlib
from collections import Counter

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from bioclaim import scan

FLAGGED = {"NOT_FOUND", "INVALID_FORMAT"}


def load_answers(path):
    answers = []
    with open(path, encoding="utf-8") as f:
        if path.endswith(".jsonl"):
            for line in f:
                line = line.strip()
                if line:
                    answers.append(json.loads(line).get("answer", ""))
        else:
            for line in f:
                if line.strip():
                    answers.append(line.strip())
    return answers


def main(path):
    answers = load_answers(path)
    counts = Counter()
    total_ids = 0
    ans_flagged = 0
    rows = []

    for i, ans in enumerate(answers, 1):
        verdicts = scan(ans, online=True)
        total_ids += len(verdicts)
        flagged_here = [v for v in verdicts if v.status in FLAGGED]
        if flagged_here:
            ans_flagged += 1
        for v in verdicts:
            counts[v.status] += 1
            rows.append({"answer_num": i, "curie": v.curie,
                         "prefix": v.prefix, "status": v.status})

    out = "batch_report.csv"
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["answer_num", "curie", "prefix", "status"])
        w.writeheader()
        w.writerows(rows)

    n_fake = counts["NOT_FOUND"] + counts["INVALID_FORMAT"]
    print("=" * 52)
    print(f"  bioclaim batch scan  -  {len(answers)} answers")
    print("=" * 52)
    print(f"  identifiers examined:        {total_ids}")
    print(f"  SUPPORTED (real):            {counts['SUPPORTED']}")
    print(f"  NOT_FOUND (fabricated):      {counts['NOT_FOUND']}")
    print(f"  INVALID_FORMAT:              {counts['INVALID_FORMAT']}")
    print(f"  UNVERIFIED (network):        {counts['UNVERIFIED']}")
    print("-" * 52)
    rate = ans_flagged / len(answers) if answers else 0
    print(f"  answers with >=1 fabrication: {ans_flagged}/{len(answers)} ({rate:.0%})")
    print("=" * 52)
    print(f"\nHeadline: caught {n_fake} fabricated identifier(s) "
          f"across {len(answers)} answers.")
    print(f"Full breakdown saved to {out}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: python scripts/batch.py <answers.jsonl | answers.txt>")
        sys.exit(1)
    main(sys.argv[1])
