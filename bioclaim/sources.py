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

_CACHE = {}
_HEADERS = {"User-Agent": "bioclaim/0.3 (grounding-firewall)"}

# be a good API citizen: minimum gap between outbound requests
_MIN_INTERVAL = 0.06
_last_call = [0.0]
_RETRY_CODES = {429, 500, 502, 503, 504}


def _throttle():
    gap = time.time() - _last_call[0]
    if gap < _MIN_INTERVAL:
        time.sleep(_MIN_INTERVAL - gap)
    _last_call[0] = time.time()


def _http(url, timeout=10, retries=4):
    """Return (status_code, body_bytes_or_None).

    Retries transient/rate-limit failures with exponential backoff. A definitive
    HTTP code (e.g. 404) is returned immediately with no body.
    """
    for attempt in range(retries):
        _throttle()
        try:
            req = urllib.request.Request(url, headers=_HEADERS)
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
    """UniProtKB REST: 200 exists, 404/400 not found."""
    code, _ = _http(f"https://rest.uniprot.org/uniprotkb/{acc}.json", timeout)
    if code == 200:
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
    """Dispatch to the right database checker, with caching."""
    key = (kind, curie)
    if key in _CACHE:
        return _CACHE[key]
    if kind == "ols":
        res = check_ols(curie, arg, timeout)
    elif kind == "uniprot":
        res = check_uniprot(curie, timeout)
    elif kind == "ensembl":
        res = check_ensembl(curie, timeout)
    else:
        res = None
    _CACHE[key] = res
    return res
