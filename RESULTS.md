# Results: how often do LLMs get biomedical identifiers wrong?

**Headline:** across three models, **48–68% of specialist biology answers contained
a wrong biomedical identifier.** The dominant error is a *real, valid* identifier
attached to the *wrong gene* — which passes every existence check and is only
caught by verifying the claim, not just the ID.

## Model comparison

40 specialist questions (genes, proteins, rare diseases; `data/bio_questions_hard.txt`),
each identifier verified live against UniProtKB, Ensembl, GO, HPO, MONDO, ChEBI.
Entity-correspondence is anchored to the gene each question asks about (v0.6.1).

| Model | Answers wrong | Fabricated | Mislabeled | Wrong-entity | Obsolete |
| --- | --- | --- | --- | --- | --- |
| Llama-3.1-8B | **68%** (27/40) | 7 | 28 | 30 | 7 |
| gpt-oss-120B | **60%** (24/40) | 1 | 0 | 33 | 0 |
| Llama-3.3-70B | **48%** (19/40) | 7 | 5 | 16 | 1 |

*(Llama and gpt-oss served via Groq; temperature 0.2.)*

### Each model fails differently

- **gpt-oss-120B** almost never fabricates or mislabels (1 and 0) — it returns
  real, correctly-described accessions pinned to the **wrong gene** 33 times. It
  "knows" valid identifiers and misassigns them.
- **Llama-3.1-8B** errs across *every* category — the sloppiest, and the worst
  overall at 68%.
- **Llama-3.3-70B** is the cleanest, yet still wrong in nearly half its answers.

## Error categories

- **Fabricated** — identifier does not exist in any database.
- **Mislabeled** — real identifier, wrong description (e.g. `GO:0005506` called
  "copper ion binding"; it is "iron ion binding").
- **Wrong-entity** — real, valid identifier, but for a different gene/protein.
  Asked for **GRIN2B**, gpt-oss returned `Q12879` (glutamate receptor NMDA **2A**);
  asked for **NRXN1**, it returned IL6's gene. Invisible to existence checks.
- **Obsolete** — real identifier, but deprecated/retired.

## Independent verification

Flags were checked **directly against the source databases**, separate from the
tool. Confirmed correct in every audited case, e.g.: `ENSG00000117713` = ARID1A
(not the requested ARID1B); `Q9ULB2` = Cadherin-8 (requested Neurexin-1, which is
`Q9ULB1`); `GO:0005506` = iron ion binding; `GO:0046975` = histone H3K36
methyltransferase activity. All 33 of gpt-oss's wrong-entity flags were verified
against the question's gene — zero false accusations.

A note on rigor: an earlier version of the entity check guessed the gene from
nearby text and produced false positives on table-formatted answers. It was fixed
to anchor on the question's known gene (v0.6.1), and every number here was
re-scored with the corrected logic. The audit caught the tool's own weakness
before any figure was published — that is the point of the tool.

## Honest caveats

- **Single run per model, N=40.** LLM output is nondeterministic; rates vary run
  to run. This is an illustrative study, not a comprehensive benchmark.
- **Zero false accusations by design.** Deprecated terms, placeholder labels, and
  identifiers without a known target entity are handled explicitly.
- Framing to use publicly: *"fabricated, mislabeled, misassigned, or deprecated
  identifiers,"* each defined and verifiable above.

## Reproduce

```bash
pip install openai
set GROQ_API_KEY=your_key_here        # free key at console.groq.com
python scripts/real_model_eval.py --provider groq \
    --model llama-3.3-70b-versatile \
    --questions data/bio_questions_hard.txt --out run.csv
python scripts/compare.py run.csv     # or compare several models' reports
```

Per-identifier evidence (claimed vs. real) is written to each report CSV.
