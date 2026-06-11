---
source_urls:
  - "file:///home/phun/workspace/dewly/python/personal-knowledge-ai/raw/local/qmd.md"
last_updated: "2026-06-11T07:34:30.133119+00:00"
entities:
  - "embeddinggemma-300m-q80"
---
# EmbeddingGemma-300M-Q8_0

The `embeddinggemma-300M-Q8_0` model is a local GGUF model primarily used by the [[wiki/concepts/qmd]] search engine for generating vector embeddings. It is designed for efficient on-device semantic search.

## Purpose

This model serves as the default embedding model for [[wiki/concepts/qmd]], converting document chunks and queries into vector representations that enable semantic similarity search.

## Details

*   **Type**: GGUF Model
*   **Size**: Approximately 300MB
*   **Source**: Auto-downloaded from HuggingFace (`ggml-org/embeddinggemma-300M-GGUF`) upon first use by [[wiki/concepts/qmd]].
*   **Characteristics**: English-optimized, small footprint.
*   **Runtime**: Utilizes [[wiki/concepts/node-llama-cpp]] for local execution.

## Usage in QMD

The `embeddinggemma-300M-Q8_0` model is automatically loaded by [[wiki/concepts/qmd]] to perform embedding tasks. It processes document chunks and queries to facilitate hybrid search.

### Custom Embedding Model

The default `embeddinggemma-300M` can be overridden by setting the `QMD_EMBED_MODEL` environment variable. This is particularly useful for multilingual corpora, where models like `Qwen3-Embedding-0.6B` offer broader language coverage (e.g., CJK languages).

```sh
export QMD_EMBED_MODEL="hf:Qwen/Qwen3-Embedding-0.6B-GGUF/Qwen3-Embedding-0.6B-Q8_0.gguf"
qmd embed -f # Re-embed all collections after changing the model
```

**Note**: When switching embedding models, a full re-embedding with `qmd embed -f` is required, as vector representations are not cross-compatible between different models. The prompt format is automatically adjusted by [[wiki/concepts/qmd]] for the selected model family.

## Prompt Format

For optimal performance with `embeddinggemma-300M-Q8_0`, [[wiki/concepts/qmd]] uses specific prompt formats for queries and documents:

*   **For queries**: `"task: search result | query: {query}"`
*   **For documents**: `"title: {title} | text: {content}"`

## Related

*   [[wiki/concepts/qmd]]
*   [[wiki/concepts/qwen3-reranker-06b-q8_0]]
*   [[wiki/concepts/qmd-query-expansion-17b-q4_k_m]]
*   [[wiki/concepts/gguf]]
*   [[wiki/concepts/node-llama-cpp]]
*   [[wiki/concepts/huggingface]]