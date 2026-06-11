---
source_urls:
  - "file:///home/phun/workspace/dewly/python/personal-knowledge-ai/raw/local/llm-wiki.md"
last_updated: "2026-06-11T06:54:09.620708+00:00"
entities:
  - "retrieval-augmented-generation"
---
# Retrieval Augmented Generation

## Technical Definition
Retrieval Augmented Generation (RAG) is a widely adopted pattern for building applications with Large Language Models (LLMs). In a RAG system, an LLM retrieves relevant information from a collection of raw documents at query time and then uses this retrieved context to generate an answer. This allows LLMs to leverage external, up-to-date, or proprietary knowledge beyond their initial training data.

## Architectural Design
The core mechanism of RAG involves:
1.  **Document Indexing**: A collection of source documents (e.g., articles, papers, internal files) is typically processed and indexed. This often includes converting text into numerical embeddings, enabling efficient semantic search.
2.  **Retrieval**: Upon receiving a user query, the system identifies and extracts relevant chunks or fragments of information from the indexed documents based on the query's content.
3.  **Augmentation and Generation**: These retrieved document fragments are then prepended or injected into the prompt provided to the LLM, effectively "augmenting" the LLM's context. The LLM then synthesizes an answer based on its internal knowledge and the provided external information.

## Characteristics and Limitations
*   **On-Demand Knowledge**: In RAG, the LLM rediscovers knowledge from raw documents on every query.
*   **Lack of Accumulation**: A common characteristic of many RAG systems is the absence of knowledge accumulation. The LLM processes the relevant fragments for each query without building a persistent, compounding understanding or structured knowledge base. This can mean that synthesizing complex answers from multiple documents requires the LLM to re-evaluate and piece together fragments every time.
*   **Examples**: Systems like NotebookLM, ChatGPT file uploads, and many general-purpose RAG implementations operate on this principle, providing direct retrieval and generation without an intermediate, evolving knowledge layer.

## Related Concepts
This pattern is often contrasted with approaches like the [[wiki/concepts/llm-wiki|LLM Wiki]], which focuses on LLMs incrementally building and maintaining a persistent, structured, and interlinked knowledge base that accumulates and synthesizes information over time.