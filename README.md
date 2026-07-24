# bioclaim

**A grounding firewall for biomedical LLMs.** Wrap it around any model's output and it
verifies the biological identifiers against authoritative databases — UniProtKB, Ensembl,
and EBI's Ontology Lookup Service — flagging the ones that are fabricated.

Large language models constantly emit identifiers that *look* real but don't exist
(`GO:9999999`, `HP:9999999`), alongside false gene–function and gene–disease claims. In
research and clinical settings that is a documented safety risk. `bioclaim` is a
deterministic, low-latency layer that catches it.

> **Real-model finding:** across three models, **48–68% of specialist biology
> answers contained a wrong biomedical identifier** (Llama-3.1-8B 68%, gpt-oss-120B
> 60%, Llama-3.3-70B 48%). The dominant error is a real, valid accession pointing at
> the **wrong gene** — invisible to existence checks, independently verified.
> Full study: [RESULTS.md](RESULTS.md).

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
4. **ENTITY (v0.6)** — correspondence. A *real* UniProt/Ensembl ID attached to the
   *wrong* gene ("the UniProt for TP53 is P38398", actually BRCA1) is flagged
   `SUPPORTED_ENTITY_MISMATCH` — the hardest class, invisible to existence checks.

Supported identifier types: GO, HP, MONDO, DOID, CHEBI, Ensembl gene (ENSG), UniProtKB.

Every lookup is **cached to disk** ($BIOCLAIM_CACHE, else `~/.cache/bioclaim/`), so
after a warm-up bioclaim runs fast, offline-capable, and immune to rate limits.

## Install & use

```bash
pip install -e .           # from a clone; PyPI release: pip install bioclaim
```

**One-call API:**

```python
from bioclaim import check

result = check("TP53 (P04637) is annotated with GO:9999999 (apoptosis).")
print(result.ok)           # False
for p in result.problems:
    print(p)               # GO:9999999: fabricated (does not exist)
```

**Guard any model call** (raises if a fabrication slips through):

```python
from bioclaim import Firewall
guarded = Firewall(raise_on_flag=True).guard(call_my_llm)
answer = guarded(prompt)   # BioclaimFlag raised if the answer cites a fake ID
```

**Command line:**

```bash
bioclaim "TP53 is P04637 and the fake GO:9999999"
echo "some model output" | bioclaim --entity BRCA1
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
