# Personal Knowledge AI Assistant

An internal knowledge-graph-powered AI assistant for Vietnamese-language enterprise use. It ingests documents from multiple sources (local files, GitHub, Confluence), builds a compiled wiki and a NetworkX knowledge graph, and exposes a Chainlit chat UI backed by a Gemini 2.5 Pro agent.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Layer 1 — Raw Sources                                       │
│  Local files · GitHub repos · Confluence spaces             │
│  Office/PDF (auto-converted to Markdown via MarkItDown)     │
└────────────────────────┬────────────────────────────────────┘
                         │ ingest.py
┌────────────────────────▼────────────────────────────────────┐
│  Layer 2 — Knowledge Store                                   │
│  • Entity extraction  (gemini-2.5-flash)                     │
│  • Entity resolution  (gemini-2.5-pro)                       │
│  • Compiled wiki      wiki/*.md  (markdown pages)           │
│  • Knowledge graph    graph/graph.pkl  (NetworkX)           │
│  • Vector index       Qdrant Cloud  (768-dim embeddings)    │
│  • Structured data    MongoDB  (JSON / CSV / XLSX)          │
└────────────────────────┬────────────────────────────────────┘
                         │ main.py (FastAPI + LangChain agent)
┌────────────────────────▼────────────────────────────────────┐
│  Layer 3 — Agent & UI                                        │
│  • Gemini 2.5 Pro agent with universal knowledge search     │
│  • Real-time SSE streaming via FastAPI                      │
│  • Chainlit chat UI  →  /chat                               │
│  • Redis: session cache · cost stats · ingest task status   │
│  • MongoDB: chat history · Chainlit persistence             │
└─────────────────────────────────────────────────────────────┘
```

### Key modules

| Path | Responsibility |
|---|---|
| `main.py` | FastAPI app, lifespan, SSE route, API routes |
| `app.py` | Chainlit event handlers and UI streaming |
| `ingest.py` | Ingestion CLI and pipeline orchestration |
| `app/agent.py` | LangChain agent factory (Gemini + tools) |
| `app/tools/` | LangChain tools — universal knowledge search, diagnostic tools, charts… |
| `app/retrieval/` | Source registry and adapters for wiki, graph, MongoDB, uploads, and future sources |
| `app/services/wiki_search.py` | `WikiSearchService` — BM25 + Qdrant hybrid search |
| `app/services/cost_tracker.py` | `CostTracker` — per-call cost accounting in Redis |
| `app/services/graph_store.py` | `GraphStore` singleton wrapping NetworkX `MultiDiGraph` |
| `app/services/compiler.py` | `WikiCompiler` — LLM-powered wiki page generation |
| `app/services/extractor.py` | `GraphExtractor` — entity + relation extraction |
| `app/services/resolver.py` | `EntityResolver` — canonical entity clustering |
| `app/services/embedding.py` | `GeminiEmbeddingService` / `ModernBERTEmbeddingService` factory |
| `app/services/qdrant_sync.py` | `QdrantSyncManager` — upserts wiki pages to Qdrant |
| `app/services/mongodb_import.py` | JSON / CSV / XLSX importers with hash-based dedup |
| `app/services/markitdown_converter.py` | Office/PDF → Markdown conversion |
| `app/services/connectors/` | `BaseConnector` + Local / GitHub / Confluence implementations |
| `app/memory/session_store.py` | Redis-primary / MongoDB-fallback chat history store |
| `app/memory/history_manager.py` | Facade over `SessionStore` used by the API layer |
| `app/memory/mongodb_data_layer.py` | Chainlit `BaseDataLayer` backed by MongoDB |
| `app/core/redis.py` | Singleton Redis client |

---

## Quickstart

### 1. Prerequisites

```bash
# Redis (session cache, cost stats, ingest task status)
docker run -d --name redis-local -p 6379:6379 redis

# MongoDB (chat history, structured data, Chainlit persistence)
docker run -d --name mongo-local -p 27017:27017 mongo
```

### 2. Environment variables

Create `.env` at the project root:

```bash
GOOGLE_API_KEY="AIzaSy..."
CHAINLIT_AUTH_SECRET="your-secret"
MONGO_URI="mongodb://localhost:27017/"
REDIS_HOST="localhost"
REDIS_PORT="6379"

# Optional — Qdrant vector search
QDRANT_URL="https://your-cluster.qdrant.io"
QDRANT_API_KEY="your-qdrant-key"

# Optional — GitHub ingestion
GITHUB_TOKEN="your-github-token"

# Optional — Confluence ingestion
CONFLUENCE_URL="https://your-domain.atlassian.net"
CONFLUENCE_USERNAME="user@domain.com"
CONFLUENCE_API_TOKEN="your-confluence-token"
```

### 3. Start the server

```bash
source .venv/bin/activate
uvicorn main:app --port 8000
```

- **FastAPI API:** `http://localhost:8000`
- **Chainlit UI:** `http://localhost:8000/chat` (login: `admin` / `admin`)

---

## Ingestion

The ingestion pipeline runs incrementally — only new or changed files are processed.

```bash
# Local files (also imports JSON/CSV/XLSX into MongoDB)
python ingest.py --source local --dir raw/local

# Office/PDF files (converted to Markdown first, then ingested)
python ingest.py --source office --dir raw/local

# GitHub repository (README.md + docs/*.md)
python ingest.py --source github --repo owner/repo

# Confluence space
python ingest.py --source confluence --space SPACE_KEY
```

A daily background job automatically re-runs local ingestion and a wiki health audit at server startup (every 24 hours).

---

## Agent Tools

| Tool | When to use |
|---|---|
| `knowledge_search` | Searches every configured knowledge source in parallel and returns normalized per-source `ok` / `empty` / `error` results |
| `generate_chart` | Render pie/bar/line charts from aggregated data |

Diagnostic and maintenance tools such as `graph_traverse`, `mongodb_query`, `ingest_source`, `sync_knowledge_base`, and `lint_wiki` remain exported for tests, manual debugging, and API helpers, but the active chat agent routes factual retrieval through `knowledge_search`.

---

## API Reference

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/chat` | SSE stream — agent response with tool steps |
| `GET` | `/api/chat/{session_id}` | Retrieve chat history for a session |
| `DELETE` | `/api/chat/{session_id}` | Clear chat history for a session |
| `POST` | `/api/chat/{session_id}/sync` | Overwrite chat history (used on resume) |
| `POST` | `/api/ingest` | Trigger background ingestion |
| `GET` | `/api/ingest/{task_id}` | Poll ingestion task status |
| `GET` | `/api/uploads` | List uploaded files retained as chat-session context |
| `GET` | `/api/uploads/{upload_id}` | Inspect one uploaded file context artifact |
| `GET` | `/api/graph/{entity}` | 2-hop subgraph for an entity (JSON) |
| `GET` | `/api/cost` | Accumulated LLM cost stats (today + month) |
| `GET` | `/api/health` | Redis + MongoDB connectivity check |

---

## Chainlit File Uploads

Files uploaded in Chainlit are processed only for the active chat session:

- CSV/XLSX/XLSM files are parsed with Pandas, summarized to Markdown, and exported to `csv/*.csv`.
- Other files are converted to Markdown with MarkItDown when needed.
- Processed Markdown is split into overlapping session chunks and stored as `chunks.json` beside the artifact.
- When a user asks about an upload, the `uploads` source ranks matching chunks for the query before adding bounded context to `knowledge_search`.
- Processed files are stored under `uploads/sessions/{session_id}/{upload_id}`.
- Metadata is saved in MongoDB collection `uploaded_artifacts`, including schema/sample rows, descriptions, processed paths, chunk counts, retrieval mode, and context character counts.
- The agent searches uploaded file context through the `uploads` source inside `knowledge_search`.
- Re-uploading the same file in one session reuses the existing processed artifact by SHA-256 hash instead of converting it again.
- Uploaded files are searchable through the upload retrieval source; they are not ingested into the permanent wiki, graph, vector store, or MongoDB knowledge collections.
- Image uploads currently retain metadata only. They are not OCRed, rendered into PDF page images, or sent to the LLM as multimodal image bytes in this flow.

Debug flow:

```bash
# List uploaded session artifacts
curl http://localhost:8000/api/uploads

# Inspect one upload
curl http://localhost:8000/api/uploads/{upload_id}
```

---

## Health Audit (Wiki Lint)

```bash
python -c "from app.tools import lint_wiki; print(lint_wiki.invoke({}))"
```

The report is also automatically saved to `wiki/health_report.md` after each daily sync.

---

## Debugging the Knowledge Graph

```python
import pickle

with open("graph/graph.pkl", "rb") as f:
    g = pickle.load(f)

# Inspect nodes
for node, data in g.nodes(data=True):
    print(f"  {node} ({data.get('type')}) - {data.get('description')}")

# Inspect edges
for u, v, key, data in g.edges(keys=True, data=True):
    print(f"  ({u}) --[{data.get('predicate')}]--> ({v})")
```

```python
# Manually add or remove relationships
from app.services.graph_store import GraphStore

store = GraphStore()
store.graph.add_edge("auth-service", "user-db", predicate="depends on")
store.save()
```

---

## Adding a New Connector

1. Create `app/services/connectors/my_source.py` implementing `BaseConnector.fetch_documents()`.
2. Export it in `app/services/connectors/__init__.py`.
3. Add a branch in `ingest.py::_build_connector()` for the new source name.
4. Add the source name to the `--source` choices in `ingest.py::main()`.

```python
# app/services/connectors/my_source.py
from app.services.connectors.base import BaseConnector, Document

class MySourceConnector(BaseConnector):
    def __init__(self, token: str):
        self.token = token

    def fetch_documents(self) -> list[Document]:
        # fetch and return Document objects
        return []
```
