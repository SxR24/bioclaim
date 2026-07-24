import os
import sys
import pathlib
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import bioclaim.sources as S
from bioclaim import check, Result, Firewall, BioclaimFlag
from bioclaim.cache import DiskCache, MISS


def test_check_flags_fabricated():
    S.exists = lambda kind, curie, arg, timeout=10: curie != "GO:9999999"
    S.fetch_entity = lambda *a, **k: None
    r = check("Real GO:0006915 and fake GO:9999999.", online=True)
    assert isinstance(r, Result)
    assert not r.ok
    flagged = {p.curie for p in r.problems}
    assert "GO:9999999" in flagged
    assert "GO:0006915" not in flagged
    print("check() flags fabricated: ok")


def test_result_is_truthy_when_clean():
    S.exists = lambda *a, **k: True
    S.fetch_entity = lambda *a, **k: None
    r = check("GO:0006915 is fine.", online=True)
    assert r.ok and bool(r) is True
    print("Result truthiness: ok")


def test_firewall_raises_on_flag():
    S.exists = lambda *a, **k: False
    S.fetch_entity = lambda *a, **k: None
    fw = Firewall(raise_on_flag=True)
    try:
        fw("cites GO:9999999")
        assert False, "should have raised"
    except BioclaimFlag as e:
        assert "GO:9999999" in str(e)
    print("Firewall raises: ok")


def test_disk_cache_persists():
    d = tempfile.mkdtemp()
    os.environ["BIOCLAIM_CACHE"] = d
    try:
        c = DiskCache("t")
        assert c.get("k") is MISS
        c.set("k", True)
        c.flush()
        assert DiskCache("t").get("k") is True   # reloaded from disk
    finally:
        os.environ.pop("BIOCLAIM_CACHE", None)
    print("disk cache persists: ok")


if __name__ == "__main__":
    test_check_flags_fabricated()
    test_result_is_truthy_when_clean()
    test_firewall_raises_on_flag()
    test_disk_cache_persists()
    print("OK")
