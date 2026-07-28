# How Often Do Language Models Invent Biology? Measuring and Catching Fabricated and Incorrect Biomedical Identifiers in LLM Output

**Sohil Ananth Ramesh Kumar**
*University of Leicester* · sohil.r@icloud.com
*(advisors / co-authors to be added)*

**Preprint — draft v1.** Code and data: https://github.com/SxR24/bioclaim · Package: `pip install bioclaim`

---

## Abstract

Large language models (LLMs) are increasingly used to summarise, annotate, and reason over biomedical information, yet they frequently cite database identifiers — UniProt accessions, Ensembl gene IDs, Gene Ontology (GO) terms, and others — that appear authoritative but are incorrect. Because these identifiers look well-formed and are embedded in fluent prose, such errors are difficult for a human reader to detect and can silently propagate into downstream analysis. We introduce **bioclaim**, an open-source, dependency-free tool that verifies every biomedical identifier in a piece of text against the authoritative source databases and classifies errors into five categories: fabricated, mislabeled, misassigned (wrong gene), deprecated, and — for gene–function claims — unsupported by annotation. bioclaim is *deterministic* (a database lookup, not a second model) and is designed never to falsely accuse: any claim it cannot verify is left unflagged. Evaluating three language models (Llama-3.1-8B, OpenAI gpt-oss-120B, and Llama-3.3-70B) on 40 specialist questions, we find that **48–68% of answers contained at least one incorrect biomedical identifier**, with the dominant error class being real, valid accessions assigned to the *wrong* gene — a failure invisible to existence checks alone. On a controlled benchmark of 500 answers with 394 injected fabrications, bioclaim achieves 100% precision and 95.7% recall (F1 = 0.978) with zero false accusations. A live evaluation of gene–function association on 104 curated cases correctly rejected 66/66 implausible associations and accepted 37/38 genuine ones. We argue that lightweight, deterministic identifier verification is a practical and necessary safeguard for any pipeline that exposes LLM-generated biology to human readers.

---

## 1. Introduction

Language models are being adopted across the life sciences — for literature summarisation, gene-set interpretation, hypothesis generation, and as the reasoning layer of biomedical agents. A recurring and under-measured failure mode is the confident citation of **incorrect database identifiers**. An answer may read fluently and cite `UniProtKB: P04637`, `Ensembl: ENSG00000141510`, and `GO:0006915` — but any of these may be fabricated, correct-but-mislabeled, or assigned to the wrong gene. Unlike a grammatical or factual slip in free text, an identifier error is both *high-stakes* (it points, or fails to point, to a specific database record) and *low-salience* (it is a short alphanumeric string that a reader is unlikely to check).

Existing work on LLM reliability in biomedicine has largely taken one of two forms: (i) **benchmarks** that *measure* how often models answer gene- or medical-knowledge questions correctly [GeneTuring; SciHorizon-GENE; MedHallu; Med-HALT], and (ii) **task-specific research agents** that self-verify a particular class of output, such as gene-set analysis [GeneAgent] or variant summarisation [Precision Grounding]. What is missing is a **general, deployable, deterministic layer** that can be applied to *any* LLM output to catch the specific, checkable class of error that biomedical identifiers represent.

We present **bioclaim**, an open-source tool that fills this gap. It extracts every identifier from a piece of text and verifies it live against the authoritative source database, reporting a per-identifier verdict. It requires no model of its own, has no dependencies beyond the Python standard library, installs in one command, and is designed around a single guarantee: **it never falsely accuses.**

Our contributions are:

1. **A tool** (`bioclaim`) implementing five layers of identifier and claim verification against UniProtKB, Ensembl, the EBI Ontology Lookup Service (OLS), and QuickGO, with disk caching for speed and offline operation.
2. **A measurement**: across three language models on 40 specialist biology questions, 48–68% of answers contained at least one incorrect identifier, dominated by real-but-misassigned accessions.
3. **A controlled benchmark** demonstrating 100% precision and 95.7% recall (F1 = 0.978) on 500 answers with 394 injected fabrications.
4. **A live validation** of gene–function association checking: 66/66 implausible associations rejected, 37/38 genuine ones accepted.

---

## 2. Related work

**Benchmarks of LLM biomedical knowledge.** GeneTuring and SciHorizon-GENE evaluate models on large batteries of gene-centric questions and report substantial hallucination and inconsistency. In the clinical domain, MedHallu and Med-HALT quantify medical hallucination. These works *measure* error but do not provide a runtime tool to *catch* it in arbitrary output.

**Grounding and self-verification agents.** GeneAgent (Nature Methods, 2025) is a self-verifying language agent that checks gene-set claims against domain databases to reduce hallucination; Precision Grounding augments LLMs with evidence databases for trustworthy variant summarisation. These are powerful but are bespoke research agents scoped to a single task type, not a general, installable verification layer.

**Ontology grounding.** A broad literature grounds LLM reasoning in knowledge graphs and ontologies to improve factuality. bioclaim is a pragmatic, deterministic instantiation of this idea, specialised to biomedical identifiers and deployable as a library or CLI.

bioclaim is distinguished by being **general** (any identifier type, any text), **deployable** (`pip install`, three-line integration), **deterministic** (a lookup, not a second model that can itself hallucinate), and **precision-first** (it never falsely accuses).

---

## 3. Methods

### 3.1 The bioclaim verification pipeline

Given input text, bioclaim extracts every recognised identifier (Gene Ontology `GO`, Human Phenotype Ontology `HP`, `MONDO`, `DOID`, `ChEBI`, Ensembl gene `ENSG`, and UniProtKB accessions — both official accession syntaxes) and applies up to five verification layers:

1. **Format.** Offline, deterministic rejection of malformed identifiers.
2. **Existence.** A live lookup against the source database (OLS for ontologies; UniProt and Ensembl REST for genes/proteins). A well-formed but absent identifier is flagged *fabricated*. Deleted/inactive UniProt accessions (which return HTTP 200 with an "Inactive" entry) are also treated as non-resolving.
3. **Label consistency.** When a model attaches a description to an identifier (e.g. `GO:0006281 (photosynthesis)`), bioclaim compares the claimed description to the term's real label and synonyms; a genuine mismatch is flagged. Matching is synonym-aware to avoid penalising legitimate paraphrase.
4. **Entity correspondence.** When the intended gene is known, a real UniProt/Ensembl accession assigned to the *wrong* gene (e.g. `P04637` for BRCA1 — that accession is TP53) is flagged. To preserve precision, this is only applied when the target gene is unambiguous.
5. **Gene–function association (opt-in).** Given a gene product and a GO term, bioclaim queries QuickGO — using GO propagation over `is_a`/`part_of`/`occurs_in` — to determine whether the gene is actually annotated with that term (or a descendant). A real, correctly-named GO term assigned to a gene not annotated with it is reported as *not among the gene's annotations*. Because GO annotation is incomplete, this verdict is worded as an annotation fact, never as "false".

**Never falsely accuse.** Every layer degrades safely: any lookup that cannot be completed (network failure, rate limit, ambiguous context) yields `UNVERIFIED` and is never counted as a problem. Rate-limited requests are retried with exponential backoff. Every lookup is cached to disk, so after a warm-up the tool is fast, offline-capable, and immune to rate limits.

### 3.2 Evaluation of live models

We assembled 40 specialist questions targeting the "long tail" of biology — obscure but real genes, rare diseases, and quota-style prompts ("list N GO terms with IDs") — where models are least reliable (`data/bio_questions_hard.txt`). We queried three models at temperature 0.2: **Llama-3.1-8B**, **OpenAI gpt-oss-120B**, and **Llama-3.3-70B** (served via Groq), and verified every identifier each produced. Entity-correspondence was anchored to the gene named in each question. A subset of every flag was independently confirmed by querying the source databases directly, separately from the tool.

### 3.3 Controlled benchmark

To measure precision and recall directly, we generated 500 LLM-style answers by sampling real identifiers (from live GO, HPO, and UniProt) and injecting 394 guaranteed-nonexistent identifiers, recording ground truth per answer. bioclaim was run over the set and scored against the labels.

### 3.4 Gene–function validation

We curated 104 gene–function test cases across 22 well-characterised human proteins: 38 genuine, well-annotated associations (subcellular localisation and canonical molecular functions) that should pass, and 66 implausible associations pairing each human protein with plant/bacterial/photosynthetic GO terms (e.g. photosynthesis, chlorophyll biosynthesis, pollen development) that should be flagged. Each was evaluated live against QuickGO.

---

## 4. Results

### 4.1 Leading models are wrong in roughly half of specialist answers

| Model | Answers with ≥1 wrong identifier |
| --- | --- |
| Llama-3.1-8B | **68%** (27/40) |
| OpenAI gpt-oss-120B | **60%** (24/40) |
| Llama-3.3-70B | **48%** (19/40) |

Each model exhibited a distinct failure *fingerprint*. gpt-oss-120B almost never fabricated or mislabeled identifiers but very frequently *misassigned* real accessions to the wrong gene; Llama-3.1-8B erred across every category; Llama-3.3-70B was cleanest but still wrong in nearly half its answers. The dominant error class overall was a **real, valid identifier assigned to the wrong gene** — for example, when asked for GRIN2B the model returned the accession for GRIN2A (its paralog), and when asked for Neurexin-1 it returned `Q9ULB2` (Cadherin-8) where the correct accession is the off-by-one `Q9ULB1`. Such errors pass every existence check and are only caught by verifying the claim, not the identifier.

A preliminary run of a much larger frontier model (DeepSeek-V4-Pro, ~1.6T parameters) produced markedly fewer errors on the answered subset, suggesting that identifier reliability improves substantially with model scale; we report this as an observation pending a complete run.

### 4.2 Benchmark: high recall at 100% precision

On 500 answers with 394 injected fabrications:

| Metric | Value |
| --- | --- |
| Precision | **100.0%** |
| Recall | **95.7%** (377/394) |
| F1 | **0.978** |
| False accusations | **0** |

Every uncaught fabrication corresponded to a network-throttled lookup that safely returned `UNVERIFIED`; not a single fabrication was checked and missed. This confirms the design goal: bioclaim trades recall (under network failure) for a hard precision guarantee.

### 4.3 Gene–function association: 66/66 implausible claims rejected

On 104 live gene–function cases, bioclaim rejected **66/66 (100%)** implausible associations (no human protein is annotated with photosynthesis, pollen development, or nitrogen fixation) and accepted **37/38 (97%)** genuine associations. The single exception (MTOR / "ATP binding", GO:0005524) reflects GO annotation *incompleteness*: MTOR is annotated to specific kinase-activity terms rather than to "ATP binding" directly, and the tool honestly reported "not among the gene's annotations" rather than asserting the claim was false. This case illustrates the value of the conservative, annotation-factual wording.

### 4.4 Robustness on expert-written text

On dense, expert-authored passages seeded with errors, bioclaim correctly flagged fabricated and deleted UniProt accessions across both official accession formats, fabricated Ensembl and GO identifiers, and several *genuinely deprecated* GO terms (e.g. GO:0007050 "cell cycle arrest"; GO:0005615 "extracellular space", replaced by "extracellular region") that read as valid to a domain expert. Notably, the same identifier (`GO:0005634`) was flagged in one passage where it was described as "nucleoplasm" and accepted in another where it was correctly described as "nucleus" — demonstrating that the tool verifies the *claim* rather than pattern-matching the identifier.

---

## 5. Discussion

Our central finding — that leading language models produce an incorrect biomedical identifier in roughly half of specialist answers — has a practical corollary: **any workflow that surfaces LLM-generated biology to a human should verify its identifiers.** The verification is cheap, deterministic, and (as our benchmark shows) can be made precision-safe.

The most consequential error class is not the obviously-fabricated identifier but the **real, valid identifier used incorrectly** — assigned to the wrong gene, or attached to a function the gene does not have. These errors are the most dangerous precisely because they survive naive checks and read as authoritative. Catching them requires moving from identifier verification to *claim* verification, which bioclaim does for gene identity and gene–function association.

### 5.1 Limitations

- **Context dependence.** Wrong-gene and gene–function checks require knowing the intended gene; in fully free-form text without such context, bioclaim conservatively declines to accuse. Robust context-free extraction is future work.
- **Annotation incompleteness.** The gene–function layer reflects the current state of GO annotation; a genuine function that is not yet annotated is reported as "not among the gene's annotations", not as false. This is by design.
- **Scale of evaluation.** The model comparison uses a single run of 40 questions per model; LLM output is nondeterministic and rates vary across runs. A larger, multi-run, multi-model benchmark is planned.

### 5.2 Availability

bioclaim is MIT-licensed and available at https://github.com/SxR24/bioclaim and on PyPI (`pip install bioclaim`). All evaluation scripts, question sets, and the reproduction of every figure are included.

---

## 6. Conclusion

Language models cite biomedical identifiers that are frequently wrong and hard to catch by eye. We show the problem is substantial (48–68% of specialist answers) and that a lightweight, deterministic, precision-first tool can catch fabricated, mislabeled, misassigned, deprecated, and unsupported-function identifiers with a strong precision guarantee and no false accusations. We release bioclaim as a practical safeguard for LLM-assisted biology.

---

## References

*(to be formatted for the target venue; key sources)*

1. GeneAgent: a self-verification language agent for gene-set analysis using domain databases. *Nature Methods*, 2025.
2. Precision Grounding: augmenting LLMs with evidence-based databases for genetic variant summarisation. *PMC*.
3. Benchmarking large language models for genomic knowledge with GeneTuring. *Briefings in Bioinformatics*, 2025.
4. SciHorizon-GENE: benchmarking LLMs for gene knowledge and functional understanding. *arXiv*.
5. MedHallu: a benchmark for detecting medical hallucinations. *EMNLP*, 2025.
6. Med-HALT: medical domain hallucination test for large language models. *arXiv*.
7. The Gene Ontology knowledgebase in 2026. *Nucleic Acids Research*.
8. UniProt: the Universal Protein Knowledgebase. *Nucleic Acids Research*.
9. Ensembl. *Nucleic Acids Research*.
10. QuickGO: a web-based tool for Gene Ontology searching. EMBL-EBI.
