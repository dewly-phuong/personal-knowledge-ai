---
source_urls:
  - "file:///home/phun/workspace/dewly/python/personal-knowledge-ai/raw/local/llm-wiki.md"
last_updated: "2026-06-11T06:54:18.979134+00:00"
entities:
  - "raw-sources"
---
# Raw Sources

## Description
Raw sources refer to a curated collection of original source documents that serve as the foundational immutable knowledge for an [[wiki/concepts/llm-wiki]] system. These can include articles, papers, images, data files, podcast notes, journal entries, meeting transcripts, project documents, and customer calls. The LLM reads from these sources but never modifies them, establishing them as the ultimate source of truth.

## Role in the LLM Wiki Pattern
In the [[wiki/concepts/llm-wiki]] architecture, raw sources constitute the first of three layers:
1.  **Raw sources**: The immutable collection of original documents.
2.  **[[wiki/concepts/the-wiki|The Wiki]]**: An LLM-generated and maintained directory of structured, interlinked markdown files, acting as a persistent and compounding artifact of knowledge.
3.  **[[wiki/concepts/the-schema|The Schema]]**: A configuration document that guides the LLM on wiki structure, conventions, and workflows.

When new raw sources are added, the LLM [[wiki/concepts/ingest|ingests]] them by extracting key information and integrating it into the existing wiki, updating relevant entity and concept pages, noting contradictions, and maintaining cross-references.

## Characteristics
*   **Immutability**: Raw sources are never modified by the LLM. They remain in their original state.
*   **Foundation of Truth**: They are the primary and most authoritative information layer, from which all wiki content is derived.
*   **Curated Collection**: Users are responsible for curating and providing these sources to the LLM.

## Operations Involving Raw Sources
*   **Ingest**: The process by which the LLM reads a new raw source, synthesizes its content, and integrates it into the [[wiki/concepts/the-wiki|wiki]]. This involves writing summaries, updating [[wiki/concepts/entity-pages|entity pages]], and cross-referencing.
*   **Query**: While queries are primarily directed at the wiki, the LLM's answers are ultimately grounded in information derived from raw sources.
*   **Lint**: The LLM may identify data gaps in the wiki that could be filled by looking for new raw sources.