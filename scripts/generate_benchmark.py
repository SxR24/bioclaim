"""generate_benchmark.py - build a large LABELED benchmark for bioclaim.

Pulls REAL identifiers live from authoritative sources (EBI OLS4 for GO/HPO,
UniProt REST for proteins), generates guaranteed-FAKE ones (numeric ranges that
do not exist), then assembles many LLM-style answers that mix them - recording
the ground-truth fabricated IDs per answer.

Output: data/benchmark_large.jsonl   (feed it to  python benchmark.py <file>)

Usage:
    python scripts/generate_benchmark.py            # defaults: ~400 answers
    python scripts/generate_benchmark.py 800        # ask for more
"""
import sys
import json
import random
import time
import re
import pathlib
import urllib.request
import urllib.parse

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

random.seed(7)
HEADERS = {"User-Agent": "bioclaim-benchmark/0.1"}

# --- confirmed-real fallback pool (used only if the network fetch fails) ---
FALLBACK_REAL = {
    "GO": ["GO:0006915", "GO:0008150", "GO:0016020", "GO:0005515", "GO:0003674"],
    "HP": ["HP:0001250", "HP:0000707", "HP:0001263", "HP:0000118"],
    "UNIPROT": ["P04637", "P38398", "P00533", "P01308", "Q9Y6K9"],
}


def _get(url, timeout=15):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode()


def fetch_ontology_real(slug, prefix, want=80):
    """List real terms from OLS4 and keep valid CURIEs for this prefix."""
    out = []
    rx = re.compile(rf"\b{prefix}:\d+\b")
    try:
        size = min(500, max(want * 2, 100))
        data = json.loads(_get(f"https://www.ebi.ac.uk/ols4/api/ontologies/"
                               f"{slug}/terms?size={size}"))
        for t in data.get("_embedded", {}).get("terms", []):
            oid = t.get("obo_id")
            if oid and rx.fullmatch(oid):
                out.append(oid)
    except Exception as e:
        print(f"  [warn] OLS fetch for {prefix} failed ({e}); using fallback")
    return list(dict.fromkeys(out))[:want]


def fetch_uniprot_real(want=80):
    """Reviewed human accessions from UniProt REST (one per line)."""
    try:
        q = urllib.parse.urlencode({
            "query": "reviewed:true AND organism_id:9606",
            "fields": "accession", "format": "list", "size": min(500, want * 2)})
        txt = _get(f"https://rest.uniprot.org/uniprotkb/search?{q}")
        accs = [l.strip() for l in txt.splitlines() if l.strip()]
        return accs[:want]
    except Exception as e:
        print(f"  [warn] UniProt fetch failed ({e}); using fallback")
        return []


def make_fakes(prefix, n, width=7):
    """Guaranteed-nonexistent IDs: numbers in an unused high range."""
    fakes = set()
    while len(fakes) < n:
        num = random.randint(9_900_000, 9_999_999)
        fakes.add(f"{prefix}:{num:0{width}d}")
    return list(fakes)


def make_fake_ensg(n):
    fakes = set()
    while len(fakes) < n:
        fakes.add("ENSG" + str(random.randint(99_900_000_000, 99_999_999_999)))
    return list(fakes)


TEMPLATES = [
    "The gene product {r0} is functionally annotated with {r1}.",
    "In this study, {r0} and {r1} were both implicated in the phenotype {r2}.",
    "The model reports that {r0} localizes to {r1}, consistent with prior work.",
    "Annotation pipeline output: {r0}, {r1}, and {r2} for the target locus.",
    "The protein {r0} participates in the biological process {r1}.",
    "Clinical summary: variant affects {r0}; associated terms include {r1} and {r2}.",
]


def build_answers(real_pool, fake_pool, k, fake_prob=0.5):
    answers = []
    for i in range(1, k + 1):
        reals = [random.choice(real_pool) for _ in range(3)]
        tmpl = random.choice(TEMPLATES)
        text = tmpl.format(r0=reals[0], r1=reals[1], r2=reals[2])
        fabricated = []
        if random.random() < fake_prob:
            for f in random.sample(fake_pool, random.randint(1, 2)):
                text += f" It also cites {f}."
                fabricated.append(f)
        answers.append({"id": i, "answer": text, "fabricated": fabricated})
    return answers


def main(k=400):
    print("Fetching real identifiers from live databases...")
    go = fetch_ontology_real("go", "GO", 80) or FALLBACK_REAL["GO"]
    hp = fetch_ontology_real("hp", "HP", 80) or FALLBACK_REAL["HP"]
    up = fetch_uniprot_real(80) or FALLBACK_REAL["UNIPROT"]
    real_pool = go + hp + up
    print(f"  real pool: {len(go)} GO + {len(hp)} HP + {len(up)} UniProt "
          f"= {len(real_pool)} identifiers")

    fake_pool = make_fakes("GO", 60) + make_fakes("HP", 60) + make_fake_ensg(60)
    print(f"  fake pool: {len(fake_pool)} guaranteed-nonexistent identifiers")

    answers = build_answers(real_pool, fake_pool, k)
    n_fakes = sum(len(a["fabricated"]) for a in answers)
    out = "data/benchmark_large.jsonl"
    with open(out, "w", encoding="utf-8") as f:
        for a in answers:
            f.write(json.dumps(a) + "\n")
    print(f"\nWrote {len(answers)} answers ({n_fakes} injected fabrications) -> {out}")
    print(f"Next:  python benchmark.py {out}")
    print("(benchmark verifies every ID live; expect a few minutes on first run)")


if __name__ == "__main__":
    k = int(sys.argv[1]) if len(sys.argv) > 1 else 400
    main(k)
