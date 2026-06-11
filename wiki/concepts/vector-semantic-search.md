---
source_urls:
  - "file:///home/phun/workspace/dewly/python/personal-knowledge-ai/raw/local/qmd.md"
last_updated: "2026-06-11T07:31:30.056789+00:00"
entities:
  - "vector-semantic-search"
---
# Vector Semantic Search

Vector semantic search is a search technique that leverages numerical representations (vectors) of text to find semantically similar documents or passages, rather than relying solely on keyword matching. In [[wiki/services/qmd|QMD (Query Markup Documents)]], it is a core component that works in conjunction with [[wiki/concepts/bm25|BM25 full-text search]] and [[wiki/concepts/llm-re-ranking|LLM re-ranking]] to provide a powerful hybrid search experience.

## Technical Definition

Vector semantic search in [[wiki/services/qmd|QMD]] operates by generating embeddings (dense vector representations) for both the query and the indexed document chunks. These embeddings capture the semantic meaning of the text. During a search, the similarity between the query embedding and document chunk embeddings is calculated using [[wiki/concepts/cosine-similarity|cosine distance]]. A smaller distance indicates higher semantic similarity.

Key aspects in QMD's implementation:
*   **Similarity Metric**: Uses cosine distance for raw scores, which are then converted to a 0.0 to 1.0 range using `1 / (1 + distance)`.
*   **Embedding Models**: Relies on local [[wiki/concepts/gguf-models|GGUF models]] (e.g., `embeddinggemma-300M-Q8_0`) executed via [[wiki/concepts/node-llama-cpp|node-llama-cpp]]. These models are auto-downloaded on first use.
*   **Document Chunking**: Before embedding, documents are split into approximately 900-token chunks with 15% overlap. This is done using a [[wiki/concepts/smart-chunking|smart chunking]] algorithm that identifies natural markdown and (optionally) AST-aware code boundaries to preserve semantic units.
*   **CLI Access**: Users can perform pure vector semantic search directly using `qmd vsearch "how to login"`.
*   **SDK Access**: Developers can access vector search functionality via `store.searchVector("how users log in", { limit: 10 })` in the QMD SDK.

## Architectural Design

Vector semantic search is an integral part of [[wiki/services/qmd|QMD]]'s overall architecture, particularly within its hybrid search pipeline.

### Embedding Flow
The process of creating document embeddings follows these steps:
1.  **Document Ingestion**: Markdown files from configured collections are processed.
2.  **[[wiki/concepts/smart-chunking|Smart Chunking]]**: Documents are broken into semantically meaningful chunks (approx. 900 tokens, 15% overlap). This includes detecting markdown headings, code blocks, and for code files, AST nodes (classes, functions, imports).
3.  **Chunk Formatting**: Each chunk is formatted (e.g., `"title: {title} | text: {content}"`) to optimize for the embedding model.
4.  **Embedding Generation**: The formatted chunks are passed to the `node-llama-cpp` `embedBatch()` function, which uses a local [[wiki/concepts/gguf-models|GGUF embedding model]].
5.  **Vector Storage**: The generated vectors are stored in the `content_vectors` table and indexed by [[wiki/concepts/sqlite-vec|sqlite-vec]].

### Query Flow (Hybrid)
When a query is submitted using `qmd query`, vector semantic search contributes to the overall result:
1.  **LLM Query Expansion**: The original query is expanded into several variants using an [[wiki/concepts/llm-re-ranking|LLM]].
2.  **Parallel Retrieval**: For each query (original and expanded variants), parallel searches are performed:
    *   [[wiki/concepts/bm25|BM25 Full-Text Search]]
    *   **Vector Semantic Search**
3.  **[[wiki/concepts/reciprocal-rank-fusion|RRF Fusion]]**: The ranked lists from BM25 and vector search are combined using Reciprocal Rank Fusion (RRF). The original query's contributions are weighted higher, and top-ranked documents receive a bonus.
4.  **[[wiki/concepts/llm-re-ranking|LLM Re-ranking]]**: A subset of the top candidates (e.g., top 30) from RRF are then passed to an [[wiki/concepts/llm-re-ranking|LLM re-ranker]] for a final relevance score.
5.  **Position-Aware Blending**: The final scores are a blend of RRF and re-ranker scores, with the blending ratio adjusted based on the document's initial RRF rank to preserve high-confidence exact matches.

### Embedding Models
QMD uses `embeddinggemma-300M-Q8_0` as its default embedding model, optimized for English. Users can override this with the `QMD_EMBED_MODEL` environment variable (e.g., `Qwen3-Embedding-0.6B`) for better multilingual support. It is crucial to re-embed all collections (`qmd embed -f`) when switching models due to vector incompatibility.

## Consumers

Vector semantic search is primarily consumed by:
*   **[[wiki/services/qmd|QMD]] CLI Users**: Directly via `qmd vsearch` for pure semantic search, or implicitly as part of `qmd query` for hybrid search.
*   **[[wiki/services/qmd|QMD]] SDK Users**: Developers embedding QMD as a library in their Node.js or Bun applications can use `store.searchVector()` or `store.search()` with structured queries.
*   **[[wiki/concepts/ai-agents|AI Agents]]**: Agents integrating with QMD through its command-line interface or MCP (Model Context Protocol) server leverage semantic search capabilities for contextual information retrieval.

## Related Concepts

*   [[wiki/services/qmd|QMD (Query Markup Documents)]]
*   [[wiki/concepts/bm25|BM25]]
*   [[wiki/concepts/llm-re-ranking|LLM Re-ranking]]
*   [[wiki/concepts/reciprocal-rank-fusion|Reciprocal Rank Fusion (RRF)]]
*   [[wiki/concepts/gguf-models|GGUF Models]]
*   [[wiki/concepts/node-llama-cpp|node-llama-cpp]]
*   [[wiki/concepts/sqlite-vec|sqlite-vec]]
*   [[wiki/concepts/smart-chunking|Smart Chunking]]
*   [[wiki/concepts/cosine-similarity|Cosine Similarity]]
*   [[wiki/concepts/ai-agents|AI Agents]]