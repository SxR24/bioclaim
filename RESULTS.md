# Results: how often do LLMs get biomedical identifiers wrong?

**Headline:** across **six** models — including OpenAI's GPT-4o and GPT-5 — **25–68% of
specialist biology answers contained a wrong biomedical identifier.** The dominant
error is a *real, valid* identifier attached to the *wrong* gene or disease, which
passes every existence check and is only caught by verifying the claim, not just the
identifier. Reliability is **not** monotonic in model capability: the newest reasoning
model (GPT-5, 40%) was *worse* than the older GPT-4o (25%).

## Model comparison

40 specialist questions targeting the long tail (obscure genes, rare diseases, quota
prompts; `data/bio_questions_hard.txt`), each identifier verified live against
UniProtKB, Ensembl, GO, HPO, MONDO, and ChEBI. Entity-correspondence is anchored to
the gene each question asks about. Every flag below was independently audited against
the source databases; **zero false positives.**

| Model | Answers wrong | Fabricated | Mislabeled | Wrong-entity | Obsolete |
| --- | --- | --- | --- | --- | --- |
| Llama-3.1-8B | **68%** (27/40) | 7 | 28 | 30 | 7 |
| gpt-oss-120B | **60%** (24/40) | 1 | 0 | 33 | 0 |
| GPT-4o-mini | **52%** (21/40) | 6 | 0 | 16 | 0 |
| Llama-3.3-70B | **48%** (19/40) | 7 | 5 | 16 | 1 |
| **GPT-5** | **40%** (16/40) | 0 | 5 | 10 | 1 |
| **GPT-4o** | **25%** (10/40) | 2 | 0 | 8 | 0 |

*(Llama and gpt-oss via Groq; GPT models via the OpenAI API. A preliminary partial
run of DeepSeek-V4-Pro, ~1.6T parameters, produced near-zero errors on its answered
subset.)*

### Key findings

- **Even the best model is wrong 1 in 4 times.** GPT-4o, the cleanest, still produced
  a wrong identifier in 25% of specialist answers.
- **Newer/larger is not reliably better.** GPT-5 (40%) — OpenAI's newest reasoning
  model — was *worse* than GPT-4o (25%). Reasoning ability does not translate into
  factual recall of obscure identifiers.
- **The dangerous error is confident misassignment.** GPT-5 fabricated *zero*
  non-existent identifiers — every one of its errors was a **real** identifier used
  **wrongly**, which is harder to detect than obvious fabrication.
- **Each model fails differently.** gpt-oss-120B almost exclusively misassigns real
  accessions to the wrong gene; Llama-3.1-8B errs across every category; the GPT models
  err less but still substantially.

### Examples (all independently verified)

- **Wrong disease.** Asked for the MONDO ID for **alkaptonuria**, GPT-5 returned
  `MONDO:0007915` — which is *systemic lupus erythematosus*. Asked for **Menkes disease**
  it returned the ID for *Riley-Day syndrome*, and fabricated supporting cross-references
  (`OMIM:309400`, `ORPHA:558`) to appear authoritative.
- **Wrong gene.** Asked for **GRIN2B**, gpt-oss returned the accession for GRIN2A (its
  paralog); asked for **Neurexin-1**, it returned `Q9ULB2` (Cadherin-8) where the correct
  accession is the off-by-one `Q9ULB1`. Multiple models returned `ENSG00000117713`
  (ARID1A) when asked for its paralog ARID1B.
- **Mislabeled.** `GO:0005506` described as "copper ion binding" — it is "iron ion binding".
- **Deprecated.** Several genuinely obsolete GO terms (e.g. "cell cycle arrest",
  "extracellular space") were cited as valid.

## Error categories

- **Fabricated** — identifier does not exist in any database (incl. deleted accessions).
- **Mislabeled** — real identifier, wrong description.
- **Wrong-entity** — real, valid identifier, but for a different gene/protein/disease.
- **Obsolete** — real identifier, but deprecated/retired.

## Independent verification

Every flag in this study was checked **directly against the source databases**, separate
from the tool, and confirmed correct — **zero false accusations across all six models.**
An earlier version of the entity check produced false positives on table-formatted
answers; it was fixed to anchor on the question's known gene, and all numbers were
re-scored with the corrected logic. The audit repeatedly caught the tool's own edge
cases before any figure was published — including a case where the tool correctly
flagged a deprecated term that a knowledgeable reviewer assumed was valid.

## Gene–function validation (v0.8)

On 104 curated gene–function cases run live against QuickGO, bioclaim rejected **66/66
(100%)** implausible associations (no human protein is annotated with photosynthesis,
pollen development, etc.) and accepted **37/38 (97%)** genuine ones. The single exception
reflects GO annotation incompleteness and is reported honestly as "not among the gene's
annotations", never "false".

## Controlled benchmark

On 500 answers with 394 injected fabrications, bioclaim achieved **100% precision**,
**95.7% recall** (377/394), **F1 = 0.978**, and **zero false accusations**. Every
uncaught fabrication was a network-throttled lookup that safely returned `UNVERIFIED`.

## Honest caveats

- **Single run per model, N=40.** LLM output is nondeterministic; rates vary run to run.
  This is an illustrative study; a larger, stratified, multi-run benchmark is planned.
- **Specialist / long-tail questions.** These questions deliberately target obscure
  entities where models are weakest; models are far more accurate on common genes.
  The figures apply to *specialist* questions, not all biology.
- **Zero false accusations by design.** Anything that cannot be verified is left unflagged.

## Reproduce

```bash
pip install bioclaim openai
set OPENAI_API_KEY=...        # or GROQ_API_KEY for the free models
python scripts/real_model_eval.py --provider openai --model gpt-4o \
    --questions data/bio_questions_hard.txt --out run.csv
python scripts/compare.py *.csv      # side-by-side comparison table
```

Per-identifier evidence (claimed vs. real) is written to each report CSV.
