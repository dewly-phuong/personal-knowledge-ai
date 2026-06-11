---
source_urls:
  - "file:///home/phun/workspace/dewly/python/personal-knowledge-ai/raw/local/llm-wiki.md"
  - "file:///home/phun/workspace/dewly/python/personal-knowledge-ai/raw/local/qmd.md"
last_updated: "2026-06-11T07:30:54Z"
entities:
  - "qmd"
---
# QMD - Query Markup Documents

## Purpose
QMD (Query Markup Documents) is an on-device search engine designed to index and query diverse markdown-based knowledge bases, including notes, meeting transcripts, documentation, and general knowledge bases. It aims to facilitate efficient navigation and retrieval for users and [[wiki/concepts/llm-agent]] workflows, enhancing search capabilities beyond simple file navigation as a knowledge base grows.

## Overview
QMD combines advanced search techniques with local LLM capabilities to provide a powerful, private, and efficient search experience. It is optimized for agentic flows, offering structured output formats and a robust API for programmatic access.

## Key Features

### Search Capabilities
*   **Hybrid Search**: Leverages a sophisticated blend of search technologies for optimal relevance:
    *   **BM25 Full-Text Search**: Fast, keyword-based search using SQLite FTS5.
    *   **Vector Semantic Search**: Utilizes embedding models to find semantically similar content, powered by `sqlite-vec`.
    *   **LLM Re-ranking**: Refines search results using a local LLM to re-score and re-order documents based on deeper contextual understanding.
*   **Query Expansion**: Employs a fine-tuned LLM to automatically expand user queries into multiple variations for comprehensive searching.
*   **Search Modes**: Provides distinct commands for different needs:
    *   `qmd search`: BM25 full-text search only.
    *   `qmd vsearch`: Vector semantic search only.
    *   `qmd query`: Hybrid search (FTS + Vector + Query Expansion + Re-ranking) for best quality.
*   **Context-Aware Search**: Allows adding descriptive metadata to collections and paths, improving search relevance by providing disambiguation context.

### Indexing and Data Management
*   **Collection Management**: Organize source directories (notes, docs, meetings) into named collections with customizable glob patterns.
*   **Smart Chunking**: Documents are intelligently chunked into approximately 900-token pieces with 15% overlap, preserving semantic units (sections, paragraphs, code blocks).
*   **AST-Aware Chunking**: For supported code files (TS, JS, Python, Go, Rust), QMD uses [[wiki/concepts/tree-sitter]] to chunk at AST boundaries (functions, classes, imports), improving code search quality.
*   **Vector Embeddings Generation**: Creates vector embeddings for document chunks, enabling semantic search.
*   **Index Maintenance**: Commands for updating, embedding, and cleaning the index.

### Retrieval
*   **Document Retrieval**: Retrieve specific documents by file path or unique `docid` (e.g., `qmd get "docs/api-reference.md"` or `qmd get "#abc123"`).
*   **Partial Retrieval**: Fetch specific line ranges from documents (e.g., `qmd get "file.md:50:100"`).
*   **Batch Retrieval**: Retrieve multiple documents using glob patterns or a list of paths/docids (`qmd multi-get`).

### Integration & APIs
*   **Command Line Interface (CLI)**: Provides a comprehensive set of commands for direct interaction.
*   **MCP (Model Context Protocol) Server**: Exposes QMD's capabilities as a local service for tighter integration with AI agents and tools (e.g., Claude Desktop, Claude Code). Supports stdio and HTTP transports.
*   **Node.js/Bun SDK**: Available as an npm package (`@tobilu/qmd`) for programmatic integration into custom applications.
*   **Agentic Workflow Support**: Output formats like `--json` and `--files` are designed to provide structured results for [[wiki/concepts/llm-agent]] processing.

## Architecture

### Hybrid Search Pipeline
The `qmd query` command implements a multi-stage hybrid search pipeline:
1.  **Query Expansion**: The initial query is expanded by a fine-tuned LLM into multiple variations (original + 2 alternatives).
2.  **Parallel Retrieval**: Each query variation simultaneously searches both the BM25 (FTS5) and Vector indexes.
3.  **RRF Fusion**: All retrieved result lists are combined using Reciprocal Rank Fusion (RRF), with the original query weighted double. Top-ranking documents receive a bonus.
4.  **LLM Re-ranking**: The top 30 candidates from RRF are passed to a cross-encoder LLM for re-ranking based on semantic relevance (yes/no with logprob confidence).
5.  **Position-Aware Blending**: Final scores are determined by blending RRF and LLM re-ranking scores, with higher RRF ranks (1-3) giving more weight to retrieval and lower ranks trusting the reranker more.

### Indexing and Embedding Flow
1.  **Collection Scan**: Configured directories are scanned for markdown files based on glob patterns.
2.  **Document Processing**: Markdown files are parsed, titles extracted, and content hashed to generate a unique 6-character `docid`.
3.  **Smart Chunking**: Documents are broken into ~900-token chunks with 15% overlap, using a scoring algorithm to find natural break points (headings, code blocks, blank lines). For code files, AST-aware chunking with [[wiki/concepts/tree-sitter]] is used.
4.  **Embedding Generation**: Each formatted chunk (`"title | text"`) is processed by a local embedding model via [[wiki/concepts/node-llama-cpp]], generating vector embeddings.
5.  **Storage**: Document metadata is stored in an [[wiki/concepts/sqlite]] database, and vectors are indexed using `sqlite-vec`.

### Core Technologies
QMD operates fully locally using the following key technologies:
*   **[[wiki/concepts/node-llama-cpp]]**: Powers local execution of GGUF-quantized LLMs for embedding, query expansion, and re-ranking tasks.
*   **[[wiki/concepts/GGUF models]]**: Utilizes specific GGUF models (e.g., `embeddinggemma-300M`, `qwen3-reranker`, `qmd-query-expansion`) for different LLM functionalities.
*   **[[wiki/concepts/sqlite]]**: Serves as the primary data store, leveraging FTS5 for full-text indexing and `sqlite-vec` for vector indexing.
*   **[[wiki/concepts/tree-sitter]]**: Used for AST-aware chunking in supported code files, improving chunk quality for semantic search.

## Requirements

### System Requirements
*   **Node.js**: Version >= 22
*   **Bun**: Version >= 1.0.0
*   **macOS**: Requires Homebrew SQLite for extension support (`brew install sqlite`).

### GGUF Models
QMD automatically downloads three local GGUF models on first use, which are cached in `~/.cache/qmd/models/`:
*   `embeddinggemma-300M-Q8_0` (approx. 300MB) for vector embeddings.
*   `qwen3-reranker-0.6b-q8_0` (approx. 640MB) for LLM re-ranking.
*   `qmd-query-expansion-1.7B-q4_k_m` (approx. 1.1GB) for query expansion.
Custom embedding models can be configured via the `QMD_EMBED_MODEL` environment variable.

## Repository
*   **GitHub**: [https://github.com/tobi/qmd](https://github.com/tobi/qmd)

## Related Entities
*   [[wiki/concepts/llm-wiki]]
*   [[wiki/concepts/llm-agent]]
*   [[wiki/concepts/obsidian]]
*   [[wiki/concepts/retrieval-augmented-generation]]
*   [[wiki/concepts/node-llama-cpp]]
*   [[wiki/concepts/GGUF models]]
*   [[wiki/concepts/tree-sitter]]
*   [[wiki/concepts/sqlite]]