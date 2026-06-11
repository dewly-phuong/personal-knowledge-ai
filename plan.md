# Internal Doc Q&A — Knowledge Graph Agent

> **Mục tiêu:** Build một agent chatbot cho phép team hỏi trực tiếp về docs nội bộ (Confluence, GitHub, Notion, Runbooks) bằng tiếng Việt, thay vì mò Confluence 20 phút. Dùng Knowledge Graph (LightRAG pattern) + LLM Wiki compilation thay cho traditional RAG.

---

## Architecture tổng quan

```
Layer 1 — Raw Sources (IMMUTABLE)
  GitHub README/docs  |  Confluence pages  |  Notion  |  Runbooks
         ↓ Gemini Flash extracts entities + relations
Layer 2 — Compiled Wiki + Knowledge Graph
  wiki/*.md (entity pages, concept pages, source summaries, index)
  knowledge_graph (NetworkX → Neo4j) — nodes=entities, edges=relations
         ↓ 3 operations: ingest · query · lint
Layer 3 — Agent + Interface
  LangChain Agent (wiki_search, graph_traverse, ingest_source, lint_wiki tools)
  FastAPI (/chat, /ingest, /graph)
  Chainlit UI
```

### Dual-model strategy
- **Gemini 2.0 Flash** (`gemini-2.0-flash`): entity extraction + wiki compilation — volume lớn, rẻ nhất, nhanh
- **Gemini 2.5 Pro** (`gemini-2.5-pro`): entity resolution, agent reasoning — cần nuance

### Key insight (Karpathy LLM Wiki pattern)
Thay vì re-read raw docs mỗi query, compile docs thành persistent wiki một lần:
- Raw sources = source code (immutable, ground truth)
- Wiki pages = compiled binary (pre-synthesized, interlinked)
- LLM = programmer (reads raw, writes wiki)
- Mỗi lần ingest: tạo ~10 interlinked pages + update existing pages + strengthen cross-links

---

## Tech stack

| Component | Tool | Ghi chú |
|---|---|---|
| LLM extraction | `gemini-2.0-flash` | Structured output via Pydantic + response_schema |
| LLM synthesis | `gemini-2.0-flash` | Wiki compilation — đủ dùng với schema rõ ràng |
| LLM agent reasoning | `gemini-2.5-pro` | Query time, user-facing — cần nuance |
| Embedding | `nomic-embed-text` via Ollama | Free, local, 768-dim, tốt cho tiếng Việt |
| Vector store | Qdrant Cloud (free tier) | 1GB free, managed, không cần ops |
| Graph store | NetworkX (dev) → Neo4j (prod) | MultiDiGraph |
| Graph RAG | LightRAG pattern | Không dùng Microsoft GraphRAG (quá đắt) |
| Agent framework | LangChain + LangGraph | Tool-calling agent |
| API | FastAPI + uvicorn | Async, streaming |
| Chat UI | Chainlit | Community-maintained từ 1/5/2025 — có backup plan |
| Scheduler | APScheduler hoặc cron | Incremental sync mỗi 6h |

> **Lưu ý Qdrant Cloud free tier:** 1GB storage, 1 cluster — đủ cho ~500 pages với nomic-embed (768-dim × 4 bytes × 500 = ~1.5MB, rất thoải mái). Upgrade khi corpus lớn hơn.

> **Lưu ý nomic-embed:** Cần Ollama chạy local (`ollama pull nomic-embed-text`). Nếu không muốn giữ Ollama server, fallback sang Gemini Embedding API (`text-embedding-004`) — rẻ và không cần infra local.

### Cấu trúc thư mục

```
project/
├── raw/                    # Layer 1 — immutable sources
│   ├── github/
│   ├── confluence/
│   ├── notion/
│   └── local/
├── wiki/                   # Layer 2 — compiled by LLM
│   ├── index.md
│   ├── log.md
│   ├── services/
│   ├── pipelines/
│   ├── concepts/
│   ├── decisions/
│   └── people/
├── graph/                  # Knowledge graph store
│   ├── graph.pkl           # NetworkX serialized
│   └── entities.json       # Canonical entity map
├── app/                    # Layer 3 — FastAPI + agent
│   ├── main.py             # FastAPI app
│   ├── agent.py            # LangChain agent setup
│   ├── tools/
│   │   ├── wiki_search.py
│   │   ├── graph_traverse.py
│   │   ├── ingest_source.py
│   │   └── lint_wiki.py
│   ├── ingestion/
│   │   ├── extractor.py    # Gemini Flash entity extraction
│   │   ├── resolver.py     # Gemini 2.5 Pro entity resolution
│   │   ├── compiler.py     # Gemini Flash wiki compilation
│   │   └── connectors/
│   │       ├── github.py
│   │       ├── confluence.py
│   │       ├── notion.py
│   │       └── local_files.py
│   └── db/
│       ├── vector_store.py # Qdrant Cloud operations
│       └── graph_store.py  # NetworkX operations
├── chainlit_app.py         # Chainlit UI
├── WIKI_SCHEMA.md          # Schema cho agent đọc
├── plan.md                 # File này
├── pyproject.toml
└── .env.example
```

---

## WIKI_SCHEMA — định nghĩa page types

Agent phải đọc schema này trước khi thực hiện bất kỳ ingest nào.

### Page types

```
service/{name}.md
  - Mô tả: chức năng, owners, repo link
  - Dependencies: [[service-b]], [[database-x]]
  - Runbook: link
  - Known issues: [CONFLICT] nếu có mâu thuẫn với source khác

pipeline/{name}.md
  - Steps: numbered list
  - Trigger: cron/event
  - Failure modes + rollback procedure
  - Related services: [[service-a]]

concept/{name}.md
  - Định nghĩa kỹ thuật
  - Used by: [[service-a]], [[pipeline-b]]
  - Related: [[concept-x]]

decision/{YYYY-MM-DD}-{slug}.md
  - Context, problem statement
  - Options considered
  - Decision + rationale
  - Tradeoffs

person/{name}.md
  - Expertise areas
  - Owns: [[service-a]], [[pipeline-b]]
  - Recent decisions: [[decision/...]]
```

### Ingest rules
1. Mỗi lần ingest: update tối đa 15 pages hiện có + tạo pages mới nếu cần
2. Luôn thêm backlinks `[[page-name]]` vào pages liên quan
3. Flag contradictions: `[CONFLICT: source-a says X, source-b says Y]`
4. Mỗi page có front matter: `source_urls`, `last_updated`, `entities`
5. Không xóa pages — chỉ mark `[STALE]` nếu source đã bị xóa

---

## Pydantic schemas (extractor)

```python
from typing import Literal
from pydantic import BaseModel

EntityType = Literal["PERSON", "ORGANIZATION", "SERVICE", "PIPELINE", "CONCEPT", "ARTIFACT", "DATABASE"]

class Entity(BaseModel):
    name: str
    type: EntityType
    description: str  # 1 câu, dùng để disambiguate khi resolve

class Relation(BaseModel):
    source: str       # entity name
    predicate: str    # short verb phrase: "depends on", "owned by", "part of"
    target: str       # entity name

class ExtractedGraph(BaseModel):
    entities: list[Entity]
    relations: list[Relation]

class Cluster(BaseModel):
    canonical: str    # most complete, unambiguous form
    aliases: list[str]

class ResolvedClusters(BaseModel):
    clusters: list[Cluster]

class TimeRange(BaseModel):
    start: str        # YYYY hoặc "unknown"
    end: str          # YYYY hoặc "ongoing"

class EntityProfile(BaseModel):
    summary: str      # 2-3 đoạn
    key_facts: list[str]  # 3-5 atomic facts, traceable to sources
    time_range: TimeRange
```

---

## Gemini SDK — cách dùng structured output

```python
import google.generativeai as genai

genai.configure(api_key=GEMINI_API_KEY)

# Extraction với Gemini Flash
model = genai.GenerativeModel(
    model_name="gemini-2.0-flash",
    generation_config=genai.GenerationConfig(
        response_mime_type="application/json",
        response_schema=ExtractedGraph,
    )
)
response = model.generate_content(extraction_prompt)
result = ExtractedGraph.model_validate_json(response.text)

# Agent reasoning với Gemini 2.5 Pro
agent_model = genai.GenerativeModel(
    model_name="gemini-2.5-pro",
    tools=[wiki_search_tool, graph_traverse_tool, ingest_source_tool, lint_wiki_tool],
)
```

---

## Qdrant Cloud — setup và operations

```python
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

# Connect to Qdrant Cloud
client = QdrantClient(
    url=QDRANT_URL,      # https://<cluster-id>.us-east4-0.gcp.cloud.qdrant.io
    api_key=QDRANT_API_KEY,
)

# Create collection (một lần duy nhất)
client.create_collection(
    collection_name="wiki_pages",
    vectors_config=VectorParams(size=768, distance=Distance.COSINE),  # nomic-embed dim=768
)

# Upsert wiki page
client.upsert(
    collection_name="wiki_pages",
    points=[
        PointStruct(
            id=page_id,
            vector=embedding,  # từ nomic-embed-text
            payload={"path": path, "content": content, "entities": entities, "source_urls": urls}
        )
    ]
)

# Search
results = client.search(
    collection_name="wiki_pages",
    query_vector=query_embedding,
    limit=5,
    with_payload=True,
)
```

---

## nomic-embed — embedding pipeline

```python
import ollama

def embed(text: str) -> list[float]:
    """Embed text using nomic-embed-text via Ollama."""
    response = ollama.embeddings(model="nomic-embed-text", prompt=text)
    return response["embedding"]  # 768-dim vector

# Batch embed wiki pages
def embed_batch(texts: list[str]) -> list[list[float]]:
    return [embed(t) for t in texts]
```

> **Setup:** `ollama pull nomic-embed-text` — model ~274MB, chạy CPU được.
> **Fallback nếu không muốn Ollama:** dùng `gemini-embedding-004` via Gemini API.

---

## Prompts

### Extraction prompt (Gemini Flash)
```
Extract a knowledge graph from the document below.

<document>
{text}
</document>

Guidelines:
- Extract only entities that are central to what this document is about — skip incidental mentions.
- For each entity, write a one-sentence description grounded in this document.
  Descriptions are used later to disambiguate entities with similar names.
- Predicates should be short verb phrases ("depends on", "owned by", "deployed to").
- Every relation must connect two entities you extracted.
- For internal docs: SERVICE và PIPELINE entities quan trọng nhất.

Return valid JSON matching the ExtractedGraph schema.
```

### Resolution prompt (Gemini 2.5 Pro)
```
Below are {entity_type} entities extracted from several documents.
Some are different surface forms of the same real-world entity.

<entities>
{entity_list}
</entities>

Cluster them. Each input name must appear in exactly one cluster's aliases list.
Entities that are genuinely distinct get their own single-element cluster.
Use the descriptions to avoid merging entities that merely share a name.
The canonical name should be the most complete, unambiguous form.

Return valid JSON matching the ResolvedClusters schema.
```

### Wiki compilation prompt (Gemini Flash)
```
You are a disciplined wiki maintainer. Read the schema in WIKI_SCHEMA.md.

New document to ingest:
<document>
{text}
<source_url>{url}</source_url>
</document>

Existing wiki pages that may need updating:
<existing_pages>
{relevant_existing_pages}
</existing_pages>

Known entities in graph:
{entity_summary}

Tasks:
1. Write a source summary page at sources/{slug}.md
2. Create or update up to 15 entity/concept/pipeline/service pages
3. Add [[backlinks]] on all related pages
4. Flag any [CONFLICT] between this source and existing wiki content
5. Return list of all pages created/updated with their full content

Always include front matter:
---
source_urls: ["{url}"]
last_updated: "{date}"
entities: ["{entity1}", "{entity2}"]
---
```

### Agent system prompt (tiếng Việt)
```
Bạn là trợ lý nội bộ của team engineering. Bạn có quyền truy cập vào knowledge graph
và wiki pages tổng hợp từ toàn bộ docs nội bộ của team.

Luôn trả lời bằng tiếng Việt trừ khi user hỏi bằng tiếng Anh.

Quy trình trả lời:
1. Dùng wiki_search để tìm pages liên quan
2. Dùng graph_traverse để tìm connections nếu câu hỏi liên quan đến relationships
3. Tổng hợp answer từ wiki content — KHÔNG invent thông tin không có trong wiki
4. Cite sources theo format: [nguồn: wiki/services/service-a.md | Confluence: url]
5. Nếu không tìm thấy thông tin: nói thẳng "Tôi không tìm thấy thông tin này trong docs"

Khi user hỏi về:
- Service/system cụ thể → dùng graph_traverse để thấy full dependency tree
- "Ai phụ trách X" → traverse tới PERSON nodes
- "Tại sao team quyết định X" → search decision/ pages
- Câu hỏi mơ hồ → hỏi clarify trước khi search

Wiki schema: {wiki_schema_content}
```

---

## FastAPI endpoints

```python
# POST /chat
# Request:  {"query": str, "conversation_history": list[dict], "stream": bool}
# Response: StreamingResponse với {answer, steps, citations, graph_path}

# POST /ingest
# Request:  {"url": str} | multipart file upload
# Response: {"task_id": str}  → poll GET /ingest/{task_id}

# GET /ingest/{task_id}
# Response: {"status": "pending"|"running"|"done"|"error", "summary": str}

# GET /graph/{entity_name}
# Response: {"nodes": [{id, type, label, description}], "edges": [{source, target, predicate}]}

# POST /lint
# Response: {"orphans": [], "conflicts": [], "stale": [], "health_score": float}
```

---

## LangChain tools

```python
tools = [
    Tool(
        name="wiki_search",
        description="""Tìm kiếm trong wiki pages đã compile. Dùng khi cần thông tin
        về service, pipeline, concept, decision, hoặc người cụ thể.
        Input: câu hỏi hoặc từ khóa.
        Output: top-5 wiki pages với content snippet và source path.""",
        func=wiki_search,
    ),
    Tool(
        name="graph_traverse",
        description="""Traverse knowledge graph để tìm relationships.
        Dùng khi cần biết: dependencies, owners, connections giữa các entities.
        Input: tên entity (service, pipeline, person, ...).
        Output: 2-hop subgraph dạng triples "(A) --[predicate]--> (B)".""",
        func=graph_traverse,
    ),
    Tool(
        name="ingest_source",
        description="""Ingest tài liệu mới vào wiki và knowledge graph.
        Dùng khi user cung cấp URL hoặc file mới cần được index.
        Input: URL hoặc file path.
        Output: summary of wiki pages created/updated.""",
        func=ingest_source,
    ),
    Tool(
        name="lint_wiki",
        description="""Kiểm tra sức khỏe của wiki.
        Tìm: orphan pages, [CONFLICT] tags, stale pages, missing backlinks.
        Input: không cần (audit toàn bộ wiki).
        Output: health report với danh sách issues.""",
        func=lint_wiki,
    ),
]
```

---

## Sprint plan

### Sprint 1 — tuần 1: Foundation + Extraction Pipeline

**Mục tiêu:** Pipeline ingest hoạt động end-to-end cho GitHub README. Extraction quality F1 > 0.7.

| Task | Mô tả chi tiết | Effort | Tags |
|---|---|---|---|
| T01 | Setup project scaffold: repo, venv, pyproject.toml, cấu trúc thư mục raw/ wiki/ graph/ app/ | 1h | infra |
| T02 | Viết WIKI_SCHEMA.md: page types (service, pipeline, concept, decision, person), ingest rules, cross-link convention, [CONFLICT] tag | 2h | ai |
| T03 | GitHub connector: dùng PyGitHub, walk repo, lấy README + docs/\*.md, trả về list[Document(content, metadata)] với metadata {source_url, repo, path, last_modified} | 3h | infra |
| T04 | Pydantic schemas cho extraction: ExtractedGraph, Entity, Relation, EntityType enum (PERSON/ORG/SERVICE/PIPELINE/CONCEPT/ARTIFACT/DATABASE) | 1h | ai |
| T05 | Gemini Flash extractor: dùng `response_mime_type="application/json"` + `response_schema=ExtractedGraph`, system prompt focus vào SERVICE và PIPELINE entities | 3h | ai |
| T06 | Gemini 2.5 Pro entity resolver: cluster surface-form variants, block by type trước, build alias_to_canonical map, xử lý edge case tên giống nhau khác entity | 4h | ai |
| T07 | **[BLOCKER]** Test extraction quality: viết gold set 20 entities từ 2-3 README, chạy precision/recall, target F1 > 0.7 trước khi tiếp tục Sprint 2 | 2h | test |

**Definition of Done Sprint 1:** Chạy được `python ingest.py --source github --repo <url>` và nhận về entities + relations đúng.

---

### Sprint 2 — tuần 2: Compilation — Wiki + Graph Store

**Mục tiêu:** Từ extracted entities → wiki pages có backlinks + NetworkX graph connected.

| Task | Mô tả chi tiết | Effort | Tags |
|---|---|---|---|
| T08 | NetworkX graph store: assemble MultiDiGraph từ canonical entities + relations, node attrs (type, description, source_docs, mentions), edge attrs (predicate, source_doc) | 2h | infra |
| T09 | Gemini Flash wiki compiler: với mỗi doc, generate wiki pages theo WIKI_SCHEMA, output list[WikiPage(path, content, backlinks)] | 5h | ai |
| T10 | Wiki file writer: nhận list[WikiPage], ghi ra wiki/ directory, update index.md + log.md tự động, tạo wikilinks [[page-name]] đúng format | 2h | infra |
| T11 | Incremental update logic: track last_modified timestamp mỗi source, khi re-ingest chỉ update pages liên quan, không rebuild toàn bộ | 3h | infra |
| T12 | Qdrant Cloud setup: tạo collection wiki_pages (dim=768, cosine), embed wiki pages bằng nomic-embed-text, upsert với payload {path, content, entities, source_urls} | 3h | infra |
| T13 | Confluence connector: REST API v2, lấy spaces + pages, convert Confluence storage format (XML) → plain text, metadata {space, title, url, version, last_modified} | 4h | infra |
| T14 | **[CHECKPOINT]** Test ingest pipeline end-to-end: ingest 5-10 docs, kiểm tra graph connected, wiki pages có backlinks, index.md updated, không có orphan pages | 2h | test |

**Definition of Done Sprint 2:** `wiki/` directory populated với pages có cross-links. `graph.pkl` có multiple connected components. Qdrant collection có embeddings.

---

### Sprint 3 — tuần 3: Agent — LangChain Tools + FastAPI

**Mục tiêu:** Agent trả lời được câu hỏi multi-hop với citations. FastAPI streaming.

| Task | Mô tả chi tiết | Effort | Tags |
|---|---|---|---|
| T15 | LangChain tool wiki_search: hybrid search (BM25 full-text + Qdrant cosine), trả về top-5 với snippet + source path + relevance score | 3h | ai |
| T16 | LangChain tool graph_traverse: nhận entity name, trả về 2-hop subgraph serialized as triples "(A) --[pred]--> (B)", dùng NetworkX subgraph query | 3h | ai |
| T17 | LangChain tool ingest_source: nhận URL hoặc file path, trigger full pipeline (fetch → extract → resolve → compile → update graph → upsert Qdrant), trả về summary of changes | 2h | ai |
| T18 | LangChain tool lint_wiki: audit wiki — tìm orphan pages, [CONFLICT] tags chưa resolve, stale pages, trả về health report | 3h | ai |
| T19 | Agent setup: Gemini 2.5 Pro với LangChain tool-calling, system prompt tiếng Việt + WIKI_SCHEMA, conversation memory 5 turns | 2h | ai |
| T20 | FastAPI POST /chat: nhận {query, conversation_history, stream}, StreamingResponse tokens + metadata {steps, citations}, async | 3h | ui |
| T21 | FastAPI POST /ingest + GET /ingest/{task_id}: background task, polling status | 2h | ui |
| T22 | FastAPI GET /graph/{entity}: trả về subgraph JSON cho frontend visualize | 2h | ui |
| T23 | **[BLOCKER]** Test multi-hop query quality: viết 10 câu hỏi cần multi-hop, đánh giá agent có traverse graph không, citations có đúng không | 3h | test |

**Definition of Done Sprint 3:** Câu hỏi "service X depends on gì, và team nào own dependency đó?" được trả lời đúng với citations.

---

### Sprint 4 — tuần 4: Interface — Chainlit + Ops

**Mục tiêu:** Team có thể dùng qua web UI. Hệ thống tự sync và tự maintain.

| Task | Mô tả chi tiết | Effort | Tags |
|---|---|---|---|
| T24 | Chainlit app setup: app.py với @cl.on_message, gọi FastAPI /chat endpoint, stream response tokens, hiện thinking indicator khi agent đang process | 3h | ui |
| T25 | Chainlit step visualization: mỗi tool call hiện thành expandable Step — input query, retrieved nodes/pages. Giúp user thấy reasoning chain | 3h | ui |
| T26 | Source citation rendering: parse [nguồn: path] trong response, render thành clickable links tới Confluence/GitHub URL gốc | 2h | ui |
| T27 | Scheduled sync + lint: APScheduler job mỗi 6h — incremental sync tất cả connectors, chạy lint_wiki, log health report ra file nếu có issues | 3h | ops |
| T28 | Cost monitoring: log Gemini API usage per request (input/output tokens), tính estimated cost mỗi ngày, alert nếu vượt threshold | 2h | ops |
| T29 | Load test + tuning: simulate 20 concurrent users, kiểm tra P95 latency /chat endpoint, tune Qdrant HNSW index, target P95 < 5s | 3h | test |
| T30 | Onboarding doc cho team: README hướng dẫn add connector mới, ingest manual, debug graph_traverse sai, chạy lint manually | 2h | ops |

**Definition of Done Sprint 4:** Team member không technical có thể hỏi qua Chainlit UI và nhận answer có citations trong < 10s.

---

## Rủi ro và cách xử lý

| Rủi ro | Xác suất | Cách xử lý |
|---|---|---|
| Hallucination baked vào wiki pages | Cao | Mỗi page giữ link `source_urls`, lint job spot-check, dùng `[CONFLICT]` tag |
| Entity resolution over-merge | Trung bình | Spot-check output resolver, viết unit test cho các edge cases |
| Chainlit community-maintained từ 5/2025 | Thấp | Backup plan: Streamlit hoặc React frontend đơn giản gọi FastAPI |
| Gemini 2.5 Pro instruction following kém hơn Claude | Trung bình | Test agent với 10 câu multi-hop trước Sprint 4, fallback sang Claude Sonnet nếu quality thấp |
| nomic-embed Ollama server không ổn định | Thấp | Fallback sang Gemini Embedding API (`text-embedding-004`) — đổi 1 function |
| Qdrant Cloud free tier đầy (1GB) | Thấp với corpus nhỏ | ~500 pages × 768 dim × 4 bytes ≈ 1.5MB — còn rất nhiều headroom |
| Confluence API rate limit | Trung bình | Implement exponential backoff + cache responses |
| Wiki stale sau khi doc gốc thay đổi | Cao | Incremental sync mỗi 6h track `last_modified`, delete detection |
| Gemini Flash quality thấp hơn kỳ vọng cho wiki compile | Trung bình | Upgrade compile step sang Gemini 2.5 Pro nếu cần — chỉ tăng cost lúc ingest, không ảnh hưởng query cost |

---

## Ước tính chi phí

### LLM API (Gemini)
| Bước | Model | Tokens ước tính | Chi phí |
|---|---|---|---|
| Initial extraction 500 pages | Flash | ~1M input | ~$0.10 |
| Wiki compilation 500 pages | Flash | ~2M input, 500K output | ~$0.60 |
| Entity resolution | 2.5 Pro | ~100K input | ~$0.13 |
| Agent queries (50/ngày) | 2.5 Pro | ~500K input/ngày | ~$0.63/ngày |
| **Total initial ingest** | | | **~$0.83** |
| **Ongoing (50 queries/ngày)** | | | **~$0.63/ngày** |

### Infrastructure
| Component | Chi phí |
|---|---|
| Qdrant Cloud free tier | $0 |
| nomic-embed (Ollama local) | $0 |
| FastAPI/Chainlit server | Tùy deploy (Railway ~$5/tháng, hoặc VPS) |

---

## Metrics để đánh giá chất lượng

- **Extraction F1** > 0.7 (precision/recall vs gold set) — gate trước Sprint 2
- **Multi-hop accuracy** > 80% trên test set 10 câu — gate trước Sprint 4
- **Citation accuracy**: 100% citations trỏ về source thực sự tồn tại
- **Latency P95** < 5s cho /chat endpoint với 20 concurrent users
- **Wiki health score** > 0.9 (ít orphan pages, ít conflicts chưa resolve)
- **User satisfaction**: thumbs up/down trong Chainlit, target > 80% positive

---

## Dependencies cần cài đặt

```bash
pip install google-generativeai langchain langchain-community langchain-google-genai \
            fastapi uvicorn chainlit \
            networkx qdrant-client ollama \
            tiktoken \
            PyGitHub atlassian-python-api \
            pydantic apscheduler python-dotenv \
            pytest pytest-asyncio httpx rank-bm25
```

## Biến môi trường (.env)

```bash
GEMINI_API_KEY=
QDRANT_URL=https://<cluster-id>.us-east4-0.gcp.cloud.qdrant.io
QDRANT_API_KEY=
GITHUB_TOKEN=
CONFLUENCE_URL=
CONFLUENCE_USERNAME=
CONFLUENCE_API_TOKEN=
NOTION_TOKEN=
OLLAMA_BASE_URL=http://localhost:11434   # hoặc remote Ollama server
```

---

## Checklist trước khi ship

- [ ] Extraction F1 > 0.7 đã verified
- [ ] Multi-hop test set 10 câu pass > 80%
- [ ] Không có hardcoded API keys trong code
- [ ] Incremental sync chạy được không rebuild toàn bộ
- [ ] Lint job log ra file đúng
- [ ] Onboarding README đã viết xong
- [ ] Load test P95 < 5s
- [ ] Chainlit step view hiện đúng reasoning chain
- [ ] Citation links tất cả clickable và valid
- [ ] Cost monitoring dashboard hoạt động
- [ ] Gemini agent quality đã verify vs test set trước khi ship