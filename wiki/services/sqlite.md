---
source_urls:
  - "file:///home/phun/workspace/dewly/python/personal-knowledge-ai/raw/local/qmd.md"
last_updated: "2026-06-11T07:35:55.155930+00:00"
entities:
  - "sqlite"
---
# SQLite

SQLite is a self-contained, high-reliability, embedded, full-featured public-domain SQL database engine. It is utilized by the QMD (Query Markup Documents) system as its primary data storage mechanism.

## Usage by QMD (Query Markup Documents)

QMD stores its index in an SQLite database, typically located at `~/.cache/qmd/index.sqlite`. This database contains various tables to manage collections, path contexts, documents, and their associated data:

*   `collections`: Indexed directories with names and glob patterns.
*   `path_contexts`: Context descriptions by virtual path (e.g., `qmd://...`).
*   `documents`: Markdown content with metadata and a 6-character hash `docid`.
*   `documents_fts`: An FTS5 full-text index for efficient keyword searching.
*   `content_vectors`: Embedding chunks (hash, sequence, position, ~900 tokens each).
*   `vectors_vec`: A `sqlite-vec` vector index, keyed by `hash_seq`, for semantic search.
*   `llm_cache`: Cached LLM responses, including query expansion and rerank scores.

QMD leverages SQLite's FTS5 for BM25 full-text search capabilities and integrates with `sqlite-vec` for vector similarity searches.

## Requirements

For macOS users, Homebrew SQLite is recommended for extension support, which is often crucial for tools like QMD that rely on SQLite extensions.

[[wiki/services/qmd]]