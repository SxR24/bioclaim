"""compare.py - build a multi-model comparison table from eval report CSVs.

Feed it the per-model reports produced by real_model_eval.py and it prints a
side-by-side table of hallucination rates by category - the headline artifact
for a "which model invents the most biology?" comparison.

Usage (from repo root):
    python scripts/compare.py real_model_report.csv gemini_report.csv deepseek_v4pro_report.csv
    python scripts/compare.py *.csv --questions data/bio_questions_hard.txt
"""
import csv
import json
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
    cat = lambda s: sum(1 for r in rows if r["status"] in s)

    # prefer the run's sidecar for the true answered-count (partial runs!)
    meta_path = pathlib.Path(str(path) + ".meta.json")
    if meta_path.exists():
        m = json.load(open(meta_path))
        answered, skipped = m["answered"], m.get("skipped", 0)
    else:
        answered = len({r["q_num"] for r in rows})   # lower bound
        skipped = (n_questions - answered) if n_questions else 0

    flagged_q = {r["q_num"] for r in rows if r["status"] in FLAGGED}
    return {
        "model": model, "answered": answered, "partial": skipped > 0,
        "total_ids": len(rows), "answers_flagged": len(flagged_q),
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
    summ.sort(key=lambda s: s["answers_flagged"] / max(s["answered"], 1), reverse=True)

    hdr = f"{'Model':<30}{'Answers wrong':>18}{'Fab':>6}{'Mis':>6}{'Ent':>6}{'Obs':>6}{'IDs':>6}"
    print(hdr)
    print("-" * len(hdr))
    for s in summ:
        a = max(s["answered"], 1)
        pct = s["answers_flagged"] / a * 100
        flag = " *PARTIAL" if s["partial"] else ""
        rate = f"{s['answers_flagged']}/{s['answered']} ({pct:.0f}%)"
        print(f"{s['model'][:29]:<30}{rate:>18}{s['fab']:>6}{s['mis']:>6}"
              f"{s['ent']:>6}{s['obs']:>6}{s['total_ids']:>6}{flag}")
    print("\nFab=fabricated  Mis=mislabeled  Ent=wrong-entity  Obs=obsolete")
    if any(s["partial"] for s in summ):
        print("* PARTIAL run (rate-limited) - not directly comparable to full runs.")


if __name__ == "__main__":
    main()
