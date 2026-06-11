---
source_urls:
  - "file:///home/phun/workspace/dewly/python/personal-knowledge-ai/raw/local/qmd.md"
last_updated: "2026-06-11T07:31:20.956177+00:00"
entities:
  - "bm25-full-text-search"
---
# BM25 Full-Text Search

## Technical Definition

BM25 (Best Match 25) is a ranking function used by search engines to estimate the relevance of documents to a given search query. It's a bag-of-words retrieval function that ranks a set of documents based on the query terms appearing in each document, regardless of the proximity of the query terms within the document.

In the context of the [[wiki/services/qmd|QMD (Query Markup Documents)]] system, BM25 is implemented using SQLite's FTS5 (Full-Text Search 5) extension. It provides fast, keyword-based search capabilities.

Key characteristics in QMD:
*   **Raw Score**: BM25 scores are derived from SQLite FTS5 and converted using `Math.abs(score)`, typically ranging from 0 to approximately 25+.
*   **Keyword-Based**: It primarily focuses on exact keyword matches and their frequency/distribution within documents.
*   **Component of Hybrid Search**: While powerful for keyword search, BM25 is often combined with other search methods, such as [[wiki/concepts/vector-semantic-search|vector semantic search]] and [[wiki/concepts/llm-re-ranking|LLM re-ranking]], to achieve a more comprehensive and contextually aware search experience.

## Architectural Design

Within the [[wiki/services/qmd|QMD]] architecture, BM25 (FTS5) serves as one of the primary search backends. It operates in parallel with vector search during the hybrid search pipeline.

### Integration in QMD's Hybrid Search Pipeline

1.  **Query Expansion**: User queries are first expanded by an LLM into multiple variants (original query receiving a 2x weight).
2.  **Parallel Retrieval**: For each original and expanded query, both BM25 (FTS5) and [[wiki/concepts/vector-semantic-search|vector semantic search]] backends are queried simultaneously.
3.  **[[wiki/concepts/reciprocal-rank-fusion|RRF Fusion]]**: The ranked lists of results from BM25 and vector search for all query variants are combined using Reciprocal Rank Fusion (RRF). This step includes a bonus for top-ranked documents.
4.  **LLM Re-ranking**: The top candidates from RRF are then passed to an [[wiki/concepts/llm-re-ranking|LLM re-ranking]] model (e.g., `qwen3-reranker`) for a final relevance assessment.
5.  **Position-Aware Blending**: The final score is a blend of the RRF score and the LLM reranker score, with the blending ratio adjusted based on the initial RRF rank to preserve high-confidence retrieval results.

The `qmd search` command explicitly uses only the BM25 full-text search backend for fast, keyword-based results, bypassing the LLM expansion and reranking steps.

## Consumers

The primary consumer of BM25 Full-Text Search is the [[wiki/services/qmd|QMD]] application itself, both via its command-line interface and its SDK/library.

*   **QMD CLI**: The `qmd search` command directly utilizes BM25 for keyword-based search.
*   **QMD SDK/Library**: Developers can access BM25 capabilities programmatically through the `store.searchLex()` method in Node.js or Bun applications using the `@tobilu/qmd` package.
*   **AI Agents**: Agents configured to use QMD can leverage the `qmd search` command for quick keyword lookups, particularly when a direct keyword match is expected.

## Related Concepts

*   [[wiki/services/qmd|QMD]]
*   [[wiki/concepts/vector-semantic-search|Vector Semantic Search]]
*   [[wiki/concepts/llm-re-ranking|LLM Re-ranking]]
*   [[wiki/concepts/reciprocal-rank-fusion|Reciprocal Rank Fusion]]
*   [[wiki/concepts/sqlite-fts5|SQLite FTS5]]