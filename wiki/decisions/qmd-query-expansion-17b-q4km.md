---
source_urls:
  - "file:///home/phun/workspace/dewly/python/personal-knowledge-ai/raw/local/qmd.md"
last_updated: "2026-06-11T07:34:57.489422+00:00"
entities:
  - "qmd-query-expansion-17b-q4km"
---
# QMD-Query-Expansion-1.7B-Q4_K_M

The `qmd-query-expansion-1.7B-q4_k_m` is a fine-tuned GGUF model primarily utilized by the [[wiki/services/qmd]] (Query Markup Documents) search engine for query expansion. It is one of three local GGUF models automatically downloaded and managed by QMD for its advanced search capabilities.

## Purpose and Role

This model's main function is to generate alternative query variations from an original user query. This expansion is a crucial step in [[wiki/services/qmd]]'s hybrid search pipeline, enhancing retrieval effectiveness by providing more diverse search vectors and keywords for the subsequent BM25 and vector searches.

## Technical Details

*   **Type**: GGUF model
*   **Size**: Approximately 1.1 GB
*   **Usage**: Integrated into [[wiki/services/qmd]] via [[wiki/concepts/node-llama-cpp]]'s `LlamaChatSession` API for generating query variations.
*   **Source**: HuggingFace (`hf:tobil/qmd-query-expansion-1.7B-gguf/qmd-query-expansion-1.7B-q4_k_m.gguf`)
*   **Integration**: It's configured as the `DEFAULT_GENERATE_MODEL` within QMD's model configuration.

## QMD Hybrid Search Pipeline Integration

In the [[wiki/services/qmd]] hybrid search flow, the `qmd-query-expansion-1.7B-q4_k_m` model performs the initial "LLM Expansion" step. It takes the user's query and produces additional query variants, which are then used alongside the original query for parallel retrieval across BM25 and vector search backends. This step significantly contributes to the "best quality" results offered by the `qmd query` command by improving the breadth and depth of the initial search phase before RRF fusion and LLM re-ranking.