"""bioclaim v0.2 - the ontology-ID validator (the first blade).

Two layers:
  1. FORMAT  - offline, deterministic, near-zero false positives.
  2. EXISTS  - online existence check against authoritative databases
               (EBI OLS4 for ontologies, UniProtKB and Ensembl for the rest).

Returns a per-identifier verdict a downstream app can act on.
"""
from dataclasses import dataclass, asdict
from typing import Optional
from .patterns import ID_PATTERNS, extract_ids
from . import sources


@dataclass
class Verdict:
    curie: str
    prefix: str
    label: str
    format_ok: bool
    exists: Optional[bool]  # None = not checked / could not verify
    status: str             # SUPPORTED | INVALID_FORMAT | NOT_FOUND | UNVERIFIED
    start: int
    end: int


def scan(text, online=True):
    """Scan free text, return a list of Verdict for every identifier found."""
    verdicts = []
    for prefix, curie, start, end in extract_ids(text):
        rx, kind, arg, label = ID_PATTERNS[prefix]
        format_ok = bool(rx.fullmatch(curie))
        exists, status = None, "UNVERIFIED"
        if not format_ok:
            status = "INVALID_FORMAT"
        elif online:
            exists = sources.exists(kind, curie, arg)
            if exists is True:
                status = "SUPPORTED"
            elif exists is False:
                status = "NOT_FOUND"       # well-formed but fabricated -> the money shot
        verdicts.append(Verdict(curie, prefix, label, format_ok, exists,
                                status, start, end))
    return verdicts


def report(text, online=True):
    """Human-readable summary + machine-readable verdicts."""
    v = scan(text, online=online)
    flagged = [x for x in v if x.status in ("INVALID_FORMAT", "NOT_FOUND")]
    return {
        "n_ids": len(v),
        "n_flagged": len(flagged),
        "verdicts": [asdict(x) for x in v],
    }
