---
source_urls:
  - "file:///home/phun/workspace/dewly/python/personal-knowledge-ai/raw/local/qmd.md"
last_updated: "2026-06-11T07:31:50.661740+00:00"
entities:
  - "llm-re-ranking"
---
# LLM Re-ranking

## Technical Definition
LLM Re-ranking is a crucial step in advanced hybrid search pipelines, specifically implemented in tools like [[wiki/services/qmd|QMD]], where a local Large Language Model (LLM) is used to re-score and re-order an initial set of search candidates. This process leverages the LLM's deeper semantic understanding to refine relevance beyond traditional keyword or vector similarity. It takes a pre-filtered list of documents and assigns a new relevance score, typically influencing the final order of results.

## Architectural Design
Within the [[wiki/services/qmd|QMD]] hybrid search pipeline, LLM Re-ranking occurs after the initial retrieval and fusion stages.

### Pipeline Position
1.  **[[wiki/concepts/query-expansion|Query Expansion]]**: The user's original query is optionally expanded by an LLM into multiple variants.
2.  **Parallel Retrieval**: Each query variant, along with the original, searches both [[wiki/concepts/bm25|BM25]] (full-text search) and [[wiki/concepts/vector-semantic-search|Vector Semantic Search]] indexes.
3.  **[[wiki/concepts/reciprocal-rank-fusion|Reciprocal Rank Fusion (RRF)]]**: Results from all retrieval backends are merged and scored using RRF, with bonuses for top-ranked documents.
4.  **Top-K Selection**: A subset of the highest-scoring documents (e.g., top 30 candidates) is selected for re-ranking.
5.  **LLM Re-ranking**: This is where the dedicated re-ranking LLM processes the selected candidates.

### Mechanism
The re-ranking component in [[wiki/services/qmd|QMD]] utilizes the `qwen3-reranker-0.6b-q8_0` [[wiki/concepts/gguf-models|GGUF model]] via the [[wiki/concepts/node-llama-cpp|node-llama-cpp]] library. The LLM evaluates each candidate document, providing a relevance score (internally, a "yes/no" decision with logprob confidence, which is then converted to a 0.0-1.0 rating).

### Score Fusion
The LLM's re-ranking scores are blended with the preceding RRF scores using a **Position-Aware Blending** strategy to prevent the reranker from completely overriding high-confidence initial retrieval results:
*   **RRF rank 1-3**: 75% RRF, 25% reranker
*   **RRF rank 4-10**: 60% RRF, 40% reranker
*   **RRF rank 11+**: 40% RRF, 60% reranker

This blend generates the final relevance score for each result.

## Consumers
LLM Re-ranking is primarily consumed by:
*   The `qmd query` command-line interface.
*   The `query` tool exposed by the [[wiki/services/qmd|QMD]] MCP (Model Context Protocol) server.
*   The `store.search()` method in the [[wiki/services/qmd|QMD]] SDK/library when the `rerank` option is enabled (which is the default behavior).

The re-ranking step can be explicitly skipped (e.g., using `--no-rerank` in CLI or `rerank: false` in SDK) for faster results, relying solely on RRF fusion.

## Related Concepts
*   [[wiki/services/qmd]]
*   [[wiki/concepts/bm25]]
*   [[wiki/concepts/vector-semantic-search]]
*   [[wiki/concepts/reciprocal-rank-fusion]]
*   [[wiki/concepts/query-expansion]]
*   [[wiki/concepts/gguf-models]]
*   [[wiki/concepts/node-llama-cpp]]