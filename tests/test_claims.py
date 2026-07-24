import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from bioclaim import claims
import bioclaim.sources as S


def test_label_parsing():
    txt = "GO:0006915 (apoptotic process) and GO:9999999"
    got = {c: lbl for _p, c, lbl, _s, _e in claims.extract_labeled_ids(txt)}
    assert got["GO:0006915"] == "apoptotic process"
    assert got["GO:9999999"] is None


def test_matching_is_synonym_aware():
    assert claims._matches("apoptosis", ["apoptotic process", "apoptosis"]) is True
    assert claims._matches("photosynthesis", ["DNA repair"]) is False
    assert claims._matches("", ["DNA repair"]) is None


def test_end_to_end_with_mocked_db(monkeypatch=None):
    # mock existence + entity lookups so the test runs offline
    S.exists = lambda kind, curie, arg, timeout=10: curie != "GO:9999999"
    S.fetch_entity = lambda kind, curie, arg, timeout=10: {
        "GO:0006915": {"primary": "apoptotic process",
                       "names": ["apoptotic process", "apoptosis"]},
        "GO:0006281": {"primary": "DNA repair", "names": ["DNA repair"]},
    }.get(curie)
    txt = ("GO:0006915 (apoptotic process) GO:0006281 (photosynthesis) "
           "GO:9999999 (x)")
    status = {v.curie: v.status for v in claims.check_claims(txt, online=True)}
    assert status["GO:0006915"] == "SUPPORTED_LABEL_OK"
    assert status["GO:0006281"] == "SUPPORTED_LABEL_MISMATCH"
    assert status["GO:9999999"] == "NOT_FOUND"
    print("all claim tests passed")


if __name__ == "__main__":
    test_label_parsing()
    test_matching_is_synonym_aware()
    test_end_to_end_with_mocked_db()
    print("OK")
