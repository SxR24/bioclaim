"""v0.5 demo: catch WRONG descriptions of REAL identifiers (claim verification).

Runs live. Real id + correct label -> SUPPORTED_LABEL_OK.
Real id + wrong label -> SUPPORTED_LABEL_MISMATCH  (the new catch).
Fake id -> NOT_FOUND.

    python scripts/demo_claims.py
"""
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from bioclaim import report_claims

LLM_ANSWER = (
    "TP53 is annotated with GO:0006915 (apoptotic process), which is correct. "
    "The model also claims GO:0006281 (photosynthesis) - but that GO term is "
    "actually DNA repair. Finally it cites the fabricated GO:9999999 (repair)."
)


def main():
    r = report_claims(LLM_ANSWER, online=True)
    print(f"identifiers checked: {r['n_ids']}   flagged: {r['n_flagged']}\n")
    for v in r["verdicts"]:
        bad = v["status"] in ("NOT_FOUND", "INVALID_FORMAT", "SUPPORTED_LABEL_MISMATCH")
        mark = "  FLAG ->" if bad else "         "
        claimed = f'"{v["claimed_label"]}"' if v["claimed_label"] else "(no label)"
        canon = f' | real: "{v["canonical_label"]}"' if v["canonical_label"] else ""
        print(f'{mark} {v["curie"]:<13} {v["status"]:<26} says {claimed}{canon}')
    print(f"\nResult: flagged {r['n_flagged']} problem(s) "
          f"(fabricated IDs + real IDs with wrong descriptions).")


if __name__ == "__main__":
    main()
