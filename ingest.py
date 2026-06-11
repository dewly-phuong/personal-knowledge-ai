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

    # Load environment variables
    load_dotenv()
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("Error: GOOGLE_API_KEY environment variable not found in .env.")
        sys.exit(1)

    # 1. Initialize the correct connector
    connector = None
    if args.source == "local":
        if not args.dir:
            print("Error: --dir is required for local source.")
            sys.exit(1)
        connector = LocalFilesConnector(directory_path=args.dir)
    elif args.source == "github":
        if not args.repo:
            print("Error: --repo is required for github source.")
            sys.exit(1)
        token = os.getenv("GITHUB_TOKEN")
        if not token:
            print("Error: GITHUB_TOKEN environment variable not found in .env.")
            sys.exit(1)
        connector = GitHubConnector(token=token, repo_name=args.repo)
    elif args.source == "confluence":
        if not args.space:
            print("Error: --space is required for confluence source.")
            sys.exit(1)
        url = os.getenv("CONFLUENCE_URL")
        username = os.getenv("CONFLUENCE_USERNAME")
        token = os.getenv("CONFLUENCE_API_TOKEN")
        if not url or not username or not token:
            print("Error: CONFLUENCE_URL, CONFLUENCE_USERNAME, and CONFLUENCE_API_TOKEN must be set in .env.")
            sys.exit(1)
        connector = ConfluenceConnector(url=url, username=username, token=token, space_key=args.space)

    # 2. Fetch documents
    print(f"Fetching documents from {args.source}...")
    documents = connector.fetch_documents()
    print(f"Fetched {len(documents)} document(s).")
    if not documents:
        print("No documents found. Exiting.")
        return

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
        return

    print(f"Processing {len(modified_docs)} new/modified document(s)...")

    # 4. Initialize local embedding and Qdrant sync (lazy loaded to prevent model load on skipped runs)
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

    print("Ingestion run completed successfully!")

if __name__ == "__main__":
    main()
