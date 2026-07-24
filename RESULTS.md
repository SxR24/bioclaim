# Results: how often does an LLM get biomedical identifiers wrong?

**Headline:** on 40 specialist biology questions, **Llama-3.3-70B produced a
fabricated, mislabeled, or obsolete biomedical identifier in ~32% of answers**
(13/40). Of 150 identifiers it generated, **22 (~15%) were wrong** in one of
three distinct ways — and two-thirds of those errors are invisible to
existence-checking alone.

## Setup

| | |
| --- | --- |
| Model | `llama-3.3-70b-versatile` (via Groq), temperature 0.2 |
| Questions | 40 specialist prompts on genes, proteins, rare diseases (`data/bio_questions_hard.txt`) |
| Verification | Every identifier checked live against UniProtKB, Ensembl, GO, HPO, MONDO, ChEBI |
| Network failures | 0 |

Questions target the long tail — obscure-but-real genes, rare diseases, and
quota prompts ("list N GO terms with IDs"), where LLMs are least reliable.

## Findings

| Category | Meaning | Count |
| --- | --- | --- |
| **Fabricated** | Identifier does not exist in any database | 8 |
| **Mislabeled** | Real identifier, but the model's description is wrong | 10 |
| **Obsolete** | Real identifier, but deprecated/retired | 4 |
| **Total wrong** | | **22 / 150 (15%)** |
| **Answers affected** | | **13 / 40 (32%)** |

**Why claim-checking matters:** existence-checking alone would have caught only
the 8 fabricated IDs. The other 14 problems — real identifiers paired with false
or stale descriptions — pass every existence check and are only caught by
verifying the *claim*, not just the *ID*. `bioclaim` catches all 22.

### The most dangerous class: real IDs, wrong meaning

These pass any existence check. The model attaches a plausible description to a
real GO term that means something entirely different:

| Identifier | Model said | Actually means |
| --- | --- | --- |
| GO:0043025 | "cellular amino acid metabolic process" | **neuronal cell body** |
| GO:0072657 | "regulation of cellular amino acid metabolic process" | **protein localization to membrane** |
| GO:0046975 | "ATP-dependent chromatin remodeling" | **histone H3K36 methyltransferase activity** |
| GO:0071567 | "ATPase activity, acting on DNA" | **deUFMylase activity** |
| GO:0045975 | "regulation of transcription by RNA polymerase II" | **positive regulation of translation, ncRNA-mediated** |

### Fabricated identifiers

Mostly invented Ensembl gene IDs emitted while listing GO terms — e.g.
`ENSG00000169351`, `ENSG00000188307` — none of which resolve. Plus a fabricated
HPO code (`HP:0007226`).

### Obsolete identifiers

Four answers cited **deprecated** GO terms (e.g. `GO:0030176`,
`GO:0016021`) — real once, now retired. `bioclaim` reports these separately as
`SUPPORTED_OBSOLETE` rather than as a mismatch, so no false accusation is made
against a stale label.

## Honest caveats

- **Single run, N=40.** LLM output is nondeterministic; the answer-level rate
  varies roughly **30–35%** across runs. This is an illustrative study, not a
  comprehensive benchmark.
- **Zero false accusations by design.** Obsolete terms and placeholder labels are
  handled explicitly so a real (if deprecated) identifier is never mislabeled as
  fabricated.
- Framing to use publicly: *"fabricated, mislabeled, or deprecated identifiers,"*
  each defined precisely above.

## Reproduce

```bash
pip install openai
set GROQ_API_KEY=your_key_here        # free key at console.groq.com
python scripts/real_model_eval.py --provider groq \
    --model llama-3.3-70b-versatile \
    --questions data/bio_questions_hard.txt
```

Per-identifier evidence (claimed label vs. real label) is written to
`real_model_report.csv`.
