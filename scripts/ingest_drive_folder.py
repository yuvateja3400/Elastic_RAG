# scripts/ingest_drive_folder.py
import argparse
from app.ingestion.ingestion_pipeline import run_ingestion, write_report, index_chunks

def main():
    ap = argparse.ArgumentParser(description="Ingest PDFs from Google Drive.")
    ap.add_argument("--folder-id", type=str, default=None, help="Override GDRIVE_FOLDER_ID")
    ap.add_argument("--limit", type=int, default=None, help="Limit number of files")
    ap.add_argument("--report", type=str, default="./tmp/ingestion_report.json", help="Report JSON path")
    ap.add_argument("--index", action="store_true", help="Index chunks into Elasticsearch via ELSER pipeline")
    args = ap.parse_args()

    report, chunks = run_ingestion(folder_id=args.folder_id, limit_files=args.limit)
    out = write_report(report, args.report)
    print(f"\n✅ Ingestion dry-run complete.")
    print(f"   Files seen: {report['files_seen']}")
    print(f"   Total chunks: {report['chunks_total']}")
    print(f"   Report saved to: {out}")

    if args.index and chunks:
        res = index_chunks(chunks)
        print(f"✅ Indexed {res['indexed']} chunks into Elasticsearch")

if __name__ == "__main__":
    main()
