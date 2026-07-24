"""real_model_eval.py - measure how often a REAL LLM invents biomedical IDs.

This is the study that produces the quotable headline:
    "<model> fabricated a biomedical identifier in N% of answers."

It asks a real model a set of biology questions that naturally invite database
identifiers, then uses bioclaim to check every identifier the model produced
against the authoritative source. A NOT_FOUND identifier is a fabrication -
by construction, because the source database says it does not exist.

Supports OpenAI, Anthropic, and any OpenAI-compatible API (xAI/Grok, Groq,
OpenRouter, local Ollama). You supply the API key via environment variable -
never hard-code it, or it leaks into git.

Setup (xAI / Grok example, Windows):
    pip install openai
    set XAI_API_KEY=your_key_here

Run (from the repo root):
    python scripts/real_model_eval.py --provider xai       --model grok-4.5
    python scripts/real_model_eval.py --provider openai    --model gpt-4o-mini
    python scripts/real_model_eval.py --provider anthropic --model claude-3-5-sonnet-latest --n 20
    python scripts/real_model_eval.py --provider groq      --model llama-3.3-70b-versatile

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
from bioclaim import check_claims

FABRICATED = {"NOT_FOUND", "INVALID_FORMAT"}   # invented identifiers
MISLABELED = {"SUPPORTED_LABEL_MISMATCH"}       # real id, wrong description
FLAGGED = FABRICATED | MISLABELED

SYSTEM_PROMPT = (
    "You are a biomedical research assistant. Answer each question concisely and "
    "include the relevant database identifiers (UniProt accessions, Ensembl gene "
    "IDs, GO, HP, MONDO, or ChEBI IDs) explicitly where applicable."
)


def load_questions(path, n=None):
    with open(path, encoding="utf-8") as f:
        qs = [line.strip() for line in f if line.strip()]
    return qs[:n] if n else qs


# OpenAI-compatible providers: base URL + which env var holds the key.
# xAI (Grok), Groq, OpenRouter and Ollama all speak the OpenAI API.
OPENAI_COMPATIBLE = {
    "openai": (None, "OPENAI_API_KEY"),
    "xai":    ("https://api.x.ai/v1", "XAI_API_KEY"),
    "groq":   ("https://api.groq.com/openai/v1", "GROQ_API_KEY"),
    "openrouter": ("https://openrouter.ai/api/v1", "OPENROUTER_API_KEY"),
    "ollama": ("http://localhost:11434/v1", "OLLAMA_API_KEY"),  # any value works locally
}


def ask_openai(model, question, base_url=None, api_key=None):
    from openai import OpenAI
    client = OpenAI(base_url=base_url, api_key=api_key)
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
    ap.add_argument("--provider",
                    choices=["openai", "anthropic", "xai", "groq", "openrouter", "ollama"],
                    required=True)
    ap.add_argument("--model", required=True, help="e.g. grok-4.5, gpt-4o-mini, claude-3-5-sonnet-latest")
    ap.add_argument("--n", type=int, default=None, help="number of questions (default: all)")
    ap.add_argument("--questions", default="data/bio_questions.txt")
    ap.add_argument("--out", default="real_model_report.csv")
    args = ap.parse_args()

    if args.provider == "anthropic":
        ask = ask_anthropic
    else:
        base_url, key_env = OPENAI_COMPATIBLE[args.provider]
        api_key = os.environ.get(key_env) or os.environ.get("OPENAI_API_KEY") or "ollama"
        if args.provider != "ollama" and not os.environ.get(key_env):
            print(f"ERROR: set your API key first, e.g.  set {key_env}=...")
            sys.exit(1)
        ask = lambda m, q: ask_openai(m, q, base_url=base_url, api_key=api_key)

    questions = load_questions(args.questions, args.n)
    print(f"Querying {args.provider}:{args.model} on {len(questions)} questions...\n")

    rows = []
    answers_flagged = 0
    total_ids = fabricated_ids = mislabeled_ids = unverified_ids = 0

    for i, q in enumerate(questions, 1):
        try:
            answer = ask(args.model, q)
        except Exception as e:
            print(f"  [{i}] API error: {e}")
            continue

        verdicts = check_claims(answer, online=True)
        fab = [v for v in verdicts if v.status in FABRICATED]
        mis = [v for v in verdicts if v.status in MISLABELED]
        total_ids += len(verdicts)
        fabricated_ids += len(fab)
        mislabeled_ids += len(mis)
        unverified_ids += sum(1 for v in verdicts if v.status == "UNVERIFIED")
        if fab or mis:
            answers_flagged += 1

        parts = []
        if fab:
            parts.append(f"FABRICATED x{len(fab)}")
        if mis:
            parts.append(f"MISLABELED x{len(mis)}")
        tag = " + ".join(parts) if parts else "clean"
        print(f"  [{i:>2}/{len(questions)}] {tag:<26} {q[:44]}")

        for v in verdicts:
            rows.append({
                "q_num": i, "model": args.model, "question": q,
                "curie": v.curie, "prefix": v.prefix, "status": v.status,
                "claimed_label": v.claimed_label or "",
                "real_label": v.canonical_label or "",
                "answer_excerpt": answer.replace("\n", " ")[:300],
            })
        time.sleep(0.3)  # be polite to the API

    n = len(questions)
    fields = ["q_num", "model", "question", "curie", "prefix", "status",
              "claimed_label", "real_label", "answer_excerpt"]
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    pct = answers_flagged / n * 100 if n else 0
    print("\n" + "=" * 60)
    print(f"  {args.model}  -  {n} biology questions")
    print("=" * 60)
    print(f"  answers with >=1 hallucinated identifier: {answers_flagged}/{n} ({pct:.0f}%)")
    print(f"  identifiers examined:                     {total_ids}")
    print(f"  fabricated (id does not exist):           {fabricated_ids}")
    print(f"  mislabeled (real id, wrong description):  {mislabeled_ids}")
    print(f"  unverifiable (network):                   {unverified_ids}")
    print("=" * 60)
    print(f'\nHEADLINE: {args.model} produced a fabricated or mislabeled '
          f'biomedical identifier in {pct:.0f}% of answers ({answers_flagged}/{n}).')
    print(f"Evidence saved to {args.out}")


if __name__ == "__main__":
    main()
