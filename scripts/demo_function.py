"""v0.8 demo: catch a FALSE gene-function association.

The hardest class yet: a real, correctly-named GO term assigned to a gene that
isn't actually annotated with it. Existence and label checks both pass; only a
gene-annotation check (QuickGO) catches it. Opt-in via --functions / check_functions.

    python scripts/demo_function.py
"""
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from bioclaim import check

LLM_ANSWER = (
    "TP53 (UniProt P04637) is annotated with GO:0006281 (DNA repair), which is "
    "correct, and also with GO:0015979 (photosynthesis) - a real, correctly "
    "named GO term, but one TP53 has nothing to do with."
)


def main():
    r = check(LLM_ANSWER, check_functions=True)   # opt-in gene-function check
    print(f"identifiers checked: {r.n_ids}   flagged: {len(r.problems)}\n")
    for p in r.problems:
        print("  FLAG ->", p)
    if r.ok:
        print("  (nothing flagged)")
    print("\nNote: existence + label checks pass GO:0015979 - only the gene-function "
          "check knows TP53 isn't annotated with photosynthesis.")


if __name__ == "__main__":
    main()
