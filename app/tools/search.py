"""
Knowledge-base search tools: knowledge_search (unified), graph_traverse,
uploaded_file_context.
"""

import asyncio
import json
import math
from typing import Any

from langchain_core.tools import tool

from app.retrieval.contracts import SearchContext
from app.retrieval.sources import build_default_registry
from app.services.graph_store import GraphStore
from app.tools.retrieval_context import (
    get_current_upload_ids,
    get_current_upload_session,
    register_retrieval,
)


def _graph_lookup(entity_name: str, query: str):
    """Internal helper: graph traversal + fuzzy matching for a named entity.

    Returns (graph_context_str, expanded_query_str, node_descriptions_list).
    """
    store = GraphStore()
    subg_1hop = store.get_subgraph(entity_name, hops=1)
    subg_2hop = store.get_subgraph(entity_name, hops=2)

    canonical = entity_name
    if not subg_1hop or not subg_1hop["nodes"]:
        all_nodes = list(store.graph.nodes)
        entity_lower = entity_name.lower().strip()

        matches = [n for n in all_nodes if n.lower().strip() == entity_lower]

        if not matches:
            entity_words = set(entity_lower.split())
            matches = [
                n
                for n in all_nodes
                if entity_words
                and len(entity_words & set(n.lower().split())) / len(entity_words)
                >= 0.5
            ]

        if not matches:
            from difflib import get_close_matches

            lower_map = {n.lower(): n for n in all_nodes}
            close = get_close_matches(entity_lower, list(lower_map), n=3, cutoff=0.55)
            matches = [lower_map[c] for c in close]

        if matches:
            canonical = matches[0]
            subg_1hop = store.get_subgraph(canonical, hops=1)
            subg_2hop = store.get_subgraph(canonical, hops=2)

    node_descriptions = []
    if subg_1hop and subg_1hop["nodes"]:
        edge_lines = [
            f"{e['source']} --[{e['predicate']}]--> {e['target']}"
            for e in subg_1hop["edges"]
        ]
        graph_context = f"Relations for '{canonical}': " + (
            " | ".join(edge_lines) if edge_lines else "no direct relations"
        )
        # Node details from 2-hop subgraph
        node_descriptions = [
            f"- {n['id']} [{n['type']}]{' (' + n['description'] + ')' if n.get('description') else ''}"
            for n in subg_2hop["nodes"]
        ]
        neighbor_names = [n["id"] for n in subg_2hop["nodes"] if n["id"] != canonical]
        expanded_query = f"{query} {canonical} {' '.join(neighbor_names[:10])}"
    else:
        graph_context = f"'{entity_name}' not found in knowledge graph."
        expanded_query = f"{query} {entity_name}"

    return graph_context, expanded_query, node_descriptions


@tool
def knowledge_search(
    query: str,
    limit: int = 100,
    timeout_seconds: float = 8.0,
) -> str:
    """
    Search every configured knowledge source in parallel and return one normalized result per source.

    Always use this before answering factual or internal-company questions. Sources with no data
    are returned with status="empty" and data=null. Sources that fail are returned with
    status="error" and data=null.
    """
    context = SearchContext(
        session_id=get_current_upload_session(),
        upload_ids=get_current_upload_ids(),
        limit=limit,
        timeout_seconds=timeout_seconds,
    )
    bundle = _run_registry_search(query, context)
    payload = _sanitize_json_value(bundle.to_dict())
    serialized = json.dumps(payload, ensure_ascii=False, indent=2)
    register_retrieval([json.dumps(payload, ensure_ascii=False)])
    return serialized


def _run_registry_search(query: str, context: SearchContext):
    registry = build_default_registry()
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(registry.search_all(query, context))
    raise RuntimeError(
        "knowledge_search cannot be invoked synchronously inside an active event loop"
    )


def _sanitize_json_value(value: Any) -> Any:
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {key: _sanitize_json_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_sanitize_json_value(item) for item in value]
    return value


@tool
def graph_traverse(entity_name: str) -> str:
    """
    Retrieve relationships for a given entity from the knowledge graph up to 2 hops.
    Use this to traverse the dependencies, pipeline flows, or ownership of services/components.
    Always call this tool first when investigating a specific entity, service, pipeline, project, or object,
    before using `knowledge_search` to find detailed documentation.
    Returns entity details and serialized triples in the format (A) --[predicate]--> (B).
    """
    store = GraphStore()
    subg = store.get_subgraph(entity_name, hops=2)
    if not subg or not subg["nodes"]:
        all_nodes = list(store.graph.nodes)
        matches = [
            n for n in all_nodes if n.lower().strip() == entity_name.lower().strip()
        ]
        if matches:
            subg = store.get_subgraph(matches[0], hops=2)
        else:
            return f"Entity '{entity_name}' not found in the knowledge graph."

    node_descriptions = [
        f"- {n['id']} [{n['type']}]{' (' + n['description'] + ')' if n.get('description') else ''}"
        for n in subg["nodes"]
    ]
    triples = [
        f"  ({e['source']}) --[{e['predicate']}]--> ({e['target']})"
        for e in subg["edges"]
    ]
    result = (
        f"Subgraph for '{entity_name}' (up to 2 hops):\n\n"
        "Entities involved:\n" + "\n".join(node_descriptions) + "\n\n"
        "Relationships:\n"
        + ("\n".join(triples) if triples else "  No relations found.")
    )
    register_retrieval([result])
    return result


@tool
def uploaded_file_context(query: str = "", upload_id: str = "") -> str:
    """
    Retrieve context extracted from files uploaded by the Chainlit user in the current chat session.

    USE WHEN: the user asks about, summarizes, analyzes, compares, or extracts facts from an uploaded file.
    Supports table uploads parsed by pandas (CSV/XLSX/XLSM) and document uploads converted to Markdown
    with MarkItDown. Returns session-scoped metadata, table schema/sample rows, preview text,
    and processed paths.
    """
    from app.services.upload_artifacts import build_session_upload_context

    session_id = get_current_upload_session()
    if not session_id:
        return "No active chat session is available for uploaded file lookup."
    upload_ids = [upload_id] if upload_id else None
    result = build_session_upload_context(
        session_id, upload_ids=upload_ids, query=query
    )
    if not result:
        return "No processed uploaded files were found for this chat session."
    register_retrieval([result])
    return result
