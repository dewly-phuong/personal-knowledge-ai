---
source_urls:
  - "file:///home/phun/workspace/dewly/python/personal-knowledge-ai/raw/local/qmd.md"
last_updated: "2026-06-11T07:33:33.318315+00:00"
entities:
  - "reciprocal-rank-fusion-rrf"
---
# Reciprocal Rank Fusion (RRF)

Reciprocal Rank Fusion (RRF) is a method used within the [[wiki/services/qmd|QMD]] hybrid search pipeline to combine multiple ranked lists of search results into a single, consolidated list. It is particularly effective for merging results from diverse search backends, such as [[wiki/concepts/bm25|BM25 full-text search]] and [[wiki/concepts/vector-semantic-search|vector semantic search]], while mitigating the impact of outlier scores from individual systems.

## Mechanism

In [[wiki/services/qmd|QMD]], RRF is applied after [[wiki/concepts/query-expansion|query expansion]] and parallel retrieval from both FTS (BM25) and vector indexes. Each query (original and expanded variants) contributes its FTS and vector results to the RRF process.

The RRF score for a document is calculated using the formula: `score = Σ(1/(k+rank+1))`, where `k` is a constant (set to `60` in QMD) and `rank` is the position of the document in a specific result list. The summation occurs across all result lists in which the document appears.

### Fusion Strategy Steps

1.  **Query Expansion**: The original user query is expanded (via an LLM) into one or more alternative queries. The original query is given a `2x` weighting.
2.  **Parallel Retrieval**: Each query (original and expanded variants) is run against both FTS (BM25) and vector indexes, generating multiple ranked lists.
3.  **RRF Fusion**: All generated result lists are combined using the RRF formula (`score = Σ(1/(k+rank+1))`, with `k=60`).
4.  **Top-Rank Bonus**: Documents that rank #1 in any individual list receive an additional `+0.05` score bonus. Documents ranking #2 or #3 receive a `+0.02` bonus. This helps preserve high-confidence exact matches from individual backends.
5.  **Candidate Selection**: The top 30 candidates after RRF fusion (and bonuses) are selected for further processing.
6.  **LLM Re-ranking**: These candidates are then passed to an [[wiki/concepts/llm-re-ranking|LLM re-ranker]] (e.g., using `qwen3-reranker-0.6b-q8_0` [[wiki/concepts/gguf-models|GGUF model]]) to refine their relevance scores.
7.  **Position-Aware Blending**: The final score is a blend of the RRF score and the LLM re-ranker's score, with the blending ratio adjusted based on the RRF rank:
    *   **RRF rank 1-3**: 75% RRF (retrieval score), 25% reranker score. This prioritizes strong retrieval matches.
    *   **RRF rank 4-10**: 60% RRF, 40% reranker.
    *   **RRF rank 11+**: 40% RRF, 60% reranker. This trusts the LLM re-ranker more for lower-ranked results where initial retrieval confidence might be lower.

## Rationale

The use of RRF with specific weighting and blending strategies addresses limitations of pure RRF and individual search backends:

*   **Preserving Exact Matches**: Pure RRF can sometimes dilute the scores of exact matches when expanded queries do not perfectly align. The top-rank bonus helps ensure documents that are a perfect match for the original query in any single backend retain a strong position.
*   **Balancing Retrieval and Reranking**: The position-aware blending strategy prevents the LLM re-ranker from entirely overturning high-confidence retrieval results while still leveraging its semantic understanding to improve the ranking of less obvious matches.
*   **Robustness**: By fusing multiple sources, RRF provides a more robust and comprehensive ranking, benefiting from the strengths of both keyword-based and semantic search.