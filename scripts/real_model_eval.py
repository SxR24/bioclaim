"""real_model_eval.py - measure how often a REAL LLM invents biomedical IDs.

This is the study that produces the quotable headline:
    "<model> fabricated a biomedical identifier in N% of answers."

It asks a real model a set of biology questions that naturally invite database
identifiers, then uses bioclaim to check every identifier the model produced
against the authoritative source. A NOT_FOUND identifier is a fabrication -
by construction, because the source database says it does not exist.

Supports OpenAI and Anthropic. You supply the API key via environment variable.

Setup:
    pip install openai        # for --provider openai
    pip install anthropic     # for --provider anthropic
    set OPENAI_API_KEY=...    (Windows)   or   export OPENAI_API_KEY=...  (mac/Linux)

Run (from the repo root):
    python scripts/real_model_eval.py --provider openai   --model gpt-4o-mini
    python scripts/real_model_eval.py --provider anthropic --model claude-3-5-sonnet-latest --n 20

Output: a headline stat, plus real_model_report.csv with the evidence
(every question, the model's answer, and each identifier's verdict).
"""
import os
import sys
import csv
import time
import argparse
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from bioclaim import scan

FLAGGED = {"NOT_FOUND", "INVALID_FORMAT"}

SYSTEM_PROMPT = (
    "You are a biomedical research assistant. Answer each question concisely and "
    "include the relevant database identifiers (UniProt accessions, Ensembl gene "
    "IDs, GO, HP, MONDO, or ChEBI IDs) explicitly where applicable."
)


def load_questions(path, n=None):
    with open(path, encoding="utf-8") as f:
        qs = [line.strip() for line in f if line.strip()]
    return qs[:n] if n else qs


def ask_openai(model, question):
    from openai import OpenAI
    client = OpenAI()
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": SYSTEM_PROMPT},
                  {"role": "user", "content": question}],
        temperature=0.2,
    )
    return resp.choices[0].message.content


def ask_anthropic(model, question):
    import anthropic
    client = anthropic.Anthropic()
    resp = client.messages.create(
        model=model, max_tokens=600, system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": question}],
    )
    return "".join(block.text for block in resp.content if block.type == "text")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", choices=["openai", "anthropic"], required=True)
    ap.add_argument("--model", required=True, help="e.g. gpt-4o-mini or claude-3-5-sonnet-latest")
    ap.add_argument("--n", type=int, default=None, help="number of questions (default: all)")
    ap.add_argument("--questions", default="data/bio_questions.txt")
    ap.add_argument("--out", default="real_model_report.csv")
    args = ap.parse_args()

    ask = ask_openai if args.provider == "openai" else ask_anthropic
    questions = load_questions(args.questions, args.n)
    print(f"Querying {args.provider}:{args.model} on {len(questions)} questions...\n")

    rows = []
    answers_with_fabrication = 0
    total_ids = fabricated_ids = unverified_ids = 0

    for i, q in enumerate(questions, 1):
        try:
            answer = ask(args.model, q)
        except Exception as e:
            print(f"  [{i}] API error: {e}")
            continue

        verdicts = scan(answer, online=True)
        flagged = [v for v in verdicts if v.status in FLAGGED]
        total_ids += len(verdicts)
        fabricated_ids += len(flagged)
        unverified_ids += sum(1 for v in verdicts if v.status == "UNVERIFIED")
        if flagged:
            answers_with_fabrication += 1

        tag = f"FABRICATED x{len(flagged)}" if flagged else "clean"
        print(f"  [{i:>2}/{len(questions)}] {tag:<14} {q[:52]}")

        for v in verdicts:
            rows.append({
                "q_num": i, "model": args.model, "question": q,
                "curie": v.curie, "prefix": v.prefix, "status": v.status,
                "answer_excerpt": answer.replace("\n", " ")[:300],
            })
        time.sleep(0.3)  # be polite to the API

    n = len(questions)
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else
                           ["q_num", "model", "question", "curie", "prefix",
                            "status", "answer_excerpt"])
        w.writeheader()
        w.writerows(rows)

    pct = answers_with_fabrication / n * 100 if n else 0
    print("\n" + "=" * 60)
    print(f"  {args.model}  -  {n} biology questions")
    print("=" * 60)
    print(f"  answers with >=1 fabricated identifier: {answers_with_fabrication}/{n} ({pct:.0f}%)")
    print(f"  identifiers examined:                   {total_ids}")
    print(f"  fabricated (not in source database):    {fabricated_ids}")
    print(f"  unverifiable (network):                 {unverified_ids}")
    print("=" * 60)
    print(f'\nHEADLINE: {args.model} fabricated a biomedical identifier in '
          f'{pct:.0f}% of answers ({answers_with_fabrication}/{n}).')
    print(f"Evidence saved to {args.out}")


if __name__ == "__main__":
    main()
