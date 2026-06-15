import os
import re
import json
import datetime
import threading
import uuid
from typing import List, Dict, Any
from langchain.tools import tool
from rank_bm25 import BM25Okapi
from qdrant_client import QdrantClient

from app.core.redis import get_redis_client
from app.services.embedding import get_embedding_service
from app.services.graph_store import GraphStore

@tool
def get_current_time():
    """Get the current time in the system. Use this whenever you are asked about the current time."""
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def tokenize(text: str) -> List[str]:
    """Tokenize raw text into alphanumeric word components (lowercase)."""
    return re.findall(r'\w+', text.lower())

def get_wiki_docs() -> Dict[str, str]:
    """Retrieves wiki pages content, caching in Redis for rapid FTS querying."""
    r = get_redis_client()
    try:
        cached = r.get("wiki:cache")
        if cached:
            return json.loads(cached)
    except Exception as e:
        print(f"Redis cache read error: {e}")

    docs = {}
    wiki_dir = "wiki"
    if os.path.exists(wiki_dir):
        for root, _, files in os.walk(wiki_dir):
            for file in files:
                # Exclude administrative files
                if file.endswith(".md") and file not in ("log.md", "index.md"):
                    file_path = os.path.join(root, file)
                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            docs[file_path] = f.read()
                    except Exception:
                        pass
    try:
        r.setex("wiki:cache", 3600, json.dumps(docs))
    except Exception as e:
        print(f"Redis cache write error: {e}")
    return docs

@tool
def wiki_search(query: str) -> str:
    """
    Search across the compiled wiki pages using hybrid search (BM25 full-text + Qdrant vector cosine similarity).
    Use this when the user asks questions that require matching terms or reading documentation contents.
    Returns the top 5 relevant snippets with their file paths.
    """
    docs = get_wiki_docs()
    if not docs:
        return "No wiki pages found."

    # 1. BM25 Search
    doc_paths = list(docs.keys())
    doc_contents = list(docs.values())
    tokenized_corpus = [tokenize(doc) for doc in doc_contents]
    
    bm25 = BM25Okapi(tokenized_corpus)
    tokenized_query = tokenize(query)
    bm25_scores = bm25.get_scores(tokenized_query)
    
    # Sort by BM25 score
    bm25_ranked = sorted(zip(doc_paths, bm25_scores), key=lambda x: x[1], reverse=True)
    bm25_ranking = [path for path, score in bm25_ranked if score > 0]

    # 2. Qdrant Vector Search
    qdrant_ranking = []
    qdrant_url = os.getenv("QDRANT_URL")
    qdrant_key = os.getenv("QDRANT_API_KEY")
    if qdrant_url and qdrant_key:
        try:
            client = QdrantClient(url=qdrant_url, api_key=qdrant_key)
            embed_service = get_embedding_service()
            query_vector = embed_service.embed_text(query)
            
            res = client.search(
                collection_name="wiki_pages",
                query_vector=query_vector,
                limit=10
            )
            qdrant_ranking = [hit.payload["path"] for hit in res if hit.payload and "path" in hit.payload]
        except Exception as e:
            print(f"Qdrant vector search error: {e}")

    # 3. Reciprocal Rank Fusion (RRF)
    # k = 60
    rrf_scores = {}
    
    def add_ranking(ranking):
        for rank, path in enumerate(ranking):
            norm_path = os.path.normpath(path)
            rrf_scores[norm_path] = rrf_scores.get(norm_path, 0.0) + 1.0 / (60.0 + (rank + 1))

    normalized_doc_paths = {os.path.normpath(p): p for p in doc_paths}
    
    add_ranking(bm25_ranking)
    add_ranking(qdrant_ranking)

    # Sort candidates by RRF score
    sorted_candidates = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)[:5]

    if not sorted_candidates:
        sorted_candidates = [(os.path.normpath(path), 0.0) for path, _ in bm25_ranked[:5]]

    results = []
    for rank, (norm_path, score) in enumerate(sorted_candidates):
        orig_path = normalized_doc_paths.get(norm_path)
        if not orig_path:
            continue
        content = docs[orig_path]
        
        # Extract snippet around query matches or beginning
        snippet = ""
        matches = list(re.finditer(re.escape(query), content, re.IGNORECASE))
        if matches:
            start = max(0, matches[0].start() - 100)
            end = min(len(content), matches[0].end() + 150)
            snippet = content[start:end].strip()
            if start > 0:
                snippet = "..." + snippet
            if end < len(content):
                snippet = snippet + "..."
        else:
            clean_content = content
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    clean_content = parts[2].strip()
            snippet = clean_content[:250].strip() + ("..." if len(clean_content) > 250 else "")
            
        results.append(
            f"Result {rank+1}:\n"
            f"Path: {orig_path}\n"
            f"Relevance Score (RRF): {score:.4f}\n"
            f"Snippet:\n{snippet}\n"
            f"---"
        )
        
    return "\n\n".join(results) if results else "No matches found."

@tool
def graph_traverse(entity_name: str) -> str:
    """
    Retrieve relationships for a given entity from the knowledge graph up to 2 hops.
    Use this to traverse the dependencies, pipeline flows, or ownership of services/components.
    Returns entity details and serialized triples in the format (A) --[predicate]--> (B).
    """
    store = GraphStore()
    
    # 2-hop neighborhood using the store's built-in get_subgraph
    subg = store.get_subgraph(entity_name, hops=2)
    if not subg or not subg["nodes"]:
        # Try a case-insensitive search in nodes
        all_nodes = list(store.graph.nodes)
        matches = [n for n in all_nodes if n.lower().strip() == entity_name.lower().strip()]
        if matches:
            subg = store.get_subgraph(matches[0], hops=2)
        else:
            return f"Entity '{entity_name}' not found in the knowledge graph."

    # Format nodes with descriptions
    node_descriptions = []
    for node in subg["nodes"]:
        desc = node.get("description", "")
        desc_str = f" ({desc})" if desc else ""
        node_descriptions.append(f"- {node['id']} [{node['type']}]{desc_str}")

    # Format edges as triples
    triples = []
    for edge in subg["edges"]:
        triples.append(f"  ({edge['source']}) --[{edge['predicate']}]--> ({edge['target']})")

    response = (
        f"Subgraph for '{entity_name}' (up to 2 hops):\n\n"
        f"Entities involved:\n" + "\n".join(node_descriptions) + "\n\n"
        f"Relationships:\n" + ("\n".join(triples) if triples else "  No relations found.")
    )
    return response

def _run_ingest_async(task_id: str, source: str, path_or_repo: str):
    r = get_redis_client()
    task_key = f"ingest:task:{task_id}"
    try:
        from ingest import run_ingest_pipeline
        
        # Call the refactored ingestion pipeline function
        if source == "local":
            result = run_ingest_pipeline(source=source, dir_path=path_or_repo)
        elif source == "github":
            result = run_ingest_pipeline(source=source, repo_name=path_or_repo)
        else:
            raise ValueError(f"Unsupported source: {source}")
            
        task_data = {
            "status": "SUCCESS",
            "started_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "finished_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "error": None,
            "summary": result.get("summary", "Ingestion run finished.")
        }
        r.set(task_key, json.dumps(task_data))
    except Exception as e:
        task_data = {
            "status": "FAILED",
            "started_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "finished_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "error": str(e),
            "summary": "Ingestion failed with error."
        }
        r.set(task_key, json.dumps(task_data))

@tool
def ingest_source(source: str, path_or_repo: str) -> str:
    """
    Triggers an asynchronous ingestion run for a source.
    source: 'local' (requires directory path) or 'github' (requires 'owner/repo').
    path_or_repo: The directory path or github repo identifier.
    Returns a task ID that can be polled for status.
    """
    task_id = str(uuid.uuid4())
    task_key = f"ingest:task:{task_id}"
    
    r = get_redis_client()
    task_data = {
        "status": "PENDING",
        "started_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "finished_at": None,
        "error": None,
        "summary": "Task scheduled in background thread."
    }
    r.set(task_key, json.dumps(task_data))
    
    # Run the ingestion in a separate thread
    thread = threading.Thread(
        target=_run_ingest_async,
        args=(task_id, source, path_or_repo),
        daemon=True
    )
    thread.start()
    
    return f"Ingestion task scheduled successfully. Task ID: {task_id}. You can check status with the `/ingest/{task_id}` endpoint or let the user know."

@tool
def lint_wiki() -> str:
    """
    Audits the wiki pages for consistency, orphans, and conflict tags.
    Returns a markdown health audit report.
    """
    wiki_dir = "wiki"
    if not os.path.exists(wiki_dir):
        return "Wiki directory does not exist. No files to audit."

    pages = []
    for root, _, files in os.walk(wiki_dir):
        for file in files:
            if file.endswith(".md"):
                pages.append(os.path.join(root, file))

    conflict_pages = []
    incoming_links = {}
    outgoing_links = {}

    for page in pages:
        normalized_p = os.path.normpath(page)
        incoming_links[normalized_p] = []
        outgoing_links[normalized_p] = []

    # Read files to scan for references and conflicts
    for page in pages:
        normalized_page = os.path.normpath(page)
        try:
            with open(page, "r", encoding="utf-8") as f:
                content = f.read()
                
            # Scan for conflicts
            if "[CONFLICT]" in content:
                conflict_pages.append(page)
                
            # Scan for links [[page-slug]]
            links = re.findall(r'\[\[([^\]]+)\]\]', content)
            for link in links:
                # Link is usually title or slug (e.g. `auth-service` -> `wiki/services/auth-service.md`)
                slug = link.lower().strip().replace(" ", "-")
                # Look for matching target file
                found = False
                for p in pages:
                    p_name = os.path.splitext(os.path.basename(p))[0]
                    if p_name == slug:
                        target = os.path.normpath(p)
                        outgoing_links[normalized_page].append(target)
                        if target in incoming_links:
                            incoming_links[target].append(normalized_page)
                        found = True
                        break
        except Exception:
            pass

    # Find orphan pages (pages with 0 incoming links, excluding index.md and log.md)
    orphan_pages = []
    for page in pages:
        norm_p = os.path.normpath(page)
        base = os.path.basename(page)
        if base in ("index.md", "log.md"):
            continue
        if len(incoming_links[norm_p]) == 0:
            orphan_pages.append(page)

    # Compile report
    report = [
        "# Wiki Health Audit Report",
        f"Date: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"Total Wiki Pages Audited: {len(pages)}",
        ""
    ]

    report.append("## Conflict Tags")
    if conflict_pages:
        report.append("The following pages contain active `[CONFLICT]` tags that require manual resolution:")
        for cp in conflict_pages:
            report.append(f"- [{os.path.basename(cp)}](file://{os.path.abspath(cp)})")
    else:
        report.append("✅ No pages with active `[CONFLICT]` tags found.")
    report.append("")

    report.append("## Orphan Pages")
    if orphan_pages:
        report.append("The following pages are not linked from any other page in the wiki:")
        for op in orphan_pages:
            report.append(f"- [{os.path.basename(op)}](file://{os.path.abspath(op)})")
    else:
        report.append("✅ No orphan pages found.")
    report.append("")

    return "\n".join(report)

@tool
def sync_knowledge_base() -> str:
    """
    Manually triggers a full synchronization of the local knowledge base (raw/local directory).
    Use this when the user asks to sync, update, or refresh the knowledge base manually.
    Returns a task ID that can be polled for status.
    """
    task_id = str(uuid.uuid4())
    task_key = f"ingest:task:{task_id}"
    
    r = get_redis_client()
    task_data = {
        "status": "PENDING",
        "started_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "finished_at": None,
        "error": None,
        "summary": "Manual knowledge base sync scheduled in background thread."
    }
    r.set(task_key, json.dumps(task_data))
    
    # Run the ingestion in a separate thread
    thread = threading.Thread(
        target=_run_ingest_async,
        args=(task_id, "local", "raw/local"),
        daemon=True
    )
    thread.start()
    
    return f"Manual knowledge base synchronization started. Task ID: {task_id}. You can track status with this ID."


@tool
def mongodb_query(collection: str, filter_json: str, projection_json: str = None, limit: int = 100) -> str:
    """
    Query structured company data from MongoDB. Use this when you need exact facts about employees, 
    projects, bug tracking, KPIs, or organizational charts.
    
    Available Collections & Schemas:
    1. 'employees': Information about staff.
       - Fields: id, full_name, gender, date_of_birth, department, position, level, email, phone, start_date, employment_type, status, manager_id, office, avatar
    2. 'projects': Technical and business projects.
       - Fields: id, name, code, description, type, status, phase, priority, start_date, deadline, budget_vnd, spent_vnd, progress_percent, tech_stack (list), team (dict with pm, tech_lead, members), milestones (list), risks (list), kpi (dict)
    3. 'bug_tracker': Reported software/system bugs.
       - Fields: id, title, description, project_code, severity, priority, status, reporter_id, assignee_id, created_at, closed_at, resolution
    4. 'kpi_okr': Department objectives and key results.
       - Fields: id, department, year, quarter, objective, key_results (list with name, target, current, status, owner_id)
    5. 'org_chart': Reporting relations and structures.
       - Fields: id, employee_id, role, reports_to (id), team_size
       
    Args:
        collection (str): One of the collections above ('employees', 'projects', 'bug_tracker', 'kpi_okr', 'org_chart').
        filter_json (str): A valid JSON string representing the MongoDB query filter (e.g. '{"department": "Kỹ thuật"}').
        projection_json (str, optional): A JSON string representing the projection fields to include/exclude.
        limit (int, optional): Maximum number of documents to return. Defaults to 100. Max is 1000.
    """
    import json
    # Restrict limit to avoid token blow-up, but allow up to 1000 for full-collection queries
    limit = min(max(1, limit), 1000)
    
    try:
        mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
        from pymongo import MongoClient
        client = MongoClient(mongo_uri)
        db = client["personal_knowledge_ai"]
        
        if collection not in ['employees', 'projects', 'bug_tracker', 'kpi_okr', 'org_chart']:
            return f"Error: Collection '{collection}' is invalid. Allowed collections: employees, projects, bug_tracker, kpi_okr, org_chart."
            
        col = db[collection]
        
        # Parse query parameters
        query_dict = json.loads(filter_json) if filter_json else {}
        proj_dict = json.loads(projection_json) if projection_json else None
        
        results = list(col.find(query_dict, proj_dict).limit(limit))
        
        # Serialize ObjectIds/dates for JSON output
        for r in results:
            if "_id" in r:
                r["_id"] = str(r["_id"])
                
        if not results:
            return f"No records found in collection '{collection}' matching query: {filter_json}"
            
        return json.dumps(results, ensure_ascii=False, indent=2)
        
    except json.JSONDecodeError as je:
        return f"JSON Syntax Error: Ensure filter_json and projection_json are valid JSON strings. Details: {je}"
    except Exception as e:
        return f"Error querying MongoDB: {e}"


