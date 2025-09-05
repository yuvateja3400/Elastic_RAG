import argparse, json
from app.retrieval.searcher import elser_only, hybrid_rrf

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--mode", choices=["elser","hybrid"], default="elser")
    p.add_argument("--q", required=True, help="question/query")
    p.add_argument("--k", type=int, default=5)
    a = p.parse_args()
    results = elser_only(a.q, a.k) if a.mode=="elser" else hybrid_rrf(a.q, a.k)
    print(json.dumps(results, indent=2))

if __name__ == "__main__":
    main()
