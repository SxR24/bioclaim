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
import json
import time
import argparse
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from bioclaim import check_claims

FABRICATED = {"NOT_FOUND", "INVALID_FORMAT"}   # invented identifiers
MISLABELED = {"SUPPORTED_LABEL_MISMATCH"}       # real id, wrong description
WRONG_ENTITY = {"SUPPORTED_ENTITY_MISMATCH"}    # real id, wrong gene/entity
OBSOLETE = {"SUPPORTED_OBSOLETE"}               # real id, but deprecated/retired
FLAGGED = FABRICATED | MISLABELED | WRONG_ENTITY | OBSOLETE

SYSTEM_PROMPT = (
    "You are a biomedical research assistant. Answer each question concisely and "
    "include the relevant database identifiers (UniProt accessions, Ensembl gene "
    "IDs, GO, HP, MONDO, or ChEBI IDs) explicitly where applicable."
)


def _ask_with_retry(ask, model, question, retries=4):
    """Call the model, retrying rate-limit (429) errors with backoff.

    Honors the server's suggested 'retry in Ns' when present. Returns the answer
    text, or None if it still fails (e.g. a daily quota that a wait can't clear).
    """
    import re
    for attempt in range(retries + 1):
        try:
            return ask(model, question)
        except Exception as e:
            msg = str(e)
            low = msg.lower()
            rate_limited = any(s in low for s in (
                "429", "503", "rate limit", "resource_exhausted", "resourceexhausted",
                "exhausted", "limit reached", "overloaded", "too many requests"))
            if not rate_limited or attempt == retries:
                if not rate_limited:
                    print(f"      API error: {msg[:120]}")
                return None
            m = re.search(r"retry in ([0-9.]+)s", msg) or re.search(r"'?retryDelay'?[:=]\s*'?([0-9]+)s", msg)
            wait = min(float(m.group(1)) if m else 2 * (2 ** attempt), 60) + 1
            print(f"      rate-limited, waiting {wait:.0f}s (attempt {attempt + 1}/{retries})...")
            time.sleep(wait)
    return None


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
    "gemini": ("https://generativelanguage.googleapis.com/v1beta/openai/", "GEMINI_API_KEY"),
    "nvidia": ("https://integrate.api.nvidia.com/v1", "NVIDIA_API_KEY"),
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
                    choices=["openai", "anthropic", "xai", "groq", "gemini",
                             "nvidia", "openrouter", "ollama"],
                    required=True)
    ap.add_argument("--model", required=True, help="e.g. grok-4.5, gpt-4o-mini, claude-3-5-sonnet-latest")
    ap.add_argument("--n", type=int, default=None, help="number of questions (default: all)")
    ap.add_argument("--questions", default="data/bio_questions.txt")
    ap.add_argument("--out", default="real_model_report.csv")
    ap.add_argument("--delay", type=float, default=0.3,
                    help="seconds between calls (raise for tight rate limits, e.g. 13 for Gemini free)")
    ap.add_argument("--retries", type=int, default=4,
                    help="retries with backoff on rate-limit (429) errors")
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
    answered = answers_flagged = 0
    total_ids = fabricated_ids = mislabeled_ids = 0
    wrong_entity_ids = obsolete_ids = unverified_ids = 0

    try:
      for i, q in enumerate(questions, 1):
        answer = _ask_with_retry(ask, args.model, q, args.retries)
        if answer is None:
            print(f"  [{i:>2}/{len(questions)}] SKIPPED (rate-limited / API error)")
            continue
        answered += 1

        verdicts = check_claims(answer, online=True)
        fab = [v for v in verdicts if v.status in FABRICATED]
        mis = [v for v in verdicts if v.status in MISLABELED]
        ent = [v for v in verdicts if v.status in WRONG_ENTITY]
        obs = [v for v in verdicts if v.status in OBSOLETE]
        total_ids += len(verdicts)
        fabricated_ids += len(fab)
        mislabeled_ids += len(mis)
        wrong_entity_ids += len(ent)
        obsolete_ids += len(obs)
        unverified_ids += sum(1 for v in verdicts if v.status == "UNVERIFIED")
        if fab or mis or ent or obs:
            answers_flagged += 1

        parts = []
        if fab:
            parts.append(f"FABRICATED x{len(fab)}")
        if mis:
            parts.append(f"MISLABELED x{len(mis)}")
        if ent:
            parts.append(f"WRONG-ENTITY x{len(ent)}")
        if obs:
            parts.append(f"OBSOLETE x{len(obs)}")
        tag = " + ".join(parts) if parts else "clean"
        print(f"  [{i:>2}/{len(questions)}] {tag:<34} {q[:36]}")

        for v in verdicts:
            rows.append({
                "q_num": i, "model": args.model, "question": q,
                "curie": v.curie, "prefix": v.prefix, "status": v.status,
                "claimed_label": v.claimed_label or "",
                "real_label": v.canonical_label or "",
                "answer_excerpt": answer.replace("\n", " ")[:300],
            })
        time.sleep(args.delay)  # be polite to the API
    except KeyboardInterrupt:
        print("\n[interrupted] saving partial results collected so far...")

    n = len(questions)
    skipped = n - answered
    fields = ["q_num", "model", "question", "curie", "prefix", "status",
              "claimed_label", "real_label", "answer_excerpt"]
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    # sidecar so downstream tools know the true denominator (answered != n)
    json.dump({"model": args.model, "n": n, "answered": answered,
               "skipped": skipped, "answers_flagged": answers_flagged,
               "total_ids": total_ids, "fabricated": fabricated_ids,
               "mislabeled": mislabeled_ids, "wrong_entity": wrong_entity_ids,
               "obsolete": obsolete_ids},
              open(args.out + ".meta.json", "w"))

    # rate is over ANSWERED questions, never the full set - a partial run
    # (rate-limited) must not silently divide by 40.
    denom = answered or 1
    pct = answers_flagged / denom * 100
    print("\n" + "=" * 60)
    print(f"  {args.model}  -  {answered}/{n} questions answered"
          + (f"  ({skipped} SKIPPED - rate-limited)" if skipped else ""))
    print("=" * 60)
    print(f"  answers with >=1 hallucinated identifier: {answers_flagged}/{answered} ({pct:.0f}%)")
    print(f"  identifiers examined:                     {total_ids}")
    print(f"  fabricated (id does not exist):           {fabricated_ids}")
    print(f"  mislabeled (real id, wrong description):  {mislabeled_ids}")
    print(f"  wrong-entity (real id, wrong gene):       {wrong_entity_ids}")
    print(f"  obsolete (real id, deprecated):           {obsolete_ids}")
    print(f"  unverifiable (network):                   {unverified_ids}")
    print("=" * 60)
    if skipped:
        print(f"\nWARNING: {skipped} questions were skipped (rate limit). This is a "
              f"PARTIAL run - not comparable to a full 40-question run.")
    print(f'\nHEADLINE: {args.model} produced a fabricated, mislabeled, misassigned '
          f'or obsolete identifier in {pct:.0f}% of {answered} answered questions.')
    print(f"Evidence saved to {args.out}")


if __name__ == "__main__":
    main()
