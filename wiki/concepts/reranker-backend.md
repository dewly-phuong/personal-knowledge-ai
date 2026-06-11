yaml
---
source_urls:
  - "file:///home/phun/workspace/dewly/python/personal-knowledge-ai/raw/local/qmd.md"
last_updated: "2026-06-11T07:34:16.180012+00:00"
entities:
  - "reranker-backend"
---
# Reranker Backend

## Technical Definition
The Reranker Backend is a core component of the [[wiki/concepts/qmd]] hybrid search pipeline, responsible for refining search results using a Large Language Model (LLM). It performs a second-stage ranking of candidate documents retrieved by initial search methods (like [[wiki/concepts/bm25]] and [[wiki/concepts/vector-semantic-search]]) to improve overall relevance and quality.

## Architectural Design
In the [[wiki/concepts/qmd]] hybrid search pipeline, the Reranker Backend operates after the [[wiki/concepts/rrf-fusion]] step. It takes the top 30 candidates from the RRF fusion and uses a local [[wiki/concepts/gguf-models]] (specifically `qwen3-reranker-0.6b-q8_0`) via [[wiki/services/node-llama-cpp]] to score each document for relevance.

The reranker model provides a binary (yes/no) decision with logprob confidence, which is then converted into a 0.0-1.0 relevance score. This reranker score is blended with the initial RRF scores using a position-aware strategy:
*   **RRF rank 1-3**: 75% retrieval (RRF), 25% reranker.
*   **RRF rank 4-10**: 60% retrieval (RRF), 40% reranker.
*   **RRF rank 11+**: 40% retrieval (RRF), 60% reranker.

This blending strategy prioritizes high-confidence initial matches while giving more weight to the reranker for lower-ranked candidates, preventing the LLM from entirely discarding strong keyword or semantic matches.

### Model Details
*   **Purpose**: Re-ranking search results.
*   **Model Name**: `qwen3-reranker-0.6b-q8_0`
*   **Size**: Approximately 640MB.
*   **Implementation**: Utilizes `node-llama-cpp`'s `createRankingContext()` and `rankAndSort()` API for cross-encoder reranking.
*   **Raw Score Conversion**: LLM's 0-10 rating is converted to `score / 10`, ranging from 0.0 to 1.0.

## Consumers
The Reranker Backend is primarily consumed by the following components and interfaces within [[wiki/concepts/qmd]]:
*   **`qmd query` command**: The command-line interface's hybrid search mode (e.g., `qmd query "user authentication"`) uses the reranker by default. It can be optionally disabled with the `--no-rerank` flag for faster, RRF-only results.
*   **[[wiki/services/mcp-server]]**: The `query` tool exposed by the MCP server (used by agents like Claude Desktop or Claude Code) integrates the reranker.
*   **SDK / Library Usage**: Developers using the [[wiki/concepts/qmd-sdk]] in Node.js or Bun applications can leverage the reranker via the `store.search({ query: "...", rerank: true })` method.

## Related Concepts
*   [[wiki/concepts/qmd]]
*   [[wiki/concepts/hybrid-search]]
*   [[wiki/concepts/llm-re-ranking]]
*   [[wiki/concepts/rrf-fusion]]
*   [[wiki/concepts/gguf-models]]
*   [[wiki/services/node-llama-cpp]]
*   [[wiki/concepts/query-expansion]]
*   [[wiki/concepts/vector-semantic-search]]
*   [[wiki/concepts/bm25]]