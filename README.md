# bioclaim

**A grounding firewall for biomedical LLMs.** Wrap it around any model's output and it
verifies the biological identifiers against authoritative databases — UniProtKB, Ensembl,
and EBI's Ontology Lookup Service — flagging the ones that are fabricated.

Large language models constantly emit identifiers that *look* real but don't exist
(`GO:9999999`, `HP:9999999`), alongside false gene–function and gene–disease claims. In
research and clinical settings that is a documented safety risk. `bioclaim` is a
deterministic, low-latency layer that catches it.

> **Real-model finding:** on 40 specialist biology questions, Llama-3.3-70B
> fabricated a biomedical identifier in **15% of answers** — almost always when
> asked to produce a fixed number of IDs. Full study: [RESULTS.md](RESULTS.md).

## Benchmark result

On a labeled set of **500 LLM-style answers** (394 injected fabrications):

| Metric | Score |
| --- | --- |
| Precision (flagged that were truly fake) | **100.0%** |
| Recall (fabrications caught) | **95.7%** (377 / 394) |
| F1 | **0.978** |
| False accusations | **0** |

Every uncaught fabrication was a network-throttled lookup that safely returned
`UNVERIFIED` — not a single fake was checked and missed. Reproduce with:

```bash
python scripts/generate_benchmark.py 500
python scripts/benchmark.py data/benchmark_large.jsonl
```

## How it works

Two layers, both designed to **never falsely accuse** (if a claim can't be verified it is
marked `UNVERIFIED`, never `NOT_FOUND`):

1. **FORMAT** — offline, deterministic. Rejects malformed identifiers.
2. **EXISTS** — live existence check against the source database. Well-formed but absent
   identifiers are flagged `NOT_FOUND`. Rate-limit/network errors are retried with backoff,
   then degrade to `UNVERIFIED`.
3. **CLAIM (v0.5)** — label consistency. A *real* identifier with a *wrong* description
   (`GO:0006281 (photosynthesis)`, actually "DNA repair") is flagged
   `SUPPORTED_LABEL_MISMATCH`. Synonym-aware, so paraphrases aren't falsely flagged.

Supported identifier types: GO, HP, MONDO, DOID, CHEBI, Ensembl gene (ENSG), UniProtKB.

```python
from bioclaim import report_claims
r = report_claims("Model says GO:0006281 (photosynthesis).")   # -> SUPPORTED_LABEL_MISMATCH
```

## Install & use

```bash
git clone https://github.com/SxR24/bioclaim.git
cd bioclaim
pip install -e .          # optional; scripts also run without installing
```

```python
from bioclaim import report

r = report("TP53 (P04637) is annotated with GO:0006915 and the invalid term GO:9999999.")
for v in r["verdicts"]:
    print(v["curie"], v["status"])   # SUPPORTED | NOT_FOUND | INVALID_FORMAT | UNVERIFIED
```

## Project layout

```
bioclaim/              core package (patterns, live sources, validator)
scripts/               runnable CLIs: demo, batch, benchmark, generate_benchmark
data/                  sample_answers.jsonl (labeled demo set)
tests/                 offline unit tests
```

Run the pieces (from the repo root):

```bash
python scripts/demo.py                     # catch fakes in one example answer
python scripts/benchmark.py                # precision/recall on the sample set
python scripts/batch.py your_answers.jsonl # scan your own AI answers
python -m pytest                           # run tests
```

## Roadmap (land-and-expand)

- **v0.1–0.3** Identifier validation across ontologies, genes, and proteins *(done)*
- **v0.4** Local database snapshots — microsecond lookups, fully offline, true 100% recall
- **v0.5** Claim verification — relationships, not just IDs (gene–disease, gene–function)
- **v0.6** Calibrated confidence per claim
- **v1.0** Public leaderboard + LLM-framework integrations

## Why this design wins

Generality (all identifier types, one layer) · Deployability (pure standard library,
3-line integration) · Speed (deterministic lookups, not agent loops) · Trust (never a
false accusation).

## License

MIT — see [LICENSE](LICENSE).
