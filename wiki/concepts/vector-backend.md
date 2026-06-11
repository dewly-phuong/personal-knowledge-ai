---
source_urls:
  - "file:///home/phun/workspace/dewly/python/personal-knowledge-ai/raw/local/qmd.md"
last_updated: "2026-06-11T07:34:02Z"
entities:
  - "vector-backend"
---
# Vector Backend

## Technical Definition
A Vector Backend is a system component responsible for storing and querying numerical representations (vectors) of data, typically generated through [[wiki/concepts/embeddings]] models. These vectors capture semantic meaning, allowing for similarity searches based on conceptual relevance rather than just keyword matching.

## Role within QMD
In the context of [[wiki/concepts/qmd]] (Query Markup Documents), the Vector Backend is a core component that enables [[wiki/concepts/semantic-search]]. QMD integrates vector semantic search alongside [[wiki/concepts/bm25]] full-text search and [[wiki/concepts/llm-re-ranking]] to provide a comprehensive hybrid search pipeline. It allows users to query their markdown notes and documentation using natural language, finding semantically similar documents even if exact keywords are not present.

## Architecture and Implementation
QMD's Vector Backend is implemented locally using `node-llama-cpp` with GGUF models and backed by `sqlite-vec` for vector indexing within an SQLite database.

### Data Storage
The vector backend data is stored within the `~/.cache/qmd/index.sqlite` file, utilizing specific tables:
*   `content_vectors`: Stores embedding chunks, each identified by a document hash, chunk sequence (`seq`), and character position (`pos`) in the original document. Each chunk typically contains around 900 tokens.
*   `vectors_vec`: This table acts as the [[wiki/concepts/sqlite-vec]] vector index, facilitating efficient similarity searches on the `content_vectors`.

### Embedding Flow and Smart Chunking
To populate the vector backend, documents undergo an embedding flow:
1.  **Smart Chunking**: Documents are divided into semantically coherent chunks, approximately 900 tokens each with 15% overlap. This process prioritizes natural markdown break points (e.g., headings, code block boundaries, blank lines) to keep semantic units intact.
    *   **AST-Aware Chunking**: For supported code files (`.ts`, `.tsx`, `.js`, `.jsx`, `.py`, `.go`, `.rs`), [[wiki/concepts/tree-sitter]] is used to identify AST-derived break points (e.g., classes, functions, imports), which are merged with regex-based scores to produce higher-quality chunks.
2.  **Chunk Formatting**: Each chunk is formatted (e.g., `"title: {title} | text: {content}"`) to optimize for the embedding model.
3.  **Embedding Generation**: Formatted chunks are processed by `node-llama-cpp`'s `embedBatch()` function using a local [[wiki/concepts/gguf-models]] embedding model (e.g., `embeddinggemma-300M-Q8_0`).
4.  **Vector Storage**: The generated vectors are then stored in the `content_vectors` table, and indexed by `sqlite-vec` in `vectors_vec`.

### Query Flow
During a query operation in QMD:
1.  The user's original query, potentially expanded by an LLM, is sent to the Vector Search component in parallel with the FTS (BM25) search.
2.  The Vector Search component performs a semantic similarity search against the `vectors_vec` index.
3.  The results from the Vector Search, along with those from BM25, are then combined using [[wiki/concepts/reciprocal-rank-fusion]] (RRF).
4.  Optionally, the fused results undergo [[wiki/concepts/llm-re-ranking]] for further refinement, leading to the final ordered list of relevant documents.

## Model Configuration
QMD uses `embeddinggemma-300M-Q8_0` as its default embedding model. Users can override this default via the `QMD_EMBED_MODEL` environment variable to utilize other [[wiki/concepts/gguf-models]], such as those optimized for multilingual corpora. When switching embedding models, a full re-embedding with `qmd embed -f` is required due to vector incompatibility between models.

## Usage and Integration
The vector backend capabilities are exposed in QMD through:
*   **CLI**: `qmd vsearch "your query"` for direct semantic search, or `qmd query "your query"` for hybrid search including vector contributions. `qmd embed` initiates the embedding process.
*   **MCP Server**: The `query` tool, exposed by QMD's MCP server, accepts typed sub-queries including `vec` for vector search.
*   **SDK**: The `@tobilu/qmd` Node.js/Bun SDK provides `store.search()` and `store.searchVector()` methods for programmatic access to the vector backend, as well as `store.embed()` for index management.

## Related Concepts
*   [[wiki/concepts/qmd]]
*   [[wiki/concepts/semantic-search]]
*   [[wiki/concepts/embeddings]]
*   [[wiki/concepts/llm-re-ranking]]
*   [[wiki/concepts/reciprocal-rank-fusion]]
*   [[wiki/concepts/bm25]]
*   [[wiki/concepts/node-llama-cpp]]
*   [[wiki/concepts/gguf-models]]
*   [[wiki/concepts/tree-sitter]]
*   [[wiki/concepts/sqlite-vec]]