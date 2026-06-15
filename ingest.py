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
from app.services.state_manager import StateManager
from app.services.extractor import GraphExtractor
from app.services.resolver import EntityResolver
from app.services.graph_store import GraphStore
from app.services.compiler import WikiCompiler
from app.services.embedding import get_embedding_service
from app.services.qdrant_sync import QdrantSyncManager
from app.core.redis import get_redis_client

def run_ingest_pipeline(
    source: str,
    dir_path: str = None,
    repo_name: str = None,
    space_key: str = None
) -> dict:
    """
    Core ingestion pipeline logic refactored into a reusable function.
    Can be run from command line or called inside background threads.
    """
    # Load environment variables
    load_dotenv()
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY environment variable not found in .env.")

    # 1. Initialize the correct connector
    connector = None
    if source == "local":
        if not dir_path:
            raise ValueError("--dir is required for local source.")
        connector = LocalFilesConnector(directory_path=dir_path)
        try:
            from app.services.mongodb_import import import_json_files_to_mongodb
            print("Importing local JSON files to MongoDB...")
            res = import_json_files_to_mongodb(dir_path=dir_path)
            print(f"JSON Import Result: {res}")
        except Exception as e:
            print(f"Warning: Failed to import JSON files to MongoDB: {e}")
    elif source == "github":
        if not repo_name:
            raise ValueError("--repo is required for github source.")
        token = os.getenv("GITHUB_TOKEN")
        if not token:
            raise ValueError("GITHUB_TOKEN environment variable not found in .env.")
        connector = GitHubConnector(token=token, repo_name=repo_name)
    elif source == "confluence":
        if not space_key:
            raise ValueError("--space is required for confluence source.")
        url = os.getenv("CONFLUENCE_URL")
        username = os.getenv("CONFLUENCE_USERNAME")
        token = os.getenv("CONFLUENCE_API_TOKEN")
        if not url or not username or not token:
            raise ValueError("CONFLUENCE_URL, CONFLUENCE_USERNAME, and CONFLUENCE_API_TOKEN must be set in .env.")
        connector = ConfluenceConnector(url=url, username=username, token=token, space_key=space_key)
    else:
        raise ValueError(f"Unsupported source type: {source}")

    # 2. Fetch documents
    print(f"Fetching documents from {source}...")
    documents = connector.fetch_documents()
    print(f"Fetched {len(documents)} document(s).")
    if not documents:
        print("No documents found. Exiting.")
        return {"status": "success", "summary": "No documents found to ingest."}

    # 3. Filter using StateManager for incremental sync
    state_manager = StateManager()
    modified_docs = []
    
    for doc in documents:
        if state_manager.is_modified(doc.source_url, doc.last_modified):
            modified_docs.append(doc)
        else:
            print(f"Skipping {doc.path} (unchanged since last run).")

    if not modified_docs:
        print("All documents are up-to-date. Ingestion skipped.")
        return {"status": "success", "summary": "All documents are up-to-date. Ingestion skipped."}

    print(f"Processing {len(modified_docs)} new/modified document(s)...")

    # 4. Initialize embedding and Qdrant sync
    embedding_service = None
    qdrant_manager = None
    
    qdrant_url = os.getenv("QDRANT_URL")
    qdrant_key = os.getenv("QDRANT_API_KEY")
    
    if qdrant_url and qdrant_key:
        try:
            print("Initializing embedding service...")
            embedding_service = get_embedding_service(api_key=api_key)
            print("Connecting to Qdrant Cloud...")
            qdrant_manager = QdrantSyncManager(
                url=qdrant_url,
                api_key=qdrant_key,
                embedding_service=embedding_service,
            )
        except Exception as e:
            print(f"Warning: Failed to initialize Qdrant/Embedding services: {e}. Vector sync will be skipped.")
    else:
        print("Warning: QDRANT_URL or QDRANT_API_KEY missing in .env. Skipping Qdrant vector sync.")

    # 5. Core Ingestion Pipeline
    extractor = GraphExtractor(api_key=api_key)
    resolver = EntityResolver(api_key=api_key)
    graph_store = GraphStore()
    wiki_compiler = WikiCompiler(api_key=api_key)

    # Gather entities for resolution
    all_extracted_entities = []
    doc_graphs = []

    print("Extracting entities and relations...")
    for doc in modified_docs:
        print(f"  Extracting: {doc.path}")
        extracted_graph = extractor.extract(doc.content)
        doc_graphs.append((doc, extracted_graph))
        all_extracted_entities.extend(extracted_graph.entities)

    print("Running entity resolution...")
    resolution_result = resolver.resolve(all_extracted_entities)
    
    # Map raw entity name -> canonical name
    alias_map = {}
    for cluster in resolution_result.clusters:
        for alias in cluster.aliases:
            alias_map[alias] = cluster.canonical

    # Update Knowledge Graph and Wiki
    print("Writing files & updating structures...")
    log_entries = []
    
    for doc, graph in doc_graphs:
        # Update graph database
        graph_store.add_entities_and_relations(
            entities=graph.entities,
            relations=graph.relations,
            alias_map=alias_map,
            source_doc_url=doc.source_url,
        )
        
        # Compile wiki pages for each unique canonical entity from this document
        doc_entities_slugs = []
        for entity in graph.entities:
            canonical_name = alias_map.get(entity.name, entity.name)
            doc_entities_slugs.append(wiki_compiler._get_entity_slug(canonical_name))
            
            print(f"  Compiling Wiki Page for canonical entity: {canonical_name}")
            page_path, page_content = wiki_compiler.compile_entity_page(
                entity_name=canonical_name,
                entity_type=entity.type,
                raw_doc_content=doc.content,
                source_url=doc.source_url,
            )
            
            # Sync to Qdrant Cloud if available
            if qdrant_manager:
                qdrant_manager.upsert_page(
                    file_path=page_path,
                    title=canonical_name,
                    content=page_content,
                    source_urls=[doc.source_url],
                )

        # Update state_manager
        state_manager.update_state(
            source_url=doc.source_url,
            last_modified=doc.last_modified,
            entities_mentioned=doc_entities_slugs,
        )
        
        log_entries.append(f"- {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Ingested source {doc.path} ({doc.source_url})")

    # Save Graph & State
    graph_store.save()
    state_manager.save()
    
    # Invalidate Redis wiki cache so next search is loaded with updated files
    try:
        r = get_redis_client()
        r.delete("wiki:cache")
        print("Invalidated wiki cache in Redis.")
    except Exception as e:
        print(f"Failed to invalidate wiki cache in Redis: {e}")
    
    # Programmatic Index Page Generation
    wiki_compiler.generate_index_page()

    # Append to wiki/log.md
    log_path = os.path.join(wiki_compiler.wiki_dir, "log.md")
    os.makedirs(wiki_compiler.wiki_dir, exist_ok=True)
    existing_log = ""
    if os.path.exists(log_path):
        try:
            with open(log_path, "r", encoding="utf-8") as f:
                existing_log = f.read()
        except Exception:
            pass
            
    with open(log_path, "w", encoding="utf-8") as f:
        new_log = "\n".join(log_entries)
        f.write(f"# Ingestion Log\n\n{new_log}\n\n{existing_log}".strip())

    summary_msg = f"Successfully ingested {len(modified_docs)} document(s). Extracted {len(all_extracted_entities)} entities."
    print("Ingestion run completed successfully!")
    return {"status": "success", "summary": summary_msg}

def main():
    parser = argparse.ArgumentParser(description="Ingest documentation into the Knowledge Graph and Wiki.")
    parser.add_argument(
        "--source",
        choices=["local", "github", "confluence"],
        required=True,
        help="The source type to ingest from.",
    )
    # Source-specific arguments
    parser.add_argument("--dir", help="Directory path (required for local source).")
    parser.add_argument("--repo", help="Repository path 'owner/repo' (required for github source).")
    parser.add_argument("--space", help="Confluence space key (required for confluence source).")

    args = parser.parse_args()

    try:
        run_ingest_pipeline(
            source=args.source,
            dir_path=args.dir,
            repo_name=args.repo,
            space_key=args.space
        )
    except Exception as e:
        print(f"Error running ingestion: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
