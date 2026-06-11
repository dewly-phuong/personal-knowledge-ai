---
source_urls:
  - "file:///home/phun/workspace/dewly/python/personal-knowledge-ai/raw/local/qmd.md"
last_updated: "2026-06-11T07:36:32.747182+00:00"
entities:
  - "qmd-store"
---
# QMD Store

QMD (Query Markup Documents) Store is an on-device search engine designed for indexing and searching personal knowledge bases, markdown notes, meeting transcripts, and documentation. It integrates [[wiki/concepts/BM25]] full-text search, [[wiki/concepts/vector-semantic-search]], and [[wiki/concepts/LLM-re-ranking]], all running locally via [[wiki/services/node-llama-cpp]] with [[wiki/concepts/GGUF]] models. It is particularly well-suited for integration into [[wiki/concepts/AI-agents]] workflows.

## Technical Definition

QMD provides a unified interface for local search, offering various modes:
*   `search`: BM25 full-text search.
*   `vsearch`: Vector semantic search.
*   `query`: A hybrid approach combining BM25, vector search, LLM-driven query expansion, and [[wiki/concepts/LLM-re-ranking]] for best quality.

It uses a SQLite database (`~/.cache/qmd/index.sqlite`) to store indexed content, metadata, and vector embeddings.

## Architectural Design

The QMD system consists of several integrated components to deliver its hybrid search capabilities:

### High-Level Architecture
QMD processes documents through indexing and embedding flows, and queries through a sophisticated hybrid search pipeline.

#### Indexing Flow
Markdown files are processed from defined collections, titles are parsed, content is hashed to generate a `docid`, and then stored in SQLite with an FTS5 index.

#### Embedding Flow
Documents are chunked into approximately 900-token pieces with 15% overlap, using smart boundary detection to preserve semantic units. Each chunk is formatted and passed to `node-llama-cpp` for vector embedding, which are then stored in a `sqlite-vec` index.

#### Smart Chunking
QMD employs a scoring algorithm to find natural markdown breakpoints for chunking, prioritizing headings, code block boundaries, and horizontal rules. For supported code files (`.ts`, `.tsx`, `.js`, `.jsx`, `.py`, `.go`, `.rs`), it can use AST-aware chunking with `tree-sitter` to break at class, function, and import boundaries, improving chunk quality for codebases.

### QMD Hybrid Search Pipeline

The `query` command executes a sophisticated pipeline:
1.  **Query Expansion**: The user's query is expanded by a fine-tuned LLM into 2 alternative queries, which are combined with the original query (weighted ×2).
2.  **Parallel Retrieval**: Each of the (up to) 3 queries is run against both the [[wiki/concepts/BM25]] (FTS5) and [[wiki/concepts/vector-semantic-search]] backends in parallel.
3.  **[[wiki/concepts/Reciprocal-Rank-Fusion]] (RRF)**: All resulting lists are combined using RRF (k=60), with the original query receiving ×2 weight. A top-rank bonus (+0.05 for #1, +0.02 for #2-3) is applied.
4.  **Top-K Selection**: The top 30 candidates from RRF are selected.
5.  **LLM Re-ranking**: A dedicated [[wiki/concepts/LLM-re-ranking]] model (qwen3-reranker) scores each document candidate for relevance (yes/no + logprobs confidence).
6.  **Position-Aware Blending**: Final scores blend RRF and reranker scores based on the RRF rank:
    *   Top 1-3: 75% RRF, 25% reranker
    *   Top 4-10: 60% RRF, 40% reranker
    *   Top 11+: 40% RRF, 60% reranker
7.  **Final Results**: Sorted by the blended score.

#### Score Normalization & Fusion
*   **FTS (BM25)**: Raw SQLite FTS5 BM25 score, converted to `Math.abs(score)`, range 0 to ~25+.
*   **Vector**: Raw cosine distance, converted to `1 / (1 + distance)`, range 0.0 to 1.0.
*   **Reranker**: LLM 0-10 rating, converted to `score / 10`, range 0.0 to 1.0.

## Consumers

QMD is designed for:
*   **Individual developers and knowledge workers**: To index and search their personal notes, documentation, and transcripts.
*   **[[wiki/concepts/AI-agents]] and agentic workflows**: Providing structured, context-rich search results via command-line `--json`/`--files` output or a dedicated MCP server.
*   **Node.js/Bun applications**: As an embeddable library for adding local search capabilities.

## Usage

QMD can be used via its CLI, an MCP server, or an SDK.

### Quick Start (CLI)

```sh
# Install globally (Node or Bun)
npm install -g @tobilu/qmd
# or
bun install -g @tobilu/qmd

# Create collections
qmd collection add ~/notes --name notes
qmd collection add ~/Documents/meetings --name meetings

# Add context
qmd context add qmd://notes "Personal notes and ideas"
qmd context add qmd://meetings "Meeting transcripts and notes"

# Generate embeddings
qmd embed

# Search across everything
qmd search "project timeline"           # Fast keyword search
qmd vsearch "how to deploy"             # Semantic search
qmd query "quarterly planning process"  # Hybrid + reranking (best quality)

# Get a specific document
qmd get "meetings/2024-01-15.md"
```

### Using with AI Agents

QMD's `--json` and `--files` output formats are designed for agentic workflows, allowing [[wiki/concepts/LLM]]s to consume structured results directly:

```sh
# Get structured results for an LLM
qmd search "authentication" --json -n 10

# List all relevant files above a threshold
qmd query "error handling" --all --files --min-score 0.4
```

### MCP (Model Context Protocol) Server

For tighter integration with [[wiki/concepts/AI-agents]], QMD exposes an MCP server.
**Tools exposed**: `query`, `get`, `multi_get`, `status`.
Configuration examples are provided for Claude Desktop and Claude Code.

#### HTTP Transport
The MCP server can also run as a shared, long-lived HTTP daemon (`qmd mcp --http`) to avoid repeated model loading, exposing `POST /mcp` and `GET /health` endpoints.

### SDK / Library Usage

QMD can be used as a library in Node.js or Bun applications.

```typescript
import { createStore } from '@tobilu/qmd'

const store = await createStore({
  dbPath: './my-index.sqlite',
  config: {
    collections: {
      docs: { path: '/path/to/docs', pattern: '**/*.md' },
    },
  },
})

const results = await store.search({ query: "authentication flow" })
console.log(results.map(r => `${r.title} (${Math.round(r.score * 100)}%)`))

await store.close()
```
The SDK provides methods for store creation (inline, config file, or DB-only), searching (simple, options, pre-expanded queries, direct backend access), retrieval (by path/docid, body with line range, batch `multiGet`), collection management (add, list, remove, rename, update-cmd), and context management (add, set global, list, remove).

### Collection Management

Manage indexed directories:
*   `qmd collection add . --name myproject`
*   `qmd collection list`
*   `qmd collection remove myproject`
*   `qmd collection rename myproject my-project`
*   `qmd ls notes`
*   `qmd collection include/exclude notes`
*   `qmd collection update-cmd notes 'git pull --rebase'`

### Context Management

Add descriptive metadata to collections and paths to improve search relevance:
*   `qmd context add qmd://notes "Personal notes and ideas"`
*   `qmd context add qmd://docs/api "API documentation"`
*   `qmd context add / "Knowledge base for my projects"` (global context)
*   `qmd context list`
*   `qmd context rm qmd://notes/old`

### Index Maintenance

*   `qmd status`: Show index status and collections.
*   `qmd update`: Re-index all collections, running update commands if configured.
*   `qmd embed`: Generate vector embeddings for indexed documents. `--force` to re-embed everything. `--chunk-strategy auto` enables AST-aware chunking for code files.
*   `qmd doctor`: Diagnose installation.
*   `qmd init`: Initialize a project-local index.
*   `qmd get <file/docid>[:from[:count]]`: Retrieve document content.
*   `qmd multi-get <pattern/list>`: Batch retrieve documents.
*   `qmd cleanup`: Clean up cache and orphaned data.

### Search Commands and Options

*   `qmd search "query"`: BM25 keyword search.
*   `qmd vsearch "query"`: Vector semantic search.
*   `qmd query "query"`: Hybrid search with re-ranking.
*   **Options**: `-n <num>` (results limit), `-c, --collection` (filter by collection), `--all`, `--min-score <num>`, `--full`, `--line-numbers`, `--explain`, `--index <name>`, `--intent "<text>"`, `--no-rerank`, `--candidate-limit <n>`, `--full-path`.
*   **Output Formats**: `cli` (default), `json`, `csv`, `md`, `xml`, `files`. CLI output features clickable terminal hyperlinks (OSC 8) configurable via `QMD_EDITOR_URI`.

## Related Concepts

*   [[wiki/concepts/BM25]]
*   [[wiki/concepts/Vector-Semantic-Search]]
*   [[wiki/concepts/LLM-re-ranking]]
*   [[wiki/concepts/Reciprocal-Rank-Fusion]] (RRF)
*   [[wiki/concepts/GGUF]]
*   [[wiki/concepts/AI-agents]]
*   [[wiki/services/node-llama-cpp]]

## Requirements

### System Requirements
*   **Node.js**: >= 22
*   **Bun**: >= 1.0.0
*   **macOS**: Homebrew SQLite (for extension support: `brew install sqlite`)

### GGUF Models
QMD auto-downloads three local [[wiki/concepts/GGUF]] models for its operations:
| Model | Purpose | Size |
|---|---|---|
| `embeddinggemma-300M-Q8_0` | Vector embeddings (default) | ~300MB |
| `qwen3-reranker-0.6b-q8_0` | Re-ranking | ~640MB |
| `qmd-query-expansion-1.7B-q4_k_m` | Query expansion (fine-tuned) | ~1.1GB |
Models are cached in `~/.cache/qmd/models/`.

### Custom Embedding Model
The default embedding model can be overridden using the `QMD_EMBED_MODEL` environment variable, supporting `embeddinggemma` (English) and `Qwen3-Embedding` (multilingual/CJK). Re-embedding with `qmd embed -f` is required after changing the model.

## Data Storage

The primary index is stored in `~/.cache/qmd/index.sqlite`.

### Schema
*   `collections`: Indexed directories with name and glob patterns.
*   `path_contexts`: Context descriptions by virtual path.
*   `documents`: Markdown content with metadata and `docid` (6-char hash).
*   `documents_fts`: FTS5 full-text index.
*   `content_vectors`: Embedding chunks.
*   `vectors_vec`: `sqlite-vec` vector index.
*   `llm_cache`: Cached LLM responses.

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `XDG_CACHE_HOME` | `~/.cache` | Cache directory location |
| `QMD_LLAMA_GPU` | `auto` | Force `llama.cpp` GPU backend (`metal`, `vulkan`, `cuda`) or disable with `false` |
| `QMD_FORCE_CPU` | unset | Set to `1`/`true` to force CPU mode. Equivalent CLI flag: `--no-gpu`. |
| `QMD_EMBED_PARALLELISM` | automatic | Override embedding/reranking context parallelism (1-8). |

## Model Configuration

Default models are configured via HuggingFace URIs within `src/llm.ts`:
*   `DEFAULT_EMBED_MODEL`: `embeddinggemma-300M-Q8_0`
*   `DEFAULT_RERANK_MODEL`: `qwen3-reranker-0.6b-q8_0`
*   `DEFAULT_GENERATE_MODEL`: `qmd-query-expansion-1.7B-q4_k_m`

Prompt formats are automatically adjusted for each model family (e.g., `embeddinggemma` uses "task: search result | query: {query}" for queries).