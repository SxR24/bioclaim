"""v0.6 demo: catch a REAL identifier attached to the WRONG gene.

The hardest hallucination to spot: the model gives a real, valid accession -
but for a different protein than the one it names. Existence checks pass it;
label checks may miss it; entity-correspondence catches it.

    python scripts/demo_entity.py
"""
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from bioclaim import report_claims

LLM_ANSWER = (
    "The UniProt accession for BRCA1 is P38398, which is correct. "
    "The model also states that the UniProt accession for TP53 is P38398 - "
    "but P38398 is actually BRCA1, not TP53."
)


def main():
    r = report_claims(LLM_ANSWER, online=True)
    print(f"identifiers checked: {r['n_ids']}   flagged: {r['n_flagged']}\n")
    for v in r["verdicts"]:
        bad = "MISMATCH" in v["status"] or v["status"] in ("NOT_FOUND", "INVALID_FORMAT")
        mark = "  FLAG ->" if bad else "         "
        canon = f' | really: "{v["canonical_label"]}"' if v["canonical_label"] else ""
        print(f'{mark} {v["curie"]:<10} {v["status"]:<28}{canon}')
    print(f"\nResult: flagged {r['n_flagged']} (real IDs pointing at the wrong gene).")


if __name__ == "__main__":
    main()
