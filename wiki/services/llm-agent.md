---
source_urls:
  - "file:///home/phun/workspace/dewly/python/personal-knowledge-ai/raw/local/llm-wiki.md"
last_updated: "2026-06-11T06:53:53.119005+00:00"
entities:
  - "llm-agent"
---
# LLM Agent

## Purpose

The LLM Agent is a conceptual service pattern designed for building and maintaining a personal or team [[wiki/concepts/knowledge-base]]. Unlike traditional [[wiki/concepts/rag]] systems that retrieve information from raw documents at query time, an LLM Agent incrementally builds and maintains a persistent, structured, and interlinked collection of markdown files. This wiki acts as a compounding artifact, accumulating knowledge, synthesizing information, and flagging contradictions over time, powered entirely by the LLM.

## Architecture

The LLM Agent operates across three distinct layers:

1.  **Raw Sources**: A curated collection of immutable source documents (articles, papers, images, data files). The LLM reads from these but never modifies them.
2.  **The Wiki**: A directory of LLM-generated markdown files, including summaries, entity pages, concept pages, comparisons, and an overview. The LLM owns this layer, creating, updating, and maintaining cross-references and consistency.
3.  **The Schema**: A configuration document (e.g., `CLAUDE.md`, `AGENTS.md`) that defines the wiki's structure, conventions, and workflows for ingestion, querying, and maintenance. This file co-evolves with the user and the LLM.

## Operations

The LLM Agent performs several key operations:

*   **Ingest**: Processes new source documents by reading them, extracting key information, writing summary pages, updating relevant entity and concept pages, and appending entries to a log. A single source may impact multiple wiki pages.
*   **Query**: Responds to user queries by searching relevant wiki pages, synthesizing answers, and providing citations. Importantly, valuable answers (e.g., comparisons, analyses) can be filed back into the wiki as new pages, allowing explorations to compound.
*   **Lint**: Periodically health-checks the wiki for inconsistencies such as contradictions, stale claims, orphan pages, missing cross-references, and data gaps, often suggesting new areas for investigation.

## Indexing and Logging

To facilitate navigation and tracking, the LLM Agent maintains two special files:

*   **`index.md`**: A content-oriented catalog of all wiki pages, organized by category, with links and one-line summaries. The LLM updates this on every ingest and uses it to find relevant pages during queries.
*   **`log.md`**: A chronological, append-only record of all operations, including ingests, queries, and lint passes, providing a timeline of the wiki's evolution.

## Dependencies

The LLM Agent relies on:

*   **Raw Sources**: The initial input documents.
*   **The Wiki Structure**: The defined markdown file system and linking conventions.
*   **The Schema**: The guiding rules for wiki maintenance.
*   **Underlying LLM**: A large language model capable of text generation, summarization, and instruction following (e.g., [[wiki/services/openai-codex]], [[wiki/services/claude-code]], OpenCode, Pi).

### Tools Utilized by the LLM Agent

While the LLM Agent itself is a pattern, it can leverage various tools for enhanced functionality:

*   **[[wiki/concepts/obsidian]]**: A markdown knowledge base application, often used as the interface for humans to browse and interact with the wiki.
    *   **Obsidian Web Clipper**: Browser extension for converting web articles to markdown.
    *   **Graph View**: Visualizes connections between wiki pages.
    *   **[[wiki/concepts/marp]]**: An Obsidian plugin for generating slide decks from markdown.
    *   **[[wiki/concepts/dataview]]**: An Obsidian plugin for querying page [[wiki/concepts/yaml-front-matter]] metadata.
*   **[[wiki/concepts/git]]**: Used for version history, branching, and collaboration on the wiki, which is essentially a repository of markdown files.
*   **CLI tools**: External tools like `qmd` (a local search engine for markdown) can be integrated for efficient searching at scale.

## Benefits

The primary advantage of an LLM Agent is its ability to offload the "bookkeeping" burden of knowledge base maintenance. LLMs excel at tasks like updating cross-references, keeping summaries current, noting contradictions, and maintaining consistency across numerous pages, tasks that often lead to human abandonment of wikis. This allows humans to focus on curating sources, directing analysis, asking insightful questions, and deeper strategic thinking.

## Related Concepts

The idea of an LLM-maintained wiki aligns in spirit with Vannevar Bush's 1945 concept of the [[wiki/concepts/memex]], a personal, curated knowledge store with associative trails, where the LLM addresses the critical challenge of maintenance that Bush could not solve.