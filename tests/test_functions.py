import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import bioclaim.sources as S
from bioclaim import check

_ENT = {
    "P04637": {"primary": "Cellular tumor antigen p53", "names": ["TP53"],
               "symbols": ["TP53"], "obsolete": False},
    "GO:0006281": {"primary": "DNA repair", "names": ["DNA repair"],
                   "symbols": [], "obsolete": False},
    "GO:0015979": {"primary": "photosynthesis", "names": ["photosynthesis"],
                   "symbols": [], "obsolete": False},
}

TEXT = ("TP53 (UniProt P04637) is annotated with GO:0006281 (DNA repair) "
        "and GO:0015979 (photosynthesis).")


def _setup():
    S.exists = lambda kind, curie, arg, timeout=10: True
    S.fetch_entity = lambda kind, curie, arg, timeout=10: _ENT.get(curie)
    # TP53 does DNA repair, does NOT do photosynthesis
    S.gene_has_go = lambda acc, go, timeout=12: {"GO:0006281": True,
                                                 "GO:0015979": False}.get(go)


def test_default_off_does_not_flag_associations():
    _setup()
    r = check(TEXT)                       # check_functions defaults to False
    assert r.ok, f"default behaviour changed: {r.problems}"
    print("default (off) unchanged: ok")


def test_functions_flags_false_association():
    _setup()
    r = check(TEXT, check_functions=True)
    flagged = {p.curie: p.status for p in r.problems}
    assert flagged.get("GO:0015979") == "SUPPORTED_FUNCTION_UNSUPPORTED"
    assert "GO:0006281" not in flagged   # real annotation -> not flagged
    print("function check flags false association:", str(r.problems[0]))


def test_ambiguous_target_is_skipped():
    # two different accessions -> no unambiguous gene -> never guess
    _setup()
    txt = "P04637 and P38398 with GO:0015979 (photosynthesis)."
    r = check(txt, check_functions=True)
    assert all(p.status != "SUPPORTED_FUNCTION_UNSUPPORTED" for p in r.problems)
    print("ambiguous target skipped: ok")


def test_uncertainty_never_accuses():
    _setup()
    S.gene_has_go = lambda acc, go, timeout=12: None   # could not verify
    r = check(TEXT, check_functions=True)
    assert all(p.status != "SUPPORTED_FUNCTION_UNSUPPORTED" for p in r.problems)
    print("uncertainty -> no accusation: ok")


if __name__ == "__main__":
    test_default_off_does_not_flag_associations()
    test_functions_flags_false_association()
    test_ambiguous_target_is_skipped()
    test_uncertainty_never_accuses()
    print("OK")
