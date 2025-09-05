# scripts/eval.py
import argparse, json, sys, statistics
from pathlib import Path

from app.retrieval.searcher import elser_only, hybrid_rrf

def is_hit(hits, gold):
    """
    Return (hit: bool, rr_rank: int|None)
    rr_rank is 1-based rank for MRR (None if miss).
    """
    want_fn = (gold.get("filename") or "").lower()
    want_url = (gold.get("drive_url") or "").strip()
    want_contains = (gold.get("contains") or "").lower()

    for i, h in enumerate(hits, start=1):
        fn = (h.get("filename") or "").lower()
        url = (h.get("drive_url") or "").strip()
        snippet = (h.get("snippet") or "")  # our searcher returns 'snippet'
        text = (h.get("text") or "")        # just in case

        if want_fn and fn == want_fn:
            return True, i
        if want_url and url == want_url:
            return True, i
        if want_contains and want_contains in (snippet.lower() or text.lower()):
            return True, i
    return False, None

def evaluate(mode, k, file, verbose=False):
    lines = [json.loads(l) for l in Path(file).read_text().splitlines() if l.strip()]
    if not lines:
        print("No eval items found.", file=sys.stderr)
        sys.exit(1)

    hits_count = 0
    reciprocals = []

    search_fn = elser_only if mode == "elser" else hybrid_rrf

    for idx, item in enumerate(lines, start=1):
        q = item["q"]
        gold = item["gold"]
        results = search_fn(q, k)

        ok, rr = is_hit(results, gold)
        hits_count += int(ok)
        reciprocals.append(0.0 if rr is None else 1.0/rr)

        if verbose:
            print(f"\n[{idx}] Q: {q}")
            print(f"    gold: {gold}")
            if ok:
                print(f"    ✓ HIT @ rank {rr}")
            else:
                print(f"    ✗ MISS")
            for r_i, r in enumerate(results, start=1):
                print(f"    {r_i:>2}. score={r.get('score'):.3f} | {r.get('filename')} | {r.get('drive_url')}")
                snip = (r.get('snippet') or "")[:140].replace("\n"," ")
                print(f"        {snip}…")

    n = len(lines)
    hit_at_k = hits_count / n
    mrr = statistics.fmean(reciprocals)

    summary = {
        "mode": mode,
        "k": k,
        "n": n,
        "hit@k": round(hit_at_k, 4),
        "mrr@k": round(mrr, 4),
    }
    print("\n" + json.dumps(summary, indent=2))
    return summary

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["elser","hybrid"], default="hybrid")
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--file", default="data/eval/qa.jsonl")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    evaluate(args.mode, args.k, args.file, args.verbose)

if __name__ == "__main__":
    main()
