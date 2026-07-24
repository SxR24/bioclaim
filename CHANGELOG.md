# Changelog

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
