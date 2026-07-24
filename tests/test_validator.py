import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from bioclaim import scan, report


def test_extracts_and_formats():
    txt = "GO:0006915 and ENSG00000141510 and UniProt P04637"
    v = {x.curie: x for x in scan(txt, online=False)}
    assert "GO:0006915" in v and v["GO:0006915"].format_ok
    assert "ENSG00000141510" in v
    assert "P04637" in v

def test_flags_malformed():
    # GO ids must be exactly 7 digits; this one has 6
    v = {x.curie: x for x in scan("bad id GO:000691", online=False)}
    # 6-digit code is not matched at all (won't masquerade as valid)
    assert "GO:000691" not in v

def test_report_shape():
    r = report("GO:0006915", online=False)
    assert r["n_ids"] == 1 and "verdicts" in r
    print("all offline tests passed")

if __name__ == "__main__":
    test_extracts_and_formats(); test_flags_malformed(); test_report_shape()
    print("OK")
