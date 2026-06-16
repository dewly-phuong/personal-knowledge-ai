import argparse
import os
import sys
import datetime
from dotenv import load_dotenv

from app.services.connectors import (
    LocalFilesConnector,
    GitHubConnector,
    ConfluenceConnector,
)
from app.services.connectors.base import BaseConnector
from app.services.state_manager import StateManager
from app.services.extractor import GraphExtractor
from app.services.resolver import EntityResolver
from app.services.graph_store import GraphStore
from app.services.compiler import WikiCompiler
from app.services.embedding import get_embedding_service
from app.services.qdrant_sync import QdrantSyncManager
from app.core.redis import get_redis_client
from app.services.mongodb_import import (
    import_json_files_to_mongodb,
    import_csv_files_to_mongodb,
    import_xlsx_files_to_mongodb,
)
from app.services.markitdown_converter import convert_office_files


# ── Step 1: Connector factory ─────────────────────────────────────────────────


def _build_connector(
    source: str,
    dir_path: str = None,
    repo_name: str = None,
    space_key: str = None,
) -> BaseConnector:
    """Instantiates and returns the appropriate connector for the given source type."""
    if source == "office":
        if not dir_path:
            raise ValueError("--dir is required for office source.")
        print("Converting office/PDF files to Markdown via MarkItDown...")
        conv = convert_office_files(src_dir=dir_path)
        print(
            f"Conversion result: converted={len(conv['converted'])} "
            f"skipped={len(conv['skipped'])} failed={len(conv['failed'])}"
        )
        for p in conv["failed"]:
            print(f"  [failed] {p}")
        return LocalFilesConnector(directory_path=os.path.join(dir_path, "converted"))

    if source == "local":
        if not dir_path:
            raise ValueError("--dir is required for local source.")
        return LocalFilesConnector(directory_path=dir_path)

    if source == "github":
        if not repo_name:
            raise ValueError("--repo is required for github source.")
        token = os.getenv("GITHUB_TOKEN")
        if not token:
            raise ValueError("GITHUB_TOKEN environment variable not found in .env.")
        return GitHubConnector(token=token, repo_name=repo_name)

    if source == "confluence":
        if not space_key:
            raise ValueError("--space is required for confluence source.")
        url = os.getenv("CONFLUENCE_URL")
        username = os.getenv("CONFLUENCE_USERNAME")
        token = os.getenv("CONFLUENCE_API_TOKEN")
        if not url or not username or not token:
            raise ValueError(
                "CONFLUENCE_URL, CONFLUENCE_USERNAME, and CONFLUENCE_API_TOKEN must be set in .env."
            )
        return ConfluenceConnector(
            url=url, username=username, token=token, space_key=space_key
        )

    raise ValueError(f"Unsupported source type: {source}")


# ── Step 2: MongoDB structured data import (local source only) ────────────────


def _import_mongodb_data(dir_path: str) -> None:
    """Imports JSON, CSV, and XLSX files from dir_path into MongoDB."""
    for label, fn in [
        ("JSON", import_json_files_to_mongodb),
        ("CSV", import_csv_files_to_mongodb),
        ("XLSX", import_xlsx_files_to_mongodb),
    ]:
        try:
            print(f"Importing local {label} files to MongoDB...")
            res = fn(dir_path=dir_path)
            print(f"{label} Import Result: {res}")
        except Exception as e:
            print(f"Warning: Failed to import {label} files to MongoDB: {e}")


# ── Step 3: Vector service initialisation ─────────────────────────────────────


def _init_vector_services(api_key: str):
    """Initialises embedding + Qdrant services. Returns (embedding_service, qdrant_manager) or (None, None)."""
    qdrant_url = os.getenv("QDRANT_URL")
    qdrant_key = os.getenv("QDRANT_API_KEY")

    if not qdrant_url or not qdrant_key:
        print(
            "Warning: QDRANT_URL or QDRANT_API_KEY missing. Skipping Qdrant vector sync."
        )
        return None, None

    try:
        print("Initializing embedding service...")
        embedding_service = get_embedding_service(api_key=api_key)
        print("Connecting to Qdrant Cloud...")
        qdrant_manager = QdrantSyncManager(
            url=qdrant_url,
            api_key=qdrant_key,
            embedding_service=embedding_service,
        )
        return embedding_service, qdrant_manager
    except Exception as e:
        print(
            f"Warning: Failed to initialize Qdrant/Embedding services: {e}. Vector sync will be skipped."
        )
        return None, None


# ── Step 4: Core extraction + graph/wiki update loop ─────────────────────────


def _process_documents(
    modified_docs,
    extractor: GraphExtractor,
    resolver: EntityResolver,
    graph_store: GraphStore,
    wiki_compiler: WikiCompiler,
    qdrant_manager,
    state_manager: StateManager,
) -> list:
    """Extracts entities, resolves them, updates the graph, compiles wiki pages. Returns log entries."""
    all_entities = []
    doc_graphs = []

    print("Extracting entities and relations...")
    for doc in modified_docs:
        print(f"  Extracting: {doc.path}")
        extracted = extractor.extract(doc.content)
        doc_graphs.append((doc, extracted))
        all_entities.extend(extracted.entities)

    print("Running entity resolution...")
    resolution = resolver.resolve(all_entities)
    alias_map = {
        alias: cluster.canonical
        for cluster in resolution.clusters
        for alias in cluster.aliases
    }

    print("Writing files & updating structures...")
    log_entries = []

    for doc, graph in doc_graphs:
        graph_store.add_entities_and_relations(
            entities=graph.entities,
            relations=graph.relations,
            alias_map=alias_map,
            source_doc_url=doc.source_url,
        )

        doc_entity_slugs = []
        for entity in graph.entities:
            canonical = alias_map.get(entity.name, entity.name)
            doc_entity_slugs.append(wiki_compiler._get_entity_slug(canonical))
            print(f"  Compiling Wiki Page for: {canonical}")
            page_path, page_content = wiki_compiler.compile_entity_page(
                entity_name=canonical,
                entity_type=entity.type,
                raw_doc_content=doc.content,
                source_url=doc.source_url,
            )
            if qdrant_manager:
                qdrant_manager.upsert_page(
                    file_path=page_path,
                    title=canonical,
                    content=page_content,
                    source_urls=[doc.source_url],
                )

        state_manager.update_state(
            source_url=doc.source_url,
            last_modified=doc.last_modified,
            entities_mentioned=doc_entity_slugs,
        )
        log_entries.append(
            f"- {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | "
            f"Ingested source {doc.path} ({doc.source_url})"
        )

    return log_entries


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
    connector = _build_connector(source, dir_path, repo_name, space_key)

    # 2. Import structured data (local sources only)
    if source == "local" and dir_path:
        _import_mongodb_data(dir_path)

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
    _, qdrant_manager = _init_vector_services(api_key)

    # 5. Extract, resolve, compile
    log_entries = _process_documents(
        modified_docs=modified_docs,
        extractor=GraphExtractor(api_key=api_key),
        resolver=EntityResolver(api_key=api_key),
        graph_store=GraphStore(),
        wiki_compiler=WikiCompiler(api_key=api_key),
        qdrant_manager=qdrant_manager,
        state_manager=state_manager,
    )

    # 6. Persist graph + state
    GraphStore().save()
    state_manager.save()

    # 7. Invalidate Redis wiki cache
    try:
        get_redis_client().delete("wiki:cache")
        print("Invalidated wiki cache in Redis.")
    except Exception as e:
        print(f"Failed to invalidate wiki cache: {e}")

    # 8. Regenerate wiki index
    WikiCompiler(api_key=api_key).generate_index_page()

    # 9. Append to wiki/log.md
    wiki_compiler = WikiCompiler(api_key=api_key)
    log_path = os.path.join(wiki_compiler.wiki_dir, "log.md")
    os.makedirs(wiki_compiler.wiki_dir, exist_ok=True)
    existing_log = ""
    try:
        if os.path.exists(log_path):
            with open(log_path, "r", encoding="utf-8") as f:
                existing_log = f.read()
    except Exception:
        pass
    with open(log_path, "w", encoding="utf-8") as f:
        f.write(
            f"# Ingestion Log\n\n{chr(10).join(log_entries)}\n\n{existing_log}".strip()
        )

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
