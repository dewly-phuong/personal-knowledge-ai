---
source_urls:
  - "file:///home/phun/workspace/dewly/python/personal-knowledge-ai/raw/local/qmd.md"
last_updated: "2026-06-11T07:32:18.829588+00:00"
entities:
  - "gguf-models"
---
# GGUF Models

GGUF models are a file format for storing and distributing large language models, specifically designed for efficient local inference using tools like `llama.cpp` and its Node.js binding, [[wiki/concepts/node-llama-cpp]]. They are crucial for enabling local, on-device AI capabilities without relying on remote API calls.

## Purpose and Usage

In the context of [[wiki/services/qmd]], GGUF models are central to its hybrid search capabilities, running entirely locally. They are utilized for:
*   **Vector Embeddings**: Generating semantic representations of document chunks for [[wiki/concepts/vector-semantic-search]].
*   **LLM Re-ranking**: Refining search results by using an LLM to assess relevance, improving overall quality.
*   **Query Expansion**: Expanding user queries with variations to enhance retrieval accuracy.

## Models Used by QMD

[[wiki/services/qmd]] automatically downloads and caches the following GGUF models from [[wiki/concepts/huggingface]] to `~/.cache/qmd/models/` on first use:

*   **`embeddinggemma-300M-Q8_0`**:
    *   **Purpose**: Default model for generating vector embeddings.
    *   **Size**: Approximately 300MB.
    *   **Prompt Format (for queries)**: `"task: search result | query: {query}"`
    *   **Prompt Format (for documents)**: `"title: {title} | text: {content}"`
*   **`qwen3-reranker-0.6b-q8_0`**:
    *   **Purpose**: Used for LLM-based re-ranking of search results.
    *   **Size**: Approximately 640MB.
    *   **Mechanism**: Employs `node-llama-cpp`'s `createRankingContext()` and `rankAndSort()` API for cross-encoder reranking.
*   **`qmd-query-expansion-1.7B-q4_k_m`**:
    *   **Purpose**: A fine-tuned model specifically for generating query variations ([[wiki/concepts/query-expansion]]).
    *   **Size**: Approximately 1.1GB.
    *   **Mechanism**: Used with `LlamaChatSession` for dynamic query expansion.

## Configuration and Customization

Users can customize the embedding model used by [[wiki/services/qmd]] by setting the `QMD_EMBED_MODEL` environment variable. This is particularly useful for multilingual corpora or specialized use cases.

**Supported Embedding Model Families**:
*   **`embeddinggemma`** (default): English-optimized, small footprint.
*   **`Qwen3-Embedding`**: Multilingual (119 languages including CJK), MTEB top-ranked.

**Important Note**: When switching embedding models, it is crucial to re-embed all collections using `qmd embed -f`, as vector embeddings are not cross-compatible between different models. The prompt format is automatically adjusted for the chosen model family.

## System Requirements

The use of GGUF models relies on `node-llama-cpp` and its underlying `llama.cpp` library. Key environment variables for performance and compatibility include:

*   `QMD_LLAMA_GPU`: Allows forcing a specific [[wiki/concepts/gpu-backend]] (`metal`, `vulkan`, `cuda`) or disabling GPU with `false`.
*   `QMD_FORCE_CPU`: Set to `1` or `true` to explicitly force CPU mode, bypassing GPU probing.
*   `QMD_EMBED_PARALLELISM`: Overrides the automatic parallelism for embedding/reranking contexts (range 1-8). On Windows, CUDA parallelism defaults to 1 due to potential stability issues.