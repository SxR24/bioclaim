"""Command-line interface:  bioclaim "text with GO:9999999 ..."

Reads text from the arguments or stdin, verifies every biomedical identifier,
and prints the problems. Exit code is non-zero if any identifier is flagged
(handy in CI / guardrail scripts).
"""
import sys
import argparse
from . import check, __version__


_DESCRIPTION = """\
bioclaim - verify biomedical identifiers in text against authoritative databases.

Hand it any text (an LLM's answer, a paragraph, a document) and it checks every
identifier (UniProt, Ensembl, GO, HP, MONDO, DOID, ChEBI) and flags the ones that
are fabricated, mislabeled, assigned to the wrong gene, deprecated, or - opt-in -
GO terms the gene isn't actually annotated with. It never falsely accuses:
anything it can't verify is left unflagged.
"""

_EXAMPLES = """\
examples:
  bioclaim "TP53 is P04637 and the fabricated GO:9999999"   check text directly
  echo "model output" | bioclaim                            pipe text in
  bioclaim < answer.txt                                     check a file
  bioclaim --entity BRCA1 "the accession is P04637"         catch wrong-gene IDs
  bioclaim --functions "TP53 (P04637) does GO:0015979"      verify gene->GO term
  bioclaim --offline "GO:0006915"                           format check only
  bioclaim < examples/sample_paragraphs.txt                 try the sample set

exit code: 0 if clean, 1 if any identifier is flagged (handy for CI / scripts).
lookups are cached to ~/.cache/bioclaim (fast + offline after warm-up).
docs & issues: https://github.com/SxR24/bioclaim
"""


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="bioclaim",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=_DESCRIPTION, epilog=_EXAMPLES)
    ap.add_argument("text", nargs="*",
                    help="text to check (or pipe it in via stdin)")
    ap.add_argument("--entity", default=None, metavar="GENE",
                    help="the gene/protein the text is about (enables the wrong-gene check)")
    ap.add_argument("--functions", action="store_true",
                    help="also verify the gene actually carries each GO term (via QuickGO)")
    ap.add_argument("--offline", action="store_true",
                    help="format check only; skip all database lookups")
    ap.add_argument("--version", action="version", version=f"bioclaim {__version__}")
    args = ap.parse_args(argv)

    text = " ".join(args.text) if args.text else sys.stdin.read()
    if not text.strip():
        ap.error("no text provided (pass as arguments or via stdin)")

    result = check(text, entity_hint=args.entity, online=not args.offline,
                   check_functions=args.functions)
    print(result)
    return 1 if not result.ok else 0


if __name__ == "__main__":
    sys.exit(main())
