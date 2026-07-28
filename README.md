# bioclaim

**A grounding firewall for biomedical LLMs.** Wrap it around any model's output and it
verifies the biological identifiers against authoritative databases — UniProtKB, Ensembl,
and EBI's Ontology Lookup Service — flagging the ones that are fabricated.

Large language models constantly emit identifiers that *look* real but don't exist
(`GO:9999999`, `HP:9999999`), alongside false gene–function and gene–disease claims. In
research and clinical settings that is a documented safety risk. `bioclaim` is a
deterministic, low-latency layer that catches it.

> **Real-model finding:** across **six** models, **25–68% of specialist biology answers
> contained a wrong biomedical identifier** — including OpenAI's GPT-4o (25%) and GPT-5
> (40%). Reliability is not monotonic in capability: the newest reasoning model (GPT-5)
> was *worse* than GPT-4o, and its errors were all real IDs used wrongly (e.g. returning
> the MONDO ID for *lupus* when asked for alkaptonuria). Independently audited, zero
> false positives. Full study: [RESULTS.md](RESULTS.md).

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

Five layers, all designed to **never falsely accuse** (if a claim can't be verified it is
marked `UNVERIFIED`, never flagged):

1. **FORMAT** — offline, deterministic. Rejects malformed identifiers.
2. **EXISTS** — live existence check against the source database. Well-formed but absent
   identifiers are flagged `NOT_FOUND`. Rate-limit/network errors are retried with backoff,
   then degrade to `UNVERIFIED`.
3. **CLAIM (v0.5)** — label consistency. A *real* identifier with a *wrong* description
   (`GO:0006281 (photosynthesis)`, actually "DNA repair") is flagged
   `SUPPORTED_LABEL_MISMATCH`. Synonym-aware, so paraphrases aren't falsely flagged.
4. **ENTITY (v0.6)** — correspondence. A *real* UniProt/Ensembl ID attached to the
   *wrong* gene ("the UniProt for TP53 is P38398", actually BRCA1) is flagged
   `SUPPORTED_ENTITY_MISMATCH` — invisible to existence checks.
5. **FUNCTION (v0.8, opt-in)** — association. A *real, correctly-named* GO term
   assigned to a gene that isn't annotated with it ("TP53 does photosynthesis,
   GO:0015979") is flagged `SUPPORTED_FUNCTION_UNSUPPORTED`, via QuickGO annotations
   (GO-hierarchy aware). Existence *and* label checks pass this — only annotation
   verification catches it. Off by default; enable with `check_functions=True`.

Supported identifier types: GO, HP, MONDO, DOID, CHEBI, Ensembl gene (ENSG), UniProtKB.

Every lookup is **cached to disk** ($BIOCLAIM_CACHE, else `~/.cache/bioclaim/`), so
after a warm-up bioclaim runs fast, offline-capable, and immune to rate limits.

## Installation

```bash
pip install bioclaim
```

Pure Python standard library — no dependencies. This installs both the `bioclaim`
command and the importable package.

## Usage

The mental model never changes: **you hand bioclaim some text — an LLM's answer, a
paragraph, a document — and it tells you which biomedical identifiers in it are
fabricated, mislabeled, misassigned, or deprecated.** It does not call any model; it
screens whatever text you give it.

### Command line

```bash
# check text directly (whatever is in the quotes gets checked)
bioclaim "TP53 is P04637 and the fabricated GO:9999999"

# pipe a model's output or a file in (best for long/messy text)
echo "some model output" | bioclaim
bioclaim < answer.txt

# tell it the gene the text is about, to also catch wrong-gene IDs
bioclaim --entity BRCA1 "the accession is P04637"    # P04637 is TP53 -> flagged

# also verify each GO term is actually annotated to the gene (opt-in)
bioclaim --functions "TP53 (P04637) does photosynthesis (GO:0015979)"

# offline: format check only, no network
bioclaim --offline "GO:0006915"

bioclaim --version
```

Exit code is `0` when clean and `1` when anything is flagged, so it fits scripts and CI:

```bash
bioclaim "$answer" && echo "safe to use" || echo "flagged!"
```

### Python — one call

```python
from bioclaim import check

result = check("TP53 (P04637) is annotated with GO:9999999 (apoptosis).")
result.ok            # False   (True if nothing is flagged)
result.n_ids         # 3       (identifiers examined)
for p in result.problems:
    print(p)         # GO:9999999: fabricated (does not exist)

check(answer, entity_hint="BRCA1")   # pass the intended gene -> wrong-gene check
check(answer, check_functions=True)  # also verify the gene carries each GO term
check(answer, online=False)          # offline, format check only
```

### Python — guard a model call (the firewall)

```python
from bioclaim import Firewall

# non-raising: inspect the result yourself
result = Firewall()(model_answer)

# raising: stop the pipeline if a fabrication slips through
guarded = Firewall(raise_on_flag=True).guard(call_my_llm)
answer = guarded(prompt)             # raises BioclaimFlag on a flagged identifier
```

### What the verdicts mean

| Verdict | Meaning |
| --- | --- |
| *(clean)* | identifier exists and is consistent with its context |
| **fabricated** | does not exist in any database (incl. deleted/inactive accessions) |
| **wrong description** | real id, wrong label — e.g. `GO:0005634` ("nucleus") called "nucleoplasm" |
| **wrong gene/entity** | real accession, but for a different gene (needs `--entity` / `entity_hint`) |
| **obsolete / deprecated** | real id, but retired from the database |
| **not among the gene's GO annotations** | real, correctly-named GO term, but the gene isn't annotated with it (opt-in, `check_functions=True`) |
| **unverifiable** | could not reach the database — never counted as a problem |

Supported identifier types: GO, HP, MONDO, DOID, ChEBI, Ensembl gene (ENSG), and
UniProtKB (both official accession forms, with deleted/inactive detection).

### Try it on realistic text

The repo ships expert-style passages that mix real, fabricated, deprecated, and
misassigned identifiers, with an answer key:

```bash
bioclaim < examples/sample_paragraphs.txt
```

### Caching

Every database lookup is cached to disk (`$BIOCLAIM_CACHE`, else `~/.cache/bioclaim/`).
After a warm-up bioclaim is fast, works offline, and is immune to rate limits — each
identifier is fetched at most once. Set `BIOCLAIM_CACHE=off` to disable.

## For developers / research

```bash
git clone https://github.com/SxR24/bioclaim.git
cd bioclaim && pip install -e .
python -m pytest

# measure a real model's hallucination rate (needs a free Groq key)
python scripts/real_model_eval.py --provider groq \
    --model llama-3.3-70b-versatile --questions data/bio_questions_hard.txt --out run.csv
python scripts/compare.py run.csv              # multi-model comparison table
```

```
bioclaim/     core package: patterns, live sources (+ cache), validator, claims, api
scripts/      research tooling: real_model_eval, benchmark, compare, rescore, demos
examples/     guard_llm.py + sample_paragraphs.txt
tests/        offline unit tests
```

## Roadmap

- **v0.1–0.4** Identifier validation: format + live existence check, disk-cached *(done)*
- **v0.5** Claim verification — label consistency (real id, wrong description) *(done)*
- **v0.6** Entity-correspondence — real id, wrong gene *(done)*
- **v0.7** Deployable release — persistent cache, one-call API, `Firewall`, CLI, PyPI *(done)*
- **v0.8** Gene–function association — does the gene actually carry the GO term? *(done)*
- **v0.9** Context-free detection (wrong-gene / association without an explicit hint) — *next*
- **later** Calibrated confidence · gene–disease & pathway claims · preprint

## Why this design wins

Generality (all identifier types, one layer) · Deployability (pure standard library,
3-line integration) · Speed (deterministic lookups, not agent loops) · Trust (never a
false accusation).

## License

MIT — see [LICENSE](LICENSE).
