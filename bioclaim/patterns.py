"""Canonical identifier patterns for biomedical ontologies and databases.

The deterministic first line of defense. A well-formed but non-existent ID
(e.g. GO:0099999) is the single most common, most verifiable class of
biomedical LLM hallucination.

Each entry: (regex, source_kind, source_arg, human_label)
  source_kind: "ols" | "uniprot" | "ensembl"  -> which live checker to use
  source_arg : ontology slug for OLS, else None
"""
import re

ID_PATTERNS = {
    "GO":      (re.compile(r"\bGO:\d{7}\b"),    "ols",     "go",    "Gene Ontology term"),
    "HP":      (re.compile(r"\bHP:\d{7}\b"),    "ols",     "hp",    "Human Phenotype Ontology term"),
    "MONDO":   (re.compile(r"\bMONDO:\d{7}\b"), "ols",     "mondo", "MONDO disease term"),
    "DOID":    (re.compile(r"\bDOID:\d+\b"),    "ols",     "doid",  "Disease Ontology term"),
    "CHEBI":   (re.compile(r"\bCHEBI:\d+\b"),   "ols",     "chebi", "ChEBI chemical entity"),
    "ENSG":    (re.compile(r"\bENSG\d{11}\b"),  "ensembl", None,    "Ensembl human gene"),
    # Full official UniProtKB accession syntax (both forms), not just O/P/Q:
    "UNIPROT": (re.compile(
        r"\b(?:[OPQ][0-9][A-Z0-9]{3}[0-9]|[A-NR-Z][0-9](?:[A-Z][A-Z0-9]{2}[0-9]){1,2})\b"),
        "uniprot", None, "UniProtKB accession"),
}


def extract_ids(text):
    """Yield (prefix, curie, start, end) for every recognized identifier."""
    for prefix, (rx, _kind, _arg, _label) in ID_PATTERNS.items():
        for m in rx.finditer(text):
            yield prefix, m.group(0), m.start(), m.end()
