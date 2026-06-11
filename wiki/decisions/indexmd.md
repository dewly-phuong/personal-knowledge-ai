---
source_urls:
  - "file:///home/phun/workspace/dewly/python/personal-knowledge-ai/raw/local/llm-wiki.md"
last_updated: "2026-06-11T06:55:29.692636+00:00"
entities:
  - "indexmd"
---
# index.md

The `index.md` file is a special, content-oriented page within an [[wiki/concepts/llm-wiki|LLM Wiki]] that serves as a comprehensive catalog for all wiki content. It helps both the LLM and human users navigate the wiki efficiently as it grows.

## Purpose and Function

The primary purpose of `index.md` is to provide a structured overview and navigation aid. It lists every page in the wiki, typically including:
*   A link to each page.
*   A concise, one-line summary for each page.
*   Optional metadata such as the date of creation or the count of source documents contributing to that page.

## Structure and Organization

The content within `index.md` is organized by category (e.g., entities, concepts, sources, etc.). The LLM is responsible for maintaining and updating `index.md` with every new source ingestion or page modification.

## Role in Querying

When an LLM processes a query, it can first consult `index.md` to identify and retrieve relevant pages, before drilling down into the specific content of those pages. This approach has proven effective for moderately scaled wikis (around 100 sources and hundreds of pages), often negating the immediate need for embedding-based RAG infrastructure.

## Relationship to [[wiki/log.md]]

While `index.md` is content-oriented, its counterpart, `[[wiki/log.md]]`, is chronological, serving as an append-only record of wiki operations such as ingests, queries, and lint passes. Together, these two special files help the LLM maintain and understand the wiki's evolution.