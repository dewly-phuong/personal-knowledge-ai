yaml
---
source_urls:
  - "file:///home/phun/workspace/dewly/python/personal-knowledge-ai/raw/local/qmd.md"
last_updated: "2026-06-11T07:32:02.428685+00:00"
entities:
  - "node-llama-cpp"
---
# Node-llama-cpp

`node-llama-cpp` is a Node.js binding for the `llama.cpp` library, designed to enable the local execution of large language models (LLMs) that are packaged in GGUF format. It serves as a foundational tool for applications requiring on-device LLM capabilities, such as natural language processing, embeddings generation, and model-based re-ranking.

## Architectural Design

As a reusable tool, `node-llama-cpp` is a critical component for applications like [[wiki/services/qmd]] (Query Markup Documents), where it powers all local LLM operations.

### Key Use Cases in QMD

*   **Vector Embeddings**: `node-llama-cpp` is used to generate vector embeddings for document chunks. This is facilitated through its `embedBatch()` API, which is essential for enabling semantic search capabilities.
*   **LLM Re-ranking**: For hybrid search strategies, `node-llama-cpp` provides `createRankingContext()` and `rankAndSort()` APIs. These are utilized for cross-encoder re-ranking of search candidates, improving the relevance of search results.
*   **Query Expansion**: It supports the generation of query variations for enhanced search effectiveness, leveraging `LlamaChatSession` for this purpose.

### Models Utilized

Applications using `node-llama-cpp` rely on specific GGUF models, which are typically auto-downloaded and cached locally upon first use:

*   `embeddinggemma-300M-Q8_0`: The default model for generating vector embeddings.
*   `qwen3-reranker-0.6b-q8_0`: Employed for re-ranking search results.
*   `qmd-query-expansion-1.7B-q4_k_m`: A fine-tuned model used for query expansion.

## Configuration and Environment Variables

`node-llama-cpp`'s behavior can be customized through various environment variables:

*   `QMD_LLAMA_GPU`: This variable allows specifying or forcing a particular GPU backend (e.g., `metal`, `vulkan`, `cuda`). Setting it to `false` disables GPU usage, defaulting to `auto` for automatic detection.
*   `QMD_FORCE_CPU`: When set to `1` or `true`, this variable forces `node-llama-cpp` to operate in CPU-only mode, bypassing any GPU probing.
*   `QMD_EMBED_PARALLELISM`: Controls the level of parallelism for embedding and re-ranking contexts, with an allowed range of 1-8. This can be critical for optimizing performance on systems with varying hardware capabilities.

## System Requirements

To run applications that use `node-llama-cpp`, the following system requirements typically apply:

*   Node.js version 22 or higher.
*   Bun version 1.0.0 or higher.
*   For macOS environments, Homebrew SQLite is recommended to ensure proper support for necessary extensions.