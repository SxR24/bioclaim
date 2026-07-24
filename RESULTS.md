# Results: how often does an LLM invent biomedical identifiers?

**Headline:** On 40 specialist biology questions, **Llama-3.3-70B fabricated a
biomedical identifier in 15% of answers** (6/40). Overall, **~4.7% of all
identifiers it produced (7/148) did not exist** in their source database.

## Setup

| | |
| --- | --- |
| Model | `llama-3.3-70b-versatile` (via Groq) |
| Questions | 40 specialist prompts on genes, proteins, rare diseases (`data/bio_questions_hard.txt`) |
| Verification | Every identifier checked live against UniProtKB, Ensembl, GO, HPO, MONDO, ChEBI |
| "Fabricated" | Identifier returns *not found* from its authoritative source database |
| Network failures | 0 (every identifier was actually verified) |

The questions deliberately target the **long tail** — obscure-but-real genes
(TMEM63C, ZC3H14, ARMC9), rare diseases (alkaptonuria, Menkes), and quota-style
prompts ("list N GO terms with their IDs"). This is where LLMs are least
reliable and where researchers actually get burned.

## Findings

| Metric | Value |
| --- | --- |
| Answers with ≥1 fabricated identifier | **6 / 40 (15%)** |
| Identifiers examined | 148 |
| Fabricated (not in source database) | **7 (4.7%)** |
| Unverifiable (network) | 0 |

### The quota trap

Nearly every fabrication appeared in response to a prompt asking for a **specific
number** of identifiers ("list 6 GO terms with their IDs"). Rather than return
fewer, the model padded the list with plausible-looking fakes. Direct single-fact
questions ("what is the UniProt accession for X?") were almost always correct —
the model fabricates when pushed to fill a quota it can't satisfy.

### Evidence

| Fabricated ID | Type | Prompt |
| --- | --- | --- |
| ENSG00000169351 | Ensembl gene | list 8 GO biological process terms (FUS) |
| ENSG00000163601 | Ensembl gene | list 7 GO cellular component terms |
| ENSG00000124457 | Ensembl gene | list 5 GO terms (GRIN2B) |
| HP:0007226 | HPO term | progressive myoclonic epilepsy |
| GO:0039787 | GO term | list 6 GO molecular function terms (KIF1A) |
| ENSG00000116217 | Ensembl gene | list 6 GO molecular function terms (KIF1A) |
| ENSG00000188307 | Ensembl gene | give 7 GO terms (SCN2A) |

Note the model repeatedly emitted **fake Ensembl gene IDs while being asked for
GO terms** — conflating identifier types and inventing accessions that resolve
nowhere. On KIF1A it produced two fabrications in a single answer.

## Honest caveats

- **Existence, not correctness.** `bioclaim` checks whether an identifier exists,
  not whether it is the *right* one for the entity asked. The true error rate is
  therefore a **floor**, not a ceiling.
- **Single model, N=40.** This is an illustrative study, not a comprehensive
  benchmark. Results will vary by model and prompt set.
- Framing to use publicly: *"invented identifiers that do not exist in the source
  database,"* not *"got it wrong."*

## Reproduce

```bash
pip install openai
set GROQ_API_KEY=your_key_here        # free key at console.groq.com
python scripts/real_model_eval.py --provider groq \
    --model llama-3.3-70b-versatile \
    --questions data/bio_questions_hard.txt
```

Evidence is written to `real_model_report.csv` (per-identifier verdicts).
