"""rescore.py - re-score an existing eval report with the current bioclaim logic.

The expensive part (calling the LLM) is already done and saved in the report CSV.
This recomputes only the *verification* - specifically the v0.6 entity check, now
anchored to the question's known gene instead of guessing from nearby text - using
database lookups. No model re-runs, so it's cheap and deterministic.

Usage (from repo root):
    python scripts/rescore.py groq_gptoss_report.csv --out groq_gptoss_rescored.csv
"""
import sys
import csv
import json
import argparse
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from bioclaim.patterns import ID_PATTERNS
from bioclaim.claims import extract_target_entity, verify_entity

FABRICATED = {"NOT_FOUND", "INVALID_FORMAT"}
MISLABELED = {"SUPPORTED_LABEL_MISMATCH"}
WRONG_ENTITY = {"SUPPORTED_ENTITY_MISMATCH"}
OBSOLETE = {"SUPPORTED_OBSOLETE"}
FLAGGED = FABRICATED | MISLABELED | WRONG_ENTITY | OBSOLETE


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("report")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    out = args.out or args.report.replace(".csv", "_rescored.csv")

    rows = list(csv.DictReader(open(args.report, encoding="utf-8")))
    changed = 0
    for r in rows:
        info = ID_PATTERNS.get(r["prefix"])
        if not info:
            continue
        _rx, kind, arg, _lbl = info
        # only UniProt/Ensembl entity checks change; fabricated/unverified stay put
        if kind in ("uniprot", "ensembl") and r["status"] not in FABRICATED \
                and r["status"] != "UNVERIFIED":
            hint = extract_target_entity(r["question"])
            old = r["status"]
            if hint:
                st, canon = verify_entity(r["curie"], kind, arg, hint)
                r["status"] = st
                if canon:
                    r["real_label"] = canon
            else:
                r["status"] = "SUPPORTED_NO_LABEL"
            if r["status"] != old:
                changed += 1

    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader()
        w.writerows(rows)

    # preserve the true answered-count from the original sidecar if present
    meta_in = pathlib.Path(args.report + ".meta.json")
    answered = (json.load(open(meta_in))["answered"] if meta_in.exists()
                else len({r["q_num"] for r in rows}))
    model = rows[0].get("model", "?")
    flagged_q = {r["q_num"] for r in rows if r["status"] in FLAGGED}
    cat = lambda s: sum(1 for r in rows if r["status"] in s)
    json.dump({"model": model, "n": answered, "answered": answered, "skipped": 0,
               "answers_flagged": len(flagged_q), "total_ids": len(rows),
               "fabricated": cat(FABRICATED), "mislabeled": cat(MISLABELED),
               "wrong_entity": cat(WRONG_ENTITY), "obsolete": cat(OBSOLETE)},
              open(out + ".meta.json", "w"))

    pct = len(flagged_q) / max(answered, 1) * 100
    print(f"{model}: {changed} verdicts corrected")
    print(f"  answers wrong: {len(flagged_q)}/{answered} ({pct:.0f}%)"
          f"  | fab={cat(FABRICATED)} mis={cat(MISLABELED)} "
          f"ent={cat(WRONG_ENTITY)} obs={cat(OBSOLETE)}")
    print(f"  -> {out}")


if __name__ == "__main__":
    main()
