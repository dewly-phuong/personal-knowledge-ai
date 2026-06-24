"""
Knowledge-base search tools: wiki_search, entity_search, graph_traverse,
uploaded_file_context.
"""

from langchain_core.tools import tool

from app.services.wiki_search import WikiSearchService
from app.services.graph_store import GraphStore
from app.tools.retrieval_context import register_retrieval, get_current_upload_session

_wiki = WikiSearchService()


@tool
def wiki_search(query: str) -> str:
    """
    Hybrid BM25 + vector search over compiled wiki pages.

    USE WHEN: general questions about policy, process, or concepts with NO specific named entity.
    Examples: "How does the leave approval process work?", "What is the deployment policy?"

    DO NOT USE when a specific named entity is involved — use entity_search instead.
    DO NOT USE for exact numbers or statistics — use mongodb_query instead.

    Returns the top 5 relevant snippets with their file paths.
    """
    result = _wiki.search(query)
    chunks = [c.strip() for c in result.split("\n\n") if c.strip()]
    register_retrieval(chunks)
    return result


@tool
def entity_search(entity_name: str, query: str) -> str:
    """
    Combined lookup for a SPECIFIC NAMED ENTITY (service, project, person, pipeline, team, system).
    Performs graph relationship extraction + wiki search in one call for higher recall.

    USE WHEN: the question names a specific internal entity.
    Examples: "What does AuthService do?", "Who owns DataPipeline?", "Tell me about project X."

    DO NOT USE for general questions without a specific named entity — use wiki_search instead.
    DO NOT USE for exact numbers or statistics — use mongodb_query instead.

    Returns a graph relationship summary followed by relevant wiki snippets.
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

    if subg_1hop and subg_1hop["nodes"]:
        edge_lines = [
            f"{e['source']} --[{e['predicate']}]--> {e['target']}"
            for e in subg_1hop["edges"]
        ]
        graph_context = f"Relations for '{canonical}': " + (
            " | ".join(edge_lines) if edge_lines else "no direct relations"
        )
        neighbor_names = [n["id"] for n in subg_2hop["nodes"] if n["id"] != canonical]
        expanded_query = f"{query} {canonical} {' '.join(neighbor_names[:10])}"
    else:
        graph_context = f"'{entity_name}' not found in knowledge graph."
        expanded_query = f"{query} {entity_name}"

    search_results = _wiki.search(expanded_query)
    register_retrieval([graph_context, search_results])
    return f"[Graph] {graph_context}\n\n[Wiki]\n{search_results}"


@tool
def graph_traverse(entity_name: str) -> str:
    """
    Retrieve relationships for a given entity from the knowledge graph up to 2 hops.
    Use this to traverse the dependencies, pipeline flows, or ownership of services/components.
    Always call this tool first when investigating a specific entity, service, pipeline, project, or object,
    before using `wiki_search` to find detailed documentation.
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
