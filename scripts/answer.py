import argparse, json
from app.retrieval.searcher import elser_only, hybrid_rrf
from app.generation.generator import generate_answer
from app.generation.guardrails import is_safe, REFUSAL

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["elser","hybrid"], default="hybrid")
    ap.add_argument("--q", required=True)
    ap.add_argument("--k", type=int, default=5)
    args = ap.parse_args()

    if not is_safe(args.q):
        print(json.dumps({"answer": REFUSAL, "citations": []}))
        return

    hits = elser_only(args.q, args.k) if args.mode == "elser" else hybrid_rrf(args.q, args.k)
    out = generate_answer(args.q, hits)
    print(json.dumps(out, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
