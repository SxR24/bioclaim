"""compare.py - build a multi-model comparison table from eval report CSVs.

Feed it the per-model reports produced by real_model_eval.py and it prints a
side-by-side table of hallucination rates by category - the headline artifact
for a "which model invents the most biology?" comparison.

Usage (from repo root):
    python scripts/compare.py real_model_report.csv gemini_report.csv deepseek_v4pro_report.csv
    python scripts/compare.py *.csv --questions data/bio_questions_hard.txt
"""
import sys
import csv
import argparse
import pathlib

FABRICATED = {"NOT_FOUND", "INVALID_FORMAT"}
MISLABELED = {"SUPPORTED_LABEL_MISMATCH"}
WRONG_ENTITY = {"SUPPORTED_ENTITY_MISMATCH"}
OBSOLETE = {"SUPPORTED_OBSOLETE"}
FLAGGED = FABRICATED | MISLABELED | WRONG_ENTITY | OBSOLETE


def summarize(path, n_questions=None):
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    if not rows:
        return None
    model = rows[0].get("model", pathlib.Path(path).stem)
    n = n_questions or max(int(r["q_num"]) for r in rows)
    flagged_q = {r["q_num"] for r in rows if r["status"] in FLAGGED}
    cat = lambda s: sum(1 for r in rows if r["status"] in s)
    return {
        "model": model, "n": n, "total_ids": len(rows),
        "answers_flagged": len(flagged_q),
        "fab": cat(FABRICATED), "mis": cat(MISLABELED),
        "ent": cat(WRONG_ENTITY), "obs": cat(OBSOLETE),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("reports", nargs="+")
    ap.add_argument("--questions", default=None,
                    help="questions file, to fix the answer count (N)")
    args = ap.parse_args()

    n_q = None
    if args.questions:
        n_q = sum(1 for l in open(args.questions, encoding="utf-8") if l.strip())

    summ = [s for s in (summarize(p, n_q) for p in args.reports) if s]
    summ.sort(key=lambda s: s["answers_flagged"] / s["n"], reverse=True)

    hdr = f"{'Model':<34}{'Answers wrong':>16}{'Fab':>6}{'Mis':>6}{'Ent':>6}{'Obs':>6}{'IDs':>6}"
    print(hdr)
    print("-" * len(hdr))
    for s in summ:
        pct = s["answers_flagged"] / s["n"] * 100
        rate = f"{s['answers_flagged']}/{s['n']} ({pct:.0f}%)"
        print(f"{s['model'][:33]:<34}{rate:>16}{s['fab']:>6}{s['mis']:>6}"
              f"{s['ent']:>6}{s['obs']:>6}{s['total_ids']:>6}")
    print("\nFab=fabricated  Mis=mislabeled  Ent=wrong-entity  Obs=obsolete")


if __name__ == "__main__":
    main()
