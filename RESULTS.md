# Results: how often does an LLM get biomedical identifiers wrong?

**Headline:** on 40 specialist biology questions, **Llama-3.3-70B produced a wrong
biomedical identifier in ~48% of answers** (19/40). Of 150 identifiers it
generated, **30 (~20%) were wrong** in one of four ways — and the largest error
class is real, valid identifiers pointing at the **wrong gene**, which is
invisible to existence-checking.

## Setup

| | |
| --- | --- |
| Model | `llama-3.3-70b-versatile` (via Groq), temperature 0.2 |
| Questions | 40 specialist prompts on genes, proteins, rare diseases (`data/bio_questions_hard.txt`) |
| Verification | Every identifier checked live against UniProtKB, Ensembl, GO, HPO, MONDO, ChEBI |

## Findings

| Category | Meaning | Count |
| --- | --- | --- |
| **Fabricated** | Identifier does not exist in any database | 7 |
| **Mislabeled** | Real identifier, but the model's description is wrong | 5 |
| **Wrong-entity** | Real identifier, but for a **different gene/protein** | 17 |
| **Obsolete** | Real identifier, but deprecated/retired | 1 |
| **Total wrong** | | **30 / 150 (~20%)** |
| **Answers affected** | | **19 / 40 (~48%)** |
| Unverifiable (network) | | 3 |

Existence-checking alone catches only the 7 fabricated IDs. The other 23 problems
— real identifiers that are mislabeled, misassigned, or deprecated — pass every
existence check and require verifying the *claim*, not just the *ID*.

### The most dangerous class: real IDs, wrong gene

The model confidently returns a **real, valid** accession — for the wrong protein.
Independently confirmed against UniProt/Ensembl:

| Asked about | Model gave | That identifier actually is |
| --- | --- | --- |
| Neurexin-1 (NRXN1) | `Q9ULB2` | **Cadherin-8** (real NRXN1 is `Q9ULB1` — off by one digit) |
| ARID1B | `ENSG00000117713` | **ARID1A** (its paralog) |
| MECP2 | `Q00548` | **Exoglucanase 1** (a fungal enzyme) |
| TARDBP | `ENSG00000120913` | **PDLIM2** |
| KIF1A | `O00214` | **Galectin-8** |

These are the errors most likely to slip past a human reader: the ID is real,
well-formed, and cited with total confidence.

### Mislabeled (real ID, wrong description)

e.g. `GO:0046975` described as "ATP-dependent chromatin remodeling" — it is
actually "histone H3K36 methyltransferase activity" (verified via EBI OLS).

### Fabricated & obsolete

7 invented identifiers (mostly non-existent Ensembl IDs) and 1 deprecated GO term.

## Independent verification

A random sample of the wrong-entity and mislabeled flags was checked **directly
against the source databases**, separate from the tool. All confirmed correct:
`ENSG00000117713` = ARID1A, `Q9ULB2` = Cadherin-8, `Q9ULB1` = Neurexin-1,
`GO:0046975` = histone H3K36 methyltransferase activity, `GO:0043025` = neuronal
cell body. bioclaim made **zero false accusations** in the audited sample.

## Honest caveats

- **Single run, N=40.** LLM output is nondeterministic; the answer-level rate
  varies (roughly 30–48% across runs as detection has deepened). Illustrative
  study, not a comprehensive benchmark.
- **Zero false accusations by design.** Deprecated terms, placeholder labels, and
  other identifiers near a symbol are handled explicitly.
- Framing to use publicly: *"fabricated, mislabeled, misassigned, or deprecated
  identifiers,"* each defined and verifiable above.

## Reproduce

```bash
pip install openai
set GROQ_API_KEY=your_key_here        # free key at console.groq.com
python scripts/real_model_eval.py --provider groq \
    --model llama-3.3-70b-versatile \
    --questions data/bio_questions_hard.txt
```

Per-identifier evidence (claimed vs. real) is written to `real_model_report.csv`.
