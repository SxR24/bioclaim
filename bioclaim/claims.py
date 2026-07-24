"""bioclaim v0.5 - claim verification (label consistency).

Existence checking (v0.1-0.3) answers "does this identifier exist?".
Claim checking answers "is what the model SAID about it true?".

The first and most catchable class of claim is the label a model attaches to an
identifier. When a model writes:

    GO:0006281 (photosynthesis)

that GO id is real - but its actual meaning is "DNA repair". Existence checking
passes it; claim checking flags it as SUPPORTED_LABEL_MISMATCH.

Matching is synonym-aware (it pulls the term's synonyms from the source database)
so legitimate paraphrases like "apoptosis" vs "apoptotic process" are NOT flagged.
When the canonical name can't be fetched, the verdict degrades to a non-accusing
status - bioclaim never falsely accuses.

Verdict statuses:
    SUPPORTED_LABEL_OK        real id, and the model's description matches
    SUPPORTED_LABEL_MISMATCH  real id, but the model's description is wrong  <-- the catch
    SUPPORTED_NO_LABEL        real id, no description given to check
    SUPPORTED                 real id, description given but name couldn't be fetched
    NOT_FOUND / INVALID_FORMAT / UNVERIFIED   (as in existence checking)
"""
import re
from dataclasses import dataclass, asdict
from typing import Optional
from .patterns import ID_PATTERNS, extract_ids
from . import sources

_MATCH_THRESHOLD = 0.6  # token-overlap needed to accept a paraphrase


@dataclass
class ClaimVerdict:
    curie: str
    prefix: str
    kind_label: str
    claimed_label: Optional[str]
    canonical_label: Optional[str]
    status: str
    start: int
    end: int


def _normalize(s):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", s.lower())).strip()


def _is_placeholder(name, curie):
    """A 'name' that is really just the identifier echoed back (e.g. 'GO_0016021')
    carries no information - never accuse a mismatch against it."""
    n = _normalize(name)
    return not n or n == _normalize(curie) or n == _normalize(curie.replace(":", "_"))


def _real_names(names, curie):
    return [n for n in names if not _is_placeholder(n, curie)]


def _matches(claimed, names):
    """True (match) / False (mismatch) / None (nothing to compare)."""
    c = _normalize(claimed)
    if not c or not names:
        return None
    ct = set(c.split())
    for n in names:
        nn = _normalize(n)
        if not nn:
            continue
        if c == nn or c in nn or nn in c:
            return True
        nt = set(nn.split())
        if ct and nt and len(ct & nt) / len(ct | nt) >= _MATCH_THRESHOLD:
            return True
    return False


# --- v0.6: entity-correspondence (is this real ID the RIGHT one for the gene?) ---

_CAND_RE = re.compile(r"\bC\d+orf\d+\b|\b[A-Z][A-Z0-9]{1,7}\b")
_SYMBOL_STOP = {
    "DNA", "RNA", "MRNA", "TRNA", "RRNA", "NCRNA", "ATP", "GTP", "ADP", "GDP",
    "AMP", "NAD", "NADP", "NADH", "FAD", "GO", "HP", "HPO", "ID", "IDS", "THE",
    "FOR", "IS", "ARE", "AND", "OR", "OF", "IN", "TO", "GENE", "HUMAN", "UNIPROT",
    "ENSEMBL", "ENSG", "MONDO", "DOID", "CHEBI", "HGNC", "EC", "PDB", "KEGG",
    "NCBI", "OMIM", "API", "REST", "JSON", "PH", "UV", "PCR", "MW", "KDA",
}


def _looks_like_id(tok):
    for _rx, (rx, _k, _a, _l) in [(p, ID_PATTERNS[p]) for p in ID_PATTERNS]:
        if rx.fullmatch(tok):
            return True
    return False


def _gene_candidates(window):
    """Symbol-like tokens near an identifier (nearest last), minus noise/IDs."""
    out = []
    for m in _CAND_RE.finditer(window):
        tok = m.group(0)
        up = tok.upper()
        if up in _SYMBOL_STOP or _looks_like_id(tok):
            continue
        out.append(up)
    return out


def _entity_status(curie, kind, arg, claimed_label, window_before):
    """For UniProt/Ensembl: does the ID correspond to the claimed gene/entity?"""
    ent = sources.fetch_entity(kind, curie, arg)
    if not ent:
        return "SUPPORTED", None
    canonical = ent.get("primary")
    real_syms = {s.upper() for s in ent.get("symbols", [])}
    real_names = _real_names(ent.get("names", []), curie)

    signals = []                       # collect True/False evidence
    if claimed_label:                  # e.g. "P04637 (Cellular tumor antigen p53)"
        signals.append(_matches(claimed_label, real_names))
    cands = _gene_candidates(window_before)
    if cands and real_syms:
        if any(c in real_syms for c in cands):
            signals.append(True)
        else:
            signals.append(False)      # a gene symbol is claimed, none match

    if any(s is True for s in signals):
        return "SUPPORTED_ENTITY_OK", canonical
    if any(s is False for s in signals):
        return "SUPPORTED_ENTITY_MISMATCH", canonical
    return "SUPPORTED_NO_LABEL", canonical


def extract_target_entity(question):
    """Best-effort: the gene/protein a question is asking about.

    Reliable because our questions are structured ("...for the gene FUS",
    "...human protein Neurexin-1 (NRXN1)"). Used to anchor entity-correspondence
    to the KNOWN entity instead of guessing from nearby text.
    """
    stop = {"ontology", "id", "ids", "the", "human", "a", "an"}
    m = re.search(r"\(([A-Z][A-Z0-9]{1,9})\)", question)   # (NRXN1), (CNTN4)
    if m:
        return m.group(1)
    # all "gene X" / "protein X" mentions; the real target is the last non-filler
    # (skips "gene ID", "Gene Ontology", etc.)
    cands = [c for c in re.findall(r"(?:gene|protein)\s+([A-Za-z][A-Za-z0-9]{1,12})",
                                   question) if c.lower() not in stop]
    if cands:
        return cands[-1]
    m = re.search(r"\bfor\s+([A-Z][A-Z0-9]{1,9})\b", question)          # for SOD1
    if m and m.group(1).lower() not in stop:
        return m.group(1)
    return None


def verify_entity(curie, kind, arg, hint):
    """Does this UniProt/Ensembl id correspond to the known entity `hint`?

    Returns (status, canonical). Reliable: compares against the id's real gene
    symbols and names, not text proximity.
    """
    ent = sources.fetch_entity(kind, curie, arg)
    if not ent:
        return "SUPPORTED", None
    canonical = ent.get("primary")
    syms = {s.upper() for s in ent.get("symbols", [])}
    hit = hint.upper() in syms or _matches(hint, ent.get("names", [])) is True
    return ("SUPPORTED_ENTITY_OK" if hit else "SUPPORTED_ENTITY_MISMATCH"), canonical


_PHRASE_FILLER = {
    "the", "a", "an", "of", "via", "to", "into", "onto", "on", "at", "in", "for",
    "and", "or", "by", "with", "within", "which", "that", "its", "their", "this",
    "following", "upon", "as", "from", "these", "both", "then",
}


def _tighten_label(phrase):
    """Reduce an over-captured clause to the trailing term.

    "which rapidly colocalize within the nucleoplasm" -> "nucleoplasm"
    "DNA damage stimulus"                              -> "DNA damage stimulus"
    """
    words = [w for w in re.split(r"\s+", phrase.strip()) if w]
    words = words[-3:]                       # a GO/term label is short
    while words and words[0].lower() in _PHRASE_FILLER:
        words.pop(0)
    return " ".join(words).strip(" ,;:-") or None


def extract_labeled_ids(text):
    """Yield (prefix, curie, claimed_label, start, end).

    Captures the two dominant LLM formats:
        CURIE (label)      e.g. GO:0006915 (apoptotic process)
        label (CURIE)      e.g. apoptotic process (GO:0006915)
    """
    for prefix, curie, start, end in extract_ids(text):
        claimed = None
        after = text[end:end + 90]
        m = re.match(r"\s*\(([^)]{2,70})\)", after)
        if m:
            claimed = m.group(1).strip()
        else:
            before = text[max(0, start - 70):start]
            # no comma/semicolon in the class -> stop at the nearest clause boundary
            m2 = re.search(r"([A-Za-z][A-Za-z0-9 /-]{2,55})\(\s*$", before)
            if m2:
                claimed = _tighten_label(m2.group(1))
        yield prefix, curie, claimed, start, end


def check_claims(text, online=True, entity_hint=None):
    """Verify existence, label consistency, and (with a hint) entity match.

    entity_hint: the gene/protein the text is *about* (e.g. from the question).
    UniProt/Ensembl IDs are checked against it - reliable, format-independent.
    Without a hint, correspondence is NOT accused (proximity guessing is
    unreliable), so the never-falsely-accuse guarantee holds.
    """
    from .validator import scan
    base = {(v.curie, v.start): v for v in scan(text, online=online)}
    out = []
    for prefix, curie, claimed, start, end in extract_labeled_ids(text):
        _rx, kind, arg, kind_label = ID_PATTERNS[prefix]
        v = base.get((curie, start))
        status = v.status if v else "UNVERIFIED"
        canonical = None

        if status == "SUPPORTED" and online:
            if kind in ("uniprot", "ensembl"):
                if entity_hint:
                    status, canonical = verify_entity(curie, kind, arg, entity_hint)
                else:
                    ent = sources.fetch_entity(kind, curie, arg)
                    canonical = ent.get("primary") if ent else None
                    status = "SUPPORTED_NO_LABEL"   # no known entity to check against
            elif not claimed:
                status = "SUPPORTED_NO_LABEL"
            else:
                # v0.5: ontology term - check its description/label
                ent = sources.fetch_entity(kind, curie, arg)
                if ent:
                    canonical = ent.get("primary")
                    if ent.get("obsolete"):
                        # obsolete terms often have only a placeholder label
                        # (e.g. "GO_0007050") - don't show it as the "real" name
                        if canonical and _is_placeholder(canonical, curie):
                            canonical = None
                        status = "SUPPORTED_OBSOLETE"
                    else:
                        names = _real_names(ent.get("names", []), curie)
                        m = _matches(claimed, names)
                        status = ("SUPPORTED_LABEL_OK" if m is True
                                  else "SUPPORTED_LABEL_MISMATCH" if m is False
                                  else "SUPPORTED_NO_LABEL")
        elif status == "SUPPORTED":
            status = "SUPPORTED_NO_LABEL"
        out.append(ClaimVerdict(curie, prefix, kind_label, claimed,
                                canonical, status, start, end))
    return out


FLAGGED_STATUSES = ("NOT_FOUND", "INVALID_FORMAT", "SUPPORTED_LABEL_MISMATCH",
                    "SUPPORTED_OBSOLETE", "SUPPORTED_ENTITY_MISMATCH")


def report_claims(text, online=True, entity_hint=None):
    verdicts = check_claims(text, online=online, entity_hint=entity_hint)
    flagged = [v for v in verdicts if v.status in FLAGGED_STATUSES]
    return {
        "n_ids": len(verdicts),
        "n_flagged": len(flagged),
        "verdicts": [asdict(v) for v in verdicts],
    }
