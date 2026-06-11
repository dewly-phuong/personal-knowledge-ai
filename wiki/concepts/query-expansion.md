---
source_urls:
  - "file:///home/phun/workspace/dewly/python/personal-knowledge-ai/raw/local/qmd.md"
last_updated: "2026-06-11T07:36:52.540231+00:00"
entities:
  - "query-expansion"
---
# Query Expansion

## Technical Definition
Query Expansion is a core component within the [[wiki/concepts/qmd]] hybrid search pipeline responsible for enhancing search queries by generating semantically similar or related query variations. This process utilizes a fine-tuned [[wiki/concepts/large-language-model|Large Language Model]] (LLM) to interpret the original user query and produce alternative formulations, thereby increasing the recall and relevance of search results across both [[wiki/concepts/bm25]] full-text and [[wiki/concepts/vector-semantic-search]] backends.

The process often involves:
1.  Taking the initial user query.
2.  Using an LLM to generate one or more alternative queries.
3.  The original query is typically given twice the weight in subsequent fusion steps.
4.  Optionally incorporating user-provided "intent" for disambiguation, which guides the expansion without directly being searched on its own.

## Architectural Design
Query Expansion sits at the beginning of the [[wiki/concepts/qmd]] Hybrid Search Pipeline. A user's query first passes through the Query Expansion module, which leverages the `qmd-query-expansion-1.7B-q4_k_m` [[wiki/concepts/gguf-models|GGUF model]] via [[wiki/services/node-llama-cpp|node-llama-cpp]]'s `LlamaChatSession` API.

The output of this stage is typically a set of queries: the original query (often weighted higher) and one or more LLM-generated variant queries. These expanded queries are then fed in parallel to both the BM25 (FTS5) and Vector Search backends.

```
Query ──► LLM Expansion ──► [Original, Variant 1, Variant 2]
```
The results from these parallel searches are subsequently combined using [[wiki/concepts/reciprocal-rank-fusion|Reciprocal Rank Fusion]] (RRF) and further refined by [[wiki/concepts/llm-reranking|LLM Re-ranking]].

## Consumers
Query Expansion is implicitly used by the following [[wiki/concepts/qmd]] functionalities:
*   **`qmd query` CLI command**: The default and recommended search mode for best quality, which automatically performs query expansion.
*   **QMD MCP Server**: The `query` tool exposed by the MCP server supports query expansion.
*   **QMD SDK (`store.search()` method)**: When a simple `query` string is provided to `store.search()`, it's auto-expanded by the LLM. The SDK also allows for "pre-expanded queries" to skip this automatic step.
*   **QMD SDK (`store.expandQuery()` method)**: Allows manual query expansion for granular control over the generated variants.

## Related Concepts
*   [[wiki/concepts/qmd]]
*   [[wiki/concepts/bm25]]
*   [[wiki/concepts/vector-semantic-search]]
*   [[wiki/concepts/llm-reranking]]
*   [[wiki/concepts/reciprocal-rank-fusion]]
*   [[wiki/concepts/gguf-models]]
*   [[wiki/services/node-llama-cpp]]
*   [[wiki/concepts/large-language-model]]