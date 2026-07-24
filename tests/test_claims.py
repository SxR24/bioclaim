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


def test_entity_correspondence(monkeypatch=None):
    # v0.6: real ID for the WRONG gene must be flagged
    S.exists = lambda kind, curie, arg, timeout=10: True
    S.fetch_entity = lambda kind, curie, arg, timeout=10: {
        "P38398": {"primary": "BRCA1 protein", "names": ["BRCA1"],
                   "symbols": ["BRCA1"], "obsolete": False},
        "P04637": {"primary": "Cellular tumor antigen p53",
                   "names": ["TP53", "P53"], "symbols": ["TP53", "P53"],
                   "obsolete": False},
    }.get(curie)
    # v0.6: entity check is anchored to the known gene (entity_hint)
    ok = {v.curie: v.status for v in claims.check_claims(
        "BRCA1 has UniProt P38398.", online=True, entity_hint="BRCA1")}
    bad = {v.curie: v.status for v in claims.check_claims(
        "BRCA1 has UniProt P04637.", online=True, entity_hint="BRCA1")}
    assert ok["P38398"] == "SUPPORTED_ENTITY_OK"
    assert bad["P04637"] == "SUPPORTED_ENTITY_MISMATCH"
    # without a hint, correspondence is never accused
    none = {v.curie: v.status for v in claims.check_claims(
        "BRCA1 has UniProt P04637.", online=True, entity_hint=None)}
    assert none["P04637"] == "SUPPORTED_NO_LABEL"
    print("entity-correspondence test passed")


def test_target_entity_extraction():
    ex = claims.extract_target_entity
    assert ex("List 8 GO terms for the gene FUS.") == "FUS"
    assert ex("What is the UniProt accession for the human protein CFTR?") == "CFTR"
    assert ex("UniProt for the human protein Neurexin-1 (NRXN1)?") == "NRXN1"
    assert ex("Provide 6 GO molecular function terms for SOD1.") == "SOD1"
    assert ex("What MONDO ID corresponds to Fabry disease?") is None
    print("target-entity extraction test passed")


if __name__ == "__main__":
    test_label_parsing()
    test_matching_is_synonym_aware()
    test_end_to_end_with_mocked_db()
    test_entity_correspondence()
    test_target_entity_extraction()
    print("OK")
