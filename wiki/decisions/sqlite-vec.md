---
source_urls:
  - "file:///home/phun/workspace/dewly/python/personal-knowledge-ai/raw/local/qmd.md"
last_updated: "2026-06-11T07:35:13.313453+00:00"
entities:
  - "sqlite-vec"
---
# SQLite-vec

`SQLite-vec` is an extension for the [[wiki/services/sqlite|SQLite]] database, specifically designed for efficient [[wiki/concepts/vector-embeddings|vector indexing]] and search. It enhances SQLite's capabilities by allowing direct storage and querying of vector embeddings, which is crucial for semantic search functionalities.

## Technical Definition
Within the [[wiki/services/qmd|QMD]] (Query Markup Documents) search engine's data storage schema, `sqlite-vec` is explicitly utilized by the `vectors_vec` table. This table is dedicated to storing embedding chunks, where each chunk is identified by a `hash_seq` key. `SQLite-vec` underpins QMD's vector semantic search capabilities, providing a robust mechanism for similarity lookups directly within the local database.

## Architectural Design
In the architecture of [[wiki/services/qmd|QMD]], `sqlite-vec` enables the core [[wiki/concepts/vector-embeddings|vector similarity search]] functionality. It is an integral component of QMD's local index infrastructure, facilitating rapid retrieval of semantically similar documents based on pre-computed vector embeddings. This design allows LLM models (used for generating embeddings) to remain loaded in VRAM, contributing to faster query processing by minimizing model reloads. `SQLite-vec` works in conjunction with [[wiki/concepts/fts5|SQLite FTS5]] to provide a comprehensive hybrid search approach, combining full-text and semantic search.

## Consumers
- [[wiki/services/qmd|QMD]] (Query Markup Documents)

## System Requirements
For `sqlite-vec` to function correctly, particularly on macOS, an installation of [[wiki/services/sqlite|SQLite]] with extension support is necessary. This can typically be achieved using Homebrew:

```sh
brew install sqlite
```
This command ensures the required SQLite environment is in place to load and utilize the `sqlite-vec` extension effectively.