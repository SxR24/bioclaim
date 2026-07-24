"""Demo: catch fabricated biomedical identifiers in an LLM answer.

Runs LIVE by default: checks every identifier against UniProt, Ensembl, and
EBI's ontology service. Real IDs come back SUPPORTED; invented ones NOT_FOUND.
Needs internet. No connection -> those IDs show UNVERIFIED (never a false accusation).

    python scripts/demo.py
"""
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from bioclaim import report

llm_answer = (
    "TP53 (UniProt P04637, gene ENSG00000141510) is annotated with "
    "GO:0006915 (apoptotic process) and the fabricated term GO:9999999. "
    "The phenotype maps to HP:0001250, plus the invented code HP:9999999."
)

r = report(llm_answer, online=True)

print(f"identifiers found: {r['n_ids']}   flagged as fabricated: {r['n_flagged']}\n")
for v in r["verdicts"]:
    mark = "  FAKE ->" if v["status"] in ("NOT_FOUND", "INVALID_FORMAT") else "        "
    print(f"{mark} {v['curie']:<16} {v['status']:<15} {v['label']}")

print(f"\nResult: caught {r['n_flagged']} fabricated identifier(s).")
