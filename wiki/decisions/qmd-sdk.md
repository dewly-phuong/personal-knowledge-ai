---
source_urls:
  - "file:///home/phun/workspace/dewly/python/personal-knowledge-ai/raw/local/qmd.md"
last_updated: "2026-06-11T07:33:10.897510+00:00"
entities:
  - "qmd"
  - "qmd-sdk"
---
# QMD - Query Markup Documents

An on-device search engine for indexing markdown notes, meeting transcripts, documentation, and knowledge bases. It supports searching with keywords or natural language and is ideal for agentic flows.

QMD combines [[wiki/concepts/bm25-search]] full-text search, [[wiki/concepts/vector-semantic-search]] with vector embeddings, and [[wiki/concepts/llm-re-ranking]] for re-ranking, all running locally via [[wiki/concepts/node-llama-cpp]] with [[wiki/concepts/gguf-models]].

## Features

*   **Hybrid Search**: Combines BM25, vector semantic search, and LLM re-ranking for best quality results.
*   **Local Execution**: All search and LLM components run locally via [[wiki/concepts/node-llama-cpp]] with GGUF models, ensuring privacy and speed.
*   **Agentic Flows**: Designed with `--json` and `--files` output formats for easy integration with AI agents.
*   **Contextual Search**: Allows adding descriptive context to collections and paths, improving search relevance for LLMs.
*   **MCP Server**: Exposes a Model Context Protocol (MCP) server for tighter integration with clients like [[wiki/services/claude-ai]].
*   **SDK/Library Usage**: Can be integrated into [[wiki/concepts/node-js]] or [[wiki/concepts/bun]] applications.
*   **Smart Chunking**: Uses a scoring algorithm and [[wiki/concepts/tree-sitter]] (for code files) to find natural markdown/code break points for embedding.

## Quick Start (CLI)

```sh
# Install globally (Node or Bun)
npm install -g @tobilu/qmd
# or
bun install -g @tobilu/qmd

# Create collections for your notes, docs, and meeting transcripts
qmd collection add ~/notes --name notes
qmd collection add ~/Documents/meetings --name meetings
qmd collection add ~/work/docs --name docs

# Add context
qmd context add qmd://notes "Personal notes and ideas"

# Generate embeddings for semantic search
qmd embed

# Search across everything
qmd search "project timeline"           # Fast keyword search
qmd vsearch "how to deploy"             # Semantic search
qmd query "quarterly planning process"  # Hybrid + reranking (best quality)
```

## Architecture

QMD employs a sophisticated hybrid search pipeline:

1.  **Query Expansion**: The initial user query is expanded by a fine-tuned LLM into multiple alternative queries. The original query is given twice the weight.
2.  **Parallel Retrieval**: Each query (original and expanded) simultaneously searches both [[wiki/concepts/bm25-search]] (FTS5) and [[wiki/concepts/vector-semantic-search]] indexes.
3.  **RRF Fusion**: All retrieved result lists are combined using [[wiki/concepts/reciprocal-rank-fusion]] (RRF) with a configurable `k` value (default 60).
4.  **Top-Rank Bonus**: Documents ranking #1 in any list receive a +0.05 bonus, and #2-3 receive +0.02.
5.  **LLM Re-ranking**: The top 30 candidates from RRF fusion are then re-ranked by a dedicated LLM ([[wiki/concepts/qwen3-reranker]]) which provides a yes/no relevance assessment with log-probability confidence.
6.  **Position-Aware Blending**: The final score is a blend of the RRF score and the LLM re-ranker score, with the blending ratio adjusted based on the RRF rank to preserve high-confidence retrieval results:
    *   RRF rank 1-3: 75% retrieval, 25% reranker
    *   RRF rank 4-10: 60% retrieval, 40% reranker
    *   RRF rank 11+: 40% retrieval, 60% reranker

## Model Context Protocol (MCP) Server

QMD exposes an MCP server for tighter integration with AI agents.

### Tools Exposed

*   `query`: Search with typed sub-queries (`lex`/`vec`/`hyde`), combined via RRF + reranking.
*   `get`: Retrieve a document by path or docid.
*   `multi_get`: Batch retrieve by glob pattern, comma-separated list, or docids.
*   `status`: Index health and collection information.

### HTTP Transport

For a shared, long-lived server that avoids repeated model loading, QMD supports an HTTP transport (default `localhost:8181`).

```sh
# Foreground
qmd mcp --http

# Background daemon
qmd mcp --http --daemon
```

## SDK / Library Usage

QMD can be used as a library in [[wiki/concepts/node-js]] or [[wiki/concepts/bun]] applications.

### Installation

```sh
npm install @tobilu/qmd
```

### Quick Start (TypeScript)

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

## Data Storage

QMD stores its index in `~/.cache/qmd/index.sqlite`.

### Schema Highlights

*   `collections`: Indexed directories with name and glob patterns.
*   `path_contexts`: Context descriptions by virtual path (qmd://...).
*   `documents`: Markdown content with metadata and docid (6-char hash).
*   `documents_fts`: [[wiki/services/sqlite]] FTS5 full-text index.
*   `content_vectors`: Embedding chunks (~900 tokens each).
*   `vectors_vec`: [[wiki/services/sqlite]] `sqlite-vec` vector index.
*   `llm_cache`: Cached LLM responses.

## Requirements

### System

*   [[wiki/concepts/node-js]] >= 22
*   [[wiki/concepts/bun]] >= 1.0.0
*   macOS: Homebrew [[wiki/services/sqlite]] (for extension support)

### GGUF Models (via [[wiki/concepts/node-llama-cpp]])

QMD automatically downloads and caches three local [[wiki/concepts/gguf-models]] from [[wiki/services/huggingface]] on first use:

*   `embeddinggemma-300M-Q8_0`: For vector embeddings (~300MB).
*   `qwen3-reranker-0.6b-q8_0`: For re-ranking (~640MB).
*   `qmd-query-expansion-1.7B-q4_k_m`: For query expansion (fine-tuned, ~1.1GB).

Custom embedding models can be specified via the `QMD_EMBED_MODEL` environment variable.

## Smart Chunking

QMD chunks documents into ~900-token pieces with 15% overlap using smart boundary detection. This algorithm scores potential break points (headings, code blocks, blank lines) and cuts at the highest-scoring point within a 200-token window before the target.

### AST-Aware Chunking

For supported code files (`.ts`, `.tsx`, `.js`, `.jsx`, `.py`, `.go`, `.rs`), QMD leverages [[wiki/concepts/tree-sitter]] to add AST-derived break points (e.g., class, function, import boundaries), which are merged with regex scores for higher-quality code chunks. This is enabled with `--chunk-strategy auto`.