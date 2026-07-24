# Changelog

## 0.7.5
- Defensive: when the ontology service returns several entries for one id, prefer
  the active, defining term so an active term can't be mislabeled obsolete by a
  stale duplicate. (Genuinely deprecated terms are still flagged - e.g. GO:0005615
  "extracellular space" is really obsolete, replaced by GO:0005576 "extracellular
  region", and remains flagged. Verified against EBI OLS.)

## 0.7.4
- Detect **deleted / demerged UniProt accessions**. These return HTTP 200 with
  `entryType: "Inactive"`, so they previously passed as "exists"; now treated as
  not-found, since they no longer resolve to a protein. Surfaced by seeded
  accessions (`J8XYZ9`, `U7FD21`) that turned out to be real-but-deleted.

## 0.7.3
- **Full UniProtKB accession coverage.** The extractor previously matched only the
  O/P/Q accession form and silently ignored the second official form (starting
  A-N/R-Z, e.g. `J8XYZ9`, `U7FD21`), so fabricated accessions in that range were
  never checked. Now uses the complete official accession syntax. Surfaced by an
  expert paragraph seeded with fake accessions.

## 0.7.2
- Cleaner obsolete-term output: no longer shows the placeholder short-form (e.g.
  "GO_0007050") as the "real" name; reads `obsolete / deprecated (labeled "...")`.
- Surfaced by an expert paragraph where GO:0007050 ("cell cycle arrest", now
  deprecated in the Gene Ontology) was correctly flagged as obsolete.

## 0.7.1
- Cleaner label extraction on dense prose: a "term (CURIE)" mention now reports the
  trailing term (e.g. "nucleoplasm") instead of over-capturing the whole clause.
  Surfaced by a real expert paragraph where the tool correctly flagged GO:0005634
  ("nucleus") used for "nucleoplasm", but displayed the claim messily.

## 0.7.0 - "Deployable & reliable"
- **Persistent on-disk cache** for every database lookup: after a warm-up, bioclaim
  runs fast, offline-capable, and immune to rate limits (each id fetched at most
  once, ever). Only definitive results are cached; transient failures never poison it.
- **One-call API:** `check(text, entity_hint=...) -> Result` with `.ok` / `.problems`.
- **`Firewall`** wrapper to guard any model-calling function (optionally raising).
- **`bioclaim` command-line tool** (`pip install` provides it; also `python -m bioclaim`).
- Non-zero exit code when identifiers are flagged (CI / guardrail friendly).

## 0.6.1
- **Precision fix for entity-correspondence.** The v0.6 check guessed the gene from
  text near the identifier, which produced false positives on densely-formatted
  (e.g. markdown-table) answers. It is now anchored to a known `entity_hint` (the
  gene the question is about); without a hint, correspondence is never accused.
- `check_claims(text, entity_hint=...)`, `extract_target_entity(question)`.
- New `scripts/rescore.py`: recompute an existing eval report with current logic
  using only database lookups - no model re-runs.

## 0.6.0
- Entity-correspondence checking for UniProt/Ensembl: a real, valid accession
  attached to the wrong gene (e.g. "the UniProt for TP53 is P38398", which is
  actually BRCA1) is now flagged `SUPPORTED_ENTITY_MISMATCH`. Closes the biggest
  accuracy gap — real-but-wrong identifiers previously passed existence checks.
- Gene-symbol detection is stoplist-filtered and ignores other identifiers, to
  preserve the never-falsely-accuse guarantee.
- New `scripts/demo_entity.py`; eval harness reports a "wrong-entity" category.

## 0.5.0
- Claim verification: label-consistency checking. A real identifier with a wrong
  description (e.g. `GO:0006281 (photosynthesis)`, actually "DNA repair") is now
  flagged `SUPPORTED_LABEL_MISMATCH` — existence checking alone would pass it.
- Synonym-aware matching (pulls term synonyms from the source) so paraphrases
  like "apoptosis" vs "apoptotic process" are not falsely flagged.
- New: `bioclaim.check_claims` / `report_claims`, `scripts/demo_claims.py`.

## 0.3.0
- Added polite throttling and retry-with-backoff to all database checkers.
- Rate-limit responses (429/503) are now retried instead of counted as "unknown".
- Benchmark recall on the 500-answer set rose from 73.9% to 95.7% (precision stayed 100%).

## 0.2.0
- Live existence checks against UniProtKB, Ensembl, and EBI OLS4.
- Robust "not found" handling (HTTP 404 and empty results -> fabricated).
- Added `scripts/benchmark.py`, `scripts/batch.py`, `scripts/generate_benchmark.py`.

## 0.1.0
- Initial release: offline format validation of biomedical identifiers
  (GO, HP, MONDO, DOID, CHEBI, Ensembl gene, UniProtKB).
