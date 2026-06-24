import argparse
import os
import sys
from dotenv import load_dotenv

from app.services.compiler import WikiCompiler
from app.services.extractor import GraphExtractor
from app.services.graph_store import GraphStore
from app.services.ingest_connectors import build_connector
from app.services.ingest_pipeline import (
    finalize_ingestion,
    import_mongodb_data,
    init_vector_services,
    process_documents,
)
from app.services.resolver import EntityResolver
from app.services.state_manager import StateManager


# ── Main pipeline ─────────────────────────────────────────────────────────────


def run_ingest_pipeline(
    source: str,
    dir_path: str = None,
    repo_name: str = None,
    space_key: str = None,
    office_only: bool = False,
) -> dict:
    """
    Core ingestion pipeline logic. Can be run from the CLI or called from background threads.
    """
    load_dotenv()
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY environment variable not found in .env.")

    # 1. Build connector
    connector = build_connector(source, dir_path, repo_name, space_key)

    # 2. Import structured data (local sources only)
    if source == "local" and dir_path:
        import_mongodb_data(dir_path)

    # 3. Fetch and filter documents
    print(f"Fetching documents from {source}...")
    documents = connector.fetch_documents()
    print(f"Fetched {len(documents)} document(s).")
    if not documents:
        print("No documents found. Exiting.")
        return {"status": "success", "summary": "No documents found to ingest."}

    state_manager = StateManager()
    modified_docs = [
        d for d in documents if state_manager.is_modified(d.source_url, d.last_modified)
    ]
    skipped = len(documents) - len(modified_docs)
    if skipped:
        print(f"Skipping {skipped} unchanged document(s).")
    if not modified_docs:
        print("All documents are up-to-date. Ingestion skipped.")
        return {
            "status": "success",
            "summary": "All documents are up-to-date. Ingestion skipped.",
        }
    print(f"Processing {len(modified_docs)} new/modified document(s)...")

    # 4. Initialise vector services
    qdrant_manager = init_vector_services()

    # 5. Extract, resolve, compile
    graph_store = GraphStore()
    log_entries = process_documents(
        modified_docs=modified_docs,
        extractor=GraphExtractor(api_key=api_key),
        resolver=EntityResolver(api_key=api_key),
        graph_store=graph_store,
        wiki_compiler=WikiCompiler(api_key=api_key),
        qdrant_manager=qdrant_manager,
        state_manager=state_manager,
    )

    finalize_ingestion(api_key, state_manager, log_entries)

    summary = f"Successfully ingested {len(modified_docs)} document(s). Extracted {sum(1 for _ in log_entries)} entities."
    print("Ingestion run completed successfully!")
    return {"status": "success", "summary": summary}


def main():
    parser = argparse.ArgumentParser(
        description="Ingest documentation into the Knowledge Graph and Wiki."
    )
    parser.add_argument(
        "--source",
        choices=["local", "office", "github", "confluence"],
        required=True,
        help=(
            "The source type to ingest from. Use 'office' to convert .docx/.pptx/.pdf to "
            "Markdown first and ingest only the converted files."
        ),
    )
    parser.add_argument(
        "--dir", help="Directory path (required for local/office source)."
    )
    parser.add_argument(
        "--repo", help="Repository path 'owner/repo' (required for github source)."
    )
    parser.add_argument(
        "--space", help="Confluence space key (required for confluence source)."
    )

    args = parser.parse_args()
    try:
        run_ingest_pipeline(
            source=args.source,
            dir_path=args.dir,
            repo_name=args.repo,
            space_key=args.space,
        )
    except Exception as e:
        print(f"Error running ingestion: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
