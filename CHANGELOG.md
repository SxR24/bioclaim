# Changelog

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
