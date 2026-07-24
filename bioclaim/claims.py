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
            before = text[max(0, start - 90):start]
            m2 = re.search(r"([A-Za-z][A-Za-z0-9 ,'/-]{2,68})\s*\(\s*$", before)
            if m2:
                claimed = m2.group(1).strip()
        yield prefix, curie, claimed, start, end


def check_claims(text, online=True):
    """Verify existence AND label consistency for every identifier in text."""
    from .validator import scan
    base = {(v.curie, v.start): v for v in scan(text, online=online)}
    out = []
    for prefix, curie, claimed, start, end in extract_labeled_ids(text):
        _rx, kind, arg, kind_label = ID_PATTERNS[prefix]
        v = base.get((curie, start))
        status = v.status if v else "UNVERIFIED"
        canonical = None

        if status == "SUPPORTED":
            if not claimed:
                status = "SUPPORTED_NO_LABEL"
            elif online:
                ent = sources.fetch_entity(kind, curie, arg)
                if ent:
                    canonical = ent.get("primary")
                    if ent.get("obsolete"):
                        # deprecated identifier: an honest, distinct finding,
                        # never a label "mismatch" against a stale name.
                        status = "SUPPORTED_OBSOLETE"
                    else:
                        names = _real_names(ent.get("names", []), curie)
                        m = _matches(claimed, names)
                        status = ("SUPPORTED_LABEL_OK" if m is True
                                  else "SUPPORTED_LABEL_MISMATCH" if m is False
                                  else "SUPPORTED_NO_LABEL")
                # ent is None -> leave status SUPPORTED (couldn't fetch name)
        out.append(ClaimVerdict(curie, prefix, kind_label, claimed,
                                canonical, status, start, end))
    return out


def report_claims(text, online=True):
    verdicts = check_claims(text, online=online)
    flagged = [v for v in verdicts
               if v.status in ("NOT_FOUND", "INVALID_FORMAT",
                               "SUPPORTED_LABEL_MISMATCH", "SUPPORTED_OBSOLETE")]
    return {
        "n_ids": len(verdicts),
        "n_flagged": len(flagged),
        "verdicts": [asdict(v) for v in verdicts],
    }
