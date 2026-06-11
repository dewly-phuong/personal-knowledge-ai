# Personal Knowledge AI Assistant — Onboarding & Operations Guide

Welcome to the Personal Knowledge AI Assistant team. This guide covers how to set up, operate, debug, and extend the Knowledge Graph agent.

---

## 🏗️ System Architecture

The project implements a **Dual-Model LLM Wiki Pattern**:
1.  **Layer 1 (Raw Sources):** Immutable documentation files pulled from GitHub, Confluence, or local directories.
2.  **Layer 2 (Compiled Wiki + Graph):** Raw text is extracted (entities & relations using `gemini-2.0-flash`), resolved into canonical names (using `gemini-2.5-pro`), compiled into interlinked markdown pages in `wiki/`, and stored in a NetworkX knowledge graph (`graph/graph.pkl`).
3.  **Layer 3 (Agent & UI):** A LangChain conversational agent (`gemini-2.5-pro`) uses tools to query the compiled wiki (hybrid BM25 + Qdrant search) and traverse the graph to answer multi-hop user queries inside a Chainlit UI.

---

## ⚡ Quickstart

### 1. Prerequisite: Local Services
Ensure Redis is running locally on port `6379` (used for cache invalidation, background ingestion task status tracking, and LLM cost monitoring):
```bash
docker run -d --name redis-local -p 6379:6379 redis
```

### 2. Configure Environment Variables
Create a `.env` file at the project root based on `.env.example`:
```bash
GOOGLE_API_KEY="AIzaSy..."
CHAINLIT_AUTH_SECRET="your-generated-secret"
QDRANT_URL="https://your-qdrant-cluster.io"
QDRANT_API_KEY="your-qdrant-key"
GITHUB_TOKEN="your-github-token"
CONFLUENCE_URL="https://your-domain.atlassian.net"
CONFLUENCE_USERNAME="user@domain.com"
CONFLUENCE_API_TOKEN="your-confluence-token"
```

### 3. Startup the Server
The FastAPI backend and Chainlit UI run together in a unified process:
```bash
# Activate the virtual environment
source .venv/bin/activate

# Start uvicorn
uvicorn main:app --port 8000
```
*   **FastAPI API Endpoints:** `http://127.0.0.1:8000`
*   **Chainlit Chat UI:** `http://127.0.0.1:8000/chat` (Login: `admin` / `admin`)

---

## 📥 Manual Ingestion

You can trigger the ingestion pipeline manually via the `ingest.py` CLI tool. It tracks modified times and performs incremental updates.

### A. Local Files Ingestion
To index files from `raw/local`:
```bash
python ingest.py --source local --dir raw/local
```

### B. GitHub Repository Ingestion
To index a repository's markdown files (requires `GITHUB_TOKEN` in `.env`):
```bash
python ingest.py --source github --repo owner/repo
```

### C. Confluence Ingestion
To index pages from a Confluence Space (requires Confluence configuration in `.env`):
```bash
python ingest.py --source confluence --space SPACE_KEY
```

---

## 🩺 Health Auditing (Linting)

To check the consistency and health of the compiled Wiki (identifying orphan pages, missing backlinks, `[CONFLICT]` tags, or stale content):

1.  **Scheduled Linting:** The system automatically runs a sync and health audit once every 24 hours via a background scheduler.
2.  **Manual Execution:** Run the lint tool from your python environment:
    ```bash
    python -c "from app.tools import lint_wiki; print(lint_wiki.invoke({}))"
    ```
    This will compile a report and output the current Wiki Health Score. The report is automatically saved to `wiki/health_report.md`.

---

## 🛠️ Debugging Graph Traversal

If the agent returns incorrect service dependencies or relationship mappings, you can inspect and modify the NetworkX MultiDiGraph manually.

The graph is persisted as a serialized pickle file at `graph/graph.pkl`.

### Inspecting the Graph
Use the following Python snippet to view the nodes and edges:
```python
import pickle

with open("graph/graph.pkl", "rb") as f:
    graph = pickle.load(f)

print("Nodes in Graph:")
for node, data in graph.nodes(data=True):
    print(f"  {node} ({data.get('type')}) - {data.get('description')}")

print("\nEdges (Relationships):")
for u, v, key, data in graph.edges(keys=True, data=True):
    print(f"  ({u}) --[{data.get('predicate')}]--> ({v})")
```

### Manually Adding or Modifying a Relationship
If the resolver incorrectly clustered an entity or missed a dependency, you can modify `graph.pkl` programmatically:
```python
import pickle
from app.services.graph_store import GraphStore

store = GraphStore()

# Manually add an edge (relationship)
store.graph.add_edge("auth-service", "user-db", predicate="depends on")

# Manually remove an incorrect edge
if store.graph.has_edge("auth-service", "payment-service"):
    store.graph.remove_edge("auth-service", "payment-service")

# Save changes back to graph.pkl
store.save()
```

---

## 🔌 How to Add a New Connector

All document connectors inherit from `BaseConnector` defined in `app/services/connectors/base.py`.

### 1. Implement the Connector Class
Create a new file (e.g., `app/services/connectors/notion.py`) and implement the abstract `fetch_documents()` method:

```python
import os
from app.services.connectors.base import BaseConnector, Document

class NotionConnector(BaseConnector):
    def __init__(self, token: str, page_id: str):
        self.token = token
        self.page_id = page_id

    def fetch_documents(self) -> list[Document]:
        documents = []
        # 1. Fetch data from Notion API using self.token and self.page_id
        # 2. Map the results into Document models:
        # doc = Document(
        #     content="Page text content here...",
        #     source_url="https://notion.so/page-url",
        #     path="notion/page_title.md",
        #     source_type="local",  # or map dynamically
        #     last_modified="2026-06-11T12:00:00Z"
        # )
        # documents.append(doc)
        return documents
```

### 2. Register in the Ingestion Script
Open `ingest.py` and import your new connector:
```diff
from app.services.connectors import (
    LocalFilesConnector,
    GitHubConnector,
    ConfluenceConnector,
+   NotionConnector,
)
```

Add your source configuration under `run_ingest_pipeline()`:
```python
    elif source == "notion":
        token = os.getenv("NOTION_TOKEN")
        page_id = os.getenv("NOTION_PAGE_ID")
        if not token or not page_id:
            raise ValueError("NOTION_TOKEN and NOTION_PAGE_ID must be set.")
        connector = NotionConnector(token=token, page_id=page_id)
```
And add `"notion"` to the CLI parser arguments at the bottom of the script.
