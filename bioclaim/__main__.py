"""Command-line interface:  bioclaim "text with GO:9999999 ..."

Reads text from the arguments or stdin, verifies every biomedical identifier,
and prints the problems. Exit code is non-zero if any identifier is flagged
(handy in CI / guardrail scripts).
"""
import sys
import argparse
from . import check, __version__


def main(argv=None):
    ap = argparse.ArgumentParser(prog="bioclaim",
                                 description="Verify biomedical identifiers in text.")
    ap.add_argument("text", nargs="*", help="text to check (or pipe via stdin)")
    ap.add_argument("--entity", default=None,
                    help="the gene/protein the text is about (enables wrong-gene check)")
    ap.add_argument("--functions", action="store_true",
                    help="also verify the gene actually carries each GO term (QuickGO)")
    ap.add_argument("--offline", action="store_true",
                    help="format check only; skip database lookups")
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
