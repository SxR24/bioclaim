"""End-to-end example: ask a model a biology question, then screen its answer
with bioclaim before you trust it.

    pip install bioclaim openai
    set GROQ_API_KEY=...            # free key at console.groq.com  (Windows)
    export GROQ_API_KEY=...         # mac / Linux

    python examples/guard_llm.py "What is the UniProt accession and 3 GO terms for TP53?"
    python examples/guard_llm.py --entity BRCA1 "What is BRCA1's UniProt accession?"

Flow:  question -> model answer -> bioclaim.check(answer) -> flags.
bioclaim never calls the model; it screens whatever text you hand it.
"""
import os
import sys
import argparse
import pathlib

# so the example runs from a clone without installing; not needed if pip-installed
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from bioclaim import check, extract_target_entity


def ask_groq(question, model):
    from openai import OpenAI
    key = os.environ.get("GROQ_API_KEY")
    if not key:
        sys.exit("Set GROQ_API_KEY first (free key at console.groq.com).")
    client = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=key)
    resp = client.chat.completions.create(
        model=model, temperature=0.2,
        messages=[
            {"role": "system", "content": "You are a biomedical assistant. "
             "Include the relevant database identifiers (UniProt, Ensembl, GO, "
             "HP, MONDO, ChEBI) explicitly where applicable."},
            {"role": "user", "content": question},
        ])
    return resp.choices[0].message.content


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("question")
    ap.add_argument("--model", default="llama-3.3-70b-versatile")
    ap.add_argument("--entity", default=None,
                    help="gene/protein the question is about (auto-detected if omitted)")
    args = ap.parse_args()

    print(f"Asking {args.model} ...\n")
    answer = ask_groq(args.question, args.model)
    print("MODEL ANSWER\n" + "-" * 60)
    print(answer)
    print("-" * 60)

    hint = args.entity or extract_target_entity(args.question)
    result = check(answer, entity_hint=hint)

    if result.ok:
        print(f"\n[bioclaim] OK - {result.n_ids} identifiers checked, none flagged.")
    else:
        print(f"\n[bioclaim] {len(result.problems)} PROBLEM(S)"
              f"  (entity context: {hint or 'none'})")
        for p in result.problems:
            print("   -", p)


if __name__ == "__main__":
    main()
