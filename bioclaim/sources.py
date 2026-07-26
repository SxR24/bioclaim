"""Live existence checkers against authoritative biomedical databases.

Each function returns:
    True  -> the identifier exists
    False -> well-formed but NOT found (the fabricated-ID catch)
    None  -> could not verify (network/API problem) -> never a false accusation

A single HTTP helper adds polite throttling + retry-with-backoff so that
rate-limit responses (429/503) are retried rather than mistaken for "unknown".
Results are cached in-process so repeat lookups are free.
"""
import json
import time
import urllib.request
import urllib.parse
import urllib.error

from .cache import DiskCache, MISS

_CACHE = DiskCache("exists")          # persistent: id -> exists (bool)
_HEADERS = {"User-Agent": "bioclaim/0.7 (grounding-firewall)"}

# be a good API citizen: minimum gap between outbound requests
_MIN_INTERVAL = 0.06
_last_call = [0.0]
_RETRY_CODES = {429, 500, 502, 503, 504}


def _throttle():
    gap = time.time() - _last_call[0]
    if gap < _MIN_INTERVAL:
        time.sleep(_MIN_INTERVAL - gap)
    _last_call[0] = time.time()


def _http(url, timeout=10, retries=4, extra_headers=None):
    """Return (status_code, body_bytes_or_None).

    Retries transient/rate-limit failures with exponential backoff. A definitive
    HTTP code (e.g. 404) is returned immediately with no body.
    """
    headers = dict(_HEADERS)
    if extra_headers:
        headers.update(extra_headers)
    for attempt in range(retries):
        _throttle()
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.getcode(), r.read()
        except urllib.error.HTTPError as e:
            if e.code in _RETRY_CODES:
                time.sleep(0.5 * (2 ** attempt))  # 0.5, 1, 2, 4s
                continue
            return e.code, None                    # definitive (e.g. 404)
        except Exception:
            time.sleep(0.4 * (2 ** attempt))
            continue
    return None, None                              # gave up -> unknown


def check_ols(curie, slug, timeout=10):
    """EBI OLS4: exact term lookup by OBO id."""
    url = (f"https://www.ebi.ac.uk/ols4/api/ontologies/{slug}/terms"
           f"?obo_id={urllib.parse.quote(curie)}")
    code, body = _http(url, timeout)
    if code == 404:
        return False
    if code != 200 or body is None:
        return None
    try:
        data = json.loads(body.decode())
    except Exception:
        return None
    total = data.get("page", {}).get("totalElements")
    if total is not None:
        return total > 0
    return bool(data.get("_embedded", {}).get("terms"))


def check_uniprot(acc, timeout=10):
    """UniProtKB REST: 200 exists, 404/400 not found.

    A deleted/demerged accession returns 200 with entryType "Inactive" - treat
    that as not-found, since it no longer resolves to a protein.
    """
    code, body = _http(f"https://rest.uniprot.org/uniprotkb/{acc}.json", timeout)
    if code == 200:
        if body:
            try:
                if json.loads(body.decode()).get("entryType", "").lower().startswith("inactive"):
                    return False        # deleted / demerged accession
            except Exception:
                pass
        return True
    if code in (400, 404):
        return False
    return None


def check_ensembl(ensg, timeout=10):
    """Ensembl REST lookup: 200 exists, 400/404 not found."""
    code, _ = _http(
        f"https://rest.ensembl.org/lookup/id/{ensg}?content-type=application/json",
        timeout)
    if code == 200:
        return True
    if code in (400, 404):
        return False
    return None


def exists(kind, curie, arg, timeout=10):
    """Dispatch to the right database checker, with persistent caching.

    Only definitive True/False is cached; a None (network failure) is never
    stored, so a transient hiccup can't poison the cache.
    """
    key = f"{kind}:{curie}"
    cached = _CACHE.get(key)
    if cached is not MISS:
        return cached
    if kind == "ols":
        res = check_ols(curie, arg, timeout)
    elif kind == "uniprot":
        res = check_uniprot(curie, timeout)
    elif kind == "ensembl":
        res = check_ensembl(curie, timeout)
    else:
        res = None
    if res is not None:
        _CACHE.set(key, res)
    return res


# ---------------------------------------------------------------------------
# v0.5: fetch the canonical name(s) of an entity, for claim/label verification.
# Returns {"primary": <name>, "names": [name, synonyms...]} or None.
# ---------------------------------------------------------------------------
_ENTITY_CACHE = DiskCache("entities")   # persistent: id -> entity dict


def _ols_entity(curie, slug, timeout=10):
    url = (f"https://www.ebi.ac.uk/ols4/api/ontologies/{slug}/terms"
           f"?obo_id={urllib.parse.quote(curie)}")
    code, body = _http(url, timeout)
    if code != 200 or body is None:
        return None
    try:
        terms = json.loads(body.decode()).get("_embedded", {}).get("terms", [])
    except Exception:
        return None
    if not terms:
        return None
    # OLS can return several entries for one id (e.g. an active term plus an
    # obsolete duplicate/alt-id). Prefer the ACTIVE, defining term so a live
    # term is never mislabeled obsolete because a stale duplicate came first.
    t = max(terms, key=lambda x: (not bool(x.get("is_obsolete")),
                                  bool(x.get("is_defining_ontology"))))
    label = t.get("label")
    obsolete = bool(t.get("is_obsolete")) or (
        isinstance(label, str) and label.lower().startswith("obsolete"))
    names = []
    if label:
        names.append(label)
    for s in t.get("synonyms") or []:
        if isinstance(s, str):
            names.append(s)
    for s in t.get("obo_synonym") or []:
        if isinstance(s, dict) and s.get("name"):
            names.append(s["name"])
    return {"primary": label, "names": names, "symbols": [], "obsolete": obsolete}


def _uniprot_entity(acc, timeout=10):
    code, body = _http(f"https://rest.uniprot.org/uniprotkb/{acc}.json", timeout)
    if code != 200 or body is None:
        return None
    try:
        d = json.loads(body.decode())
    except Exception:
        return None
    names, symbols = [], []
    pd = d.get("proteinDescription", {})
    rec = pd.get("recommendedName", {}).get("fullName", {}).get("value")
    if rec:
        names.append(rec)
    for alt in pd.get("alternativeNames", []) or []:
        v = alt.get("fullName", {}).get("value")
        if v:
            names.append(v)
    for g in d.get("genes", []) or []:
        gn = g.get("geneName", {}).get("value")
        if gn:
            names.append(gn)
            symbols.append(gn)
        for syn in g.get("synonyms", []) or []:
            if syn.get("value"):
                names.append(syn["value"])
                symbols.append(syn["value"])
    return {"primary": rec, "names": names, "symbols": symbols, "obsolete": False}


def _ensembl_entity(ensg, timeout=10):
    code, body = _http(
        f"https://rest.ensembl.org/lookup/id/{ensg}?content-type=application/json",
        timeout)
    if code != 200 or body is None:
        return None
    try:
        d = json.loads(body.decode())
    except Exception:
        return None
    names, symbols = [], []
    if d.get("display_name"):
        names.append(d["display_name"])
        symbols.append(d["display_name"])
    if d.get("description"):
        names.append(d["description"].split(" [")[0])
    return {"primary": d.get("display_name"), "names": names,
            "symbols": symbols, "obsolete": False}


# ---------------------------------------------------------------------------
# v0.8: does a gene product actually carry a given GO term? (EBI QuickGO)
# True  -> the gene is annotated with the term (or a descendant of it)
# False -> it is not among the gene's annotations
# None  -> could not verify (never accuse on uncertainty)
# ---------------------------------------------------------------------------
_FUNC_CACHE = DiskCache("functions")


def gene_has_go(accession, go_id, timeout=12):
    """Is `accession` annotated with `go_id` (respecting GO propagation)?"""
    key = f"{accession}:{go_id}"
    cached = _FUNC_CACHE.get(key)
    if cached is not MISS:
        return cached
    url = ("https://www.ebi.ac.uk/QuickGO/services/annotation/search"
           f"?geneProductId=UniProtKB:{urllib.parse.quote(accession)}"
           f"&goId={urllib.parse.quote(go_id)}"
           "&goUsage=descendants&goUsageRelationships=is_a,part_of,occurs_in&limit=1")
    code, body = _http(url, timeout, extra_headers={"Accept": "application/json"})
    res = None
    if code == 200 and body:
        try:
            res = json.loads(body.decode()).get("numberOfHits", 0) > 0
        except Exception:
            res = None
    # any non-200 (bad request, obsolete term, error) -> unknown, never accuse
    if res is not None:
        _FUNC_CACHE.set(key, res)
    return res


def fetch_entity(kind, curie, arg, timeout=10):
    key = f"{kind}:{curie}"
    cached = _ENTITY_CACHE.get(key)
    if cached is not MISS:
        return cached
    if kind == "ols":
        res = _ols_entity(curie, arg, timeout)
    elif kind == "uniprot":
        res = _uniprot_entity(curie, timeout)
    elif kind == "ensembl":
        res = _ensembl_entity(curie, timeout)
    else:
        res = None
    if res is not None:
        _ENTITY_CACHE.set(key, res)
    return res
