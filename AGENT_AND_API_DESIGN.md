# Agent and API Architecture: LangChain Tools + FastAPI + Redis

## Understanding Summary
* **What is being built**: Sprint 3:
  * LangChain tools: `wiki_search` (hybrid BM25 + Qdrant search), `graph_traverse` (2-hop subgraph), `ingest_source` (trigger pipeline), and `lint_wiki` (audit).
  * Conversational Agent: LangChain agent using `gemini-2.5-pro` with tool-calling.
  * FastAPI Server: Endpoints for `/chat` (streaming response), `/ingest` & `/ingest/{task_id}` (background task tracking), and `/graph/{entity}` (subgraph payload).
  * Chainlit integration: Update `app.py` to stream responses from the FastAPI `/chat` endpoint.
  * Test Suite: A multi-hop query quality check.
* **Why it exists**: To enable multi-hop questioning with citations, exposing the graph and wiki search to client UIs.
* **Who it is for**: Developers and users of the Chainlit chat UI.
* **Key constraints**:
  * Use the `rank-bm25` package for full-text search.
  * Use `gemini-2.5-pro` for agent reasoning.
  * Vector space dimensions must be 768 to match the existing collection.
  * Pre-load `graph.pkl` into memory during the FastAPI `lifespan` startup event.
  * Use Redis (`localhost:6379`) to cache wiki pages and track background task statuses.

## Assumptions
1. **Redis Availability**: A Redis instance is running at `localhost:6379` (standard port).
2. **Dimension Compatibility**: Vector space dimensions will remain 768.

## Decision Log
1. **FTS Library**: Selected `rank-bm25` (BM25Okapi) for the full-text search component.
2. **LLM Model**: Selected `gemini-2.5-pro` for multi-hop agent reasoning.
3. **Caching & Task Tracking**: Use Redis (`localhost:6379`) to cache wiki pages and track background task statuses.
4. **Pre-loading Graph Store**: Pre-load `graph/graph.pkl` on FastAPI startup (using `lifespan` context manager) to avoid file I/O overhead during queries.
5. **Streaming Integration**: FastAPI will expose a `/chat` stream, and Chainlit (`app.py`) will consume it using `httpx.AsyncClient` to stream tokens to the user interface.

## Final Design

### 1. Global Singleton / Lifespan Graph Loading
We will load `graph.pkl` inside `main.py` using FastAPI's `lifespan` event and make it accessible globally via `app.state.graph_store`.
```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.services.graph_store import GraphStore

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load graph store
    app.state.graph_store = GraphStore()
    yield
```

### 2. Redis Cache & Ingestion Status
* Redis keys:
  * `wiki:cache` - hash map of file paths to document content.
  * `ingest:task:{task_id}` - JSON object with status, started_at, finished_at, error, and summary.

### 3. LangChain Tools
* `wiki_search`:
  * Computes BM25 scores for cached wiki pages.
  * Queries Qdrant Cloud via the embedding service.
  * Merges rankings using Reciprocal Rank Fusion (RRF).
* `graph_traverse`:
  * Traverses the pre-loaded `graph_store.graph` up to 2 hops.
  * Formats relationships as `(A) --[predicate]--> (B)`.
* `ingest_source`:
  * Launches ingestion in a background thread and returns the `task_id` for tracking.
* `lint_wiki`:
  * Performs clean audits of `wiki/` files for conflicts or orphans.

### 4. FastAPI & Chainlit API Endpoints
* `POST /chat`: Streams response text using SSE or raw streaming.
* `POST /ingest` & `GET /ingest/{task_id}`: Tracks async ingestion runs.
* `GET /graph/{entity}`: Serves D3.js-ready JSON.
