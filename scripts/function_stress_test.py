"""Live stress test for the v0.8 gene-function check (~100 real + fake pairs).

For each pair it runs `check(text, check_functions=True)` against live QuickGO and
scores it:
  PASS cases  = a real, well-annotated function -> should NOT be flagged
  FLAG cases  = an alien function (photosynthesis, pollen dev, ...) for a human
                protein -> should be flagged

Prints per-case results and a summary. The FLAG set is the rock-solid demo (a
human protein is never annotated with photosynthesis). A few PASS cases may flag
because GO annotations are specific/incomplete - that's the honest edge, not a bug.

    python scripts/function_stress_test.py
    python scripts/function_stress_test.py --only flag     # just the fake set
"""
import sys
import argparse
import itertools
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from bioclaim import check

# gene -> (UniProt accession, [ (GO id, name) real, well-annotated functions ])
GENES = {
    "TP53":  ("P04637", [("GO:0005634", "nucleus"),
                         ("GO:0003700", "DNA-binding transcription factor activity")]),
    "EGFR":  ("P00533", [("GO:0005886", "plasma membrane"), ("GO:0005524", "ATP binding")]),
    "KRAS":  ("P01116", [("GO:0005886", "plasma membrane"), ("GO:0005525", "GTP binding")]),
    "AKT1":  ("P31749", [("GO:0005524", "ATP binding"), ("GO:0005829", "cytosol")]),
    "TNF":   ("P01375", [("GO:0005576", "extracellular region"), ("GO:0005125", "cytokine activity")]),
    "INS":   ("P01308", [("GO:0005576", "extracellular region"), ("GO:0005179", "hormone activity")]),
    "ACTB":  ("P60709", [("GO:0005737", "cytoplasm"), ("GO:0005200", "structural constituent of cytoskeleton")]),
    "SOD1":  ("P00441", [("GO:0004784", "superoxide dismutase activity"), ("GO:0005737", "cytoplasm")]),
    "CASP3": ("P42574", [("GO:0004197", "cysteine-type endopeptidase activity"), ("GO:0005737", "cytoplasm")]),
    "MYC":   ("P01106", [("GO:0005634", "nucleus"), ("GO:0003677", "DNA binding")]),
    "ALB":   ("P02768", [("GO:0005576", "extracellular region")]),
    "VEGFA": ("P15692", [("GO:0005576", "extracellular region"), ("GO:0008083", "growth factor activity")]),
    "ESR1":  ("P03372", [("GO:0005634", "nucleus"), ("GO:0003700", "DNA-binding transcription factor activity")]),
    "MAPK1": ("P28482", [("GO:0005524", "ATP binding"), ("GO:0005829", "cytosol")]),
    "HBB":   ("P68871", [("GO:0005344", "oxygen carrier activity")]),
    "PTEN":  ("P60484", [("GO:0005737", "cytoplasm")]),
    "GAPDH": ("P04406", [("GO:0005737", "cytoplasm")]),
    "IL6":   ("P05231", [("GO:0005576", "extracellular region"), ("GO:0005125", "cytokine activity")]),
    "BRCA1": ("P38398", [("GO:0005634", "nucleus")]),
    "STAT3": ("P40763", [("GO:0005634", "nucleus"), ("GO:0003700", "DNA-binding transcription factor activity")]),
    "CDK1":  ("P06493", [("GO:0005524", "ATP binding"), ("GO:0005634", "nucleus")]),
    "MTOR":  ("P42345", [("GO:0005524", "ATP binding")]),
}

# plant / bacterial / photosynthetic - never annotated to a human protein
ALIEN = [
    ("GO:0015979", "photosynthesis"),
    ("GO:0009765", "photosynthesis, light harvesting"),
    ("GO:0015995", "chlorophyll biosynthetic process"),
    ("GO:0016168", "chlorophyll binding"),
    ("GO:0010207", "photosystem II assembly"),
    ("GO:0009399", "nitrogen fixation"),
    ("GO:0009555", "pollen development"),
    ("GO:0009860", "pollen tube growth"),
    ("GO:0009772", "photosynthetic electron transport in photosystem II"),
    ("GO:0080167", "response to karrikin"),
]


def build_cases():
    cases = []
    for g, (acc, trues) in GENES.items():
        for gid, name in trues:
            cases.append(("PASS", f"{g} (UniProt: {acc}) is annotated with {name} ({gid}).", g, gid))
    alien = itertools.cycle(ALIEN)
    for g, (acc, _t) in GENES.items():
        for _ in range(3):
            gid, name = next(alien)
            cases.append(("FLAG", f"{g} (UniProt: {acc}) carries out {name} ({gid}).", g, gid))
    return cases


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=["pass", "flag"], default=None)
    args = ap.parse_args()

    cases = build_cases()
    if args.only:
        cases = [c for c in cases if c[0] == args.only.upper()]

    f_ok = f_tot = p_ok = p_tot = 0
    misses = []
    print(f"Running {len(cases)} gene-function cases against live QuickGO "
          "(first run is slow; then cached)...\n")
    for i, (exp, text, g, gid) in enumerate(cases, 1):
        r = check(text, check_functions=True)
        flagged = any(p.status == "SUPPORTED_FUNCTION_UNSUPPORTED" for p in r.problems)
        got = "FLAG" if flagged else "PASS"
        ok = (got == exp)
        if exp == "FLAG":
            f_tot += 1; f_ok += ok
        else:
            p_tot += 1; p_ok += ok
        if not ok:
            misses.append((exp, g, gid))
        print(f"  {'ok ' if ok else 'XX '}[{i:>3}] want {exp} got {got}   {g:<6} {gid}")

    print("\n" + "=" * 56)
    print(f"  FAKE associations caught:  {f_ok}/{f_tot}"
          + (f"  ({100*f_ok/f_tot:.0f}%)" if f_tot else ""))
    print(f"  REAL associations passed:  {p_ok}/{p_tot}"
          + (f"  ({100*p_ok/p_tot:.0f}%)" if p_tot else ""))
    print("=" * 56)
    if misses:
        print("\nmismatches (want vs got):")
        for exp, g, gid in misses:
            print(f"   {g} {gid}: expected {exp}")
        print("\nNote: a PASS that flags usually means GO annotates that gene to a "
              "more specific / regulatory term than the one named - annotation "
              "specificity, not a tool error. FAKE-association catches are definitive.")


if __name__ == "__main__":
    main()
