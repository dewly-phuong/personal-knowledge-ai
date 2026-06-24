import datetime
import os

from app.services.compiler import WikiCompiler
from app.services.embedding import get_embedding_service
from app.services.extractor import GraphExtractor
from app.services.graph_store import GraphStore
from app.services.mongodb_import import (
    import_csv_files_to_mongodb,
    import_json_files_to_mongodb,
    import_xlsx_files_to_mongodb,
)
from app.services.qdrant_sync import QdrantSyncManager
from app.services.resolver import EntityResolver
from app.services.state_manager import StateManager
from app.services.wiki_search import invalidate_wiki_cache


def import_mongodb_data(dir_path: str) -> None:
    for label, fn in [
        ("JSON", import_json_files_to_mongodb),
        ("CSV", import_csv_files_to_mongodb),
        ("XLSX", import_xlsx_files_to_mongodb),
    ]:
        try:
            print(f"Importing local {label} files to MongoDB...")
            print(f"{label} Import Result: {fn(dir_path=dir_path)}")
        except Exception as e:
            print(f"Warning: Failed to import {label} files to MongoDB: {e}")


def init_vector_services():
    qdrant_url = os.getenv("QDRANT_URL")
    qdrant_key = os.getenv("QDRANT_API_KEY")
    if not qdrant_url or not qdrant_key:
        print(
            "Warning: QDRANT_URL or QDRANT_API_KEY missing. Skipping Qdrant vector sync."
        )
        return None
    try:
        print("Initializing embedding service...")
        embedding_service = get_embedding_service(api_key=None)
        print("Connecting to Qdrant Cloud...")
        return QdrantSyncManager(
            url=qdrant_url,
            api_key=qdrant_key,
            embedding_service=embedding_service,
        )
    except Exception as e:
        print(f"Warning: Failed to initialize Qdrant/Embedding services: {e}.")
        return None


def process_documents(
    modified_docs,
    extractor: GraphExtractor,
    resolver: EntityResolver,
    graph_store: GraphStore,
    wiki_compiler: WikiCompiler,
    qdrant_manager,
    state_manager: StateManager,
) -> list[str]:
    all_entities, doc_graphs = [], []
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
        _persist_doc_graph(
            doc, graph, alias_map, graph_store, wiki_compiler, qdrant_manager
        )
        state_manager.update_state(
            source_url=doc.source_url,
            last_modified=doc.last_modified,
            entities_mentioned=[
                wiki_compiler._get_entity_slug(alias_map.get(entity.name, entity.name))
                for entity in graph.entities
            ],
        )
        log_entries.append(
            f"- {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | "
            f"Ingested source {doc.path} ({doc.source_url})"
        )
    return log_entries


def finalize_ingestion(
    api_key: str, state_manager: StateManager, log_entries: list[str]
) -> None:
    GraphStore().save()
    state_manager.save()
    invalidate_wiki_cache()
    print("Invalidated wiki cache.")

    wiki_compiler = WikiCompiler(api_key=api_key)
    wiki_compiler.generate_index_page()
    _append_log(wiki_compiler.wiki_dir, log_entries)


def _persist_doc_graph(
    doc, graph, alias_map, graph_store, wiki_compiler, qdrant_manager
) -> None:
    graph_store.add_entities_and_relations(
        entities=graph.entities,
        relations=graph.relations,
        alias_map=alias_map,
        source_doc_url=doc.source_url,
    )
    for entity in graph.entities:
        canonical = alias_map.get(entity.name, entity.name)
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


def _append_log(wiki_dir: str, log_entries: list[str]) -> None:
    log_path = os.path.join(wiki_dir, "log.md")
    os.makedirs(wiki_dir, exist_ok=True)
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
