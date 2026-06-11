yaml
---
source_urls:
  - "file:///home/phun/workspace/dewly/python/personal-knowledge-ai/raw/local/llm-wiki.md"
last_updated: "2026-06-11T06:53:40.688519+00:00"
entities:
  - "llm-wiki"
---
# LLM Wiki

A pattern for building personal knowledge bases using [[wiki/concepts/llm]]s, where an LLM incrementally builds and maintains a persistent, structured, and interlinked collection of markdown files. Unlike traditional [[wiki/concepts/retrieval-augmented-generation|RAG]] systems that retrieve from raw documents at query time, the LLM Wiki compiles knowledge once and keeps it current, accumulating and synthesizing information over time.

## Core Idea

The central premise is that the [[wiki/concepts/llm]] acts as a disciplined wiki maintainer, taking raw source documents and integrating their key information into an existing wiki. This involves updating entity pages, revising topic summaries, flagging contradictions, and strengthening or challenging the evolving synthesis. The wiki becomes a persistent, compounding artifact where knowledge is compiled and maintained by the LLM, rather than re-derived on every query.

The human user's role is primarily sourcing, exploration, and asking questions, while the LLM handles summarizing, cross-referencing, filing, and bookkeeping. The wiki is typically browsed using tools like [[wiki/concepts/obsidian]], which serves as an IDE for the LLM's "codebase" (the wiki content).

### Applications

This pattern can be applied to various contexts:
*   **Personal**: Tracking goals, health, psychology, self-improvement by filing journal entries, articles, and podcast notes.
*   **Research**: Deep dives into topics, incrementally building comprehensive wikis from papers, articles, and reports.
*   **Reading a book**: Creating companion wikis with pages for characters, themes, and plot threads as chapters are read.
*   **Business/Team**: Internal knowledge bases fed by Slack threads, meeting transcripts, and project documents, maintained by [[wiki/concepts/llm]]s.
*   **Other**: Competitive analysis, due diligence, trip planning, course notes, and hobby deep-dives.

## Architecture

The LLM Wiki architecture comprises three distinct layers:

1.  **Raw Sources**: Curated collection of immutable source documents (articles, papers, images, data files). The [[wiki/concepts/llm]] reads from these but never modifies them; they are the source of truth.
2.  **The Wiki**: A directory of [[wiki/concepts/llm]]-generated markdown files (summaries, entity pages, concept pages, comparisons, overviews, synthesis). The LLM owns this layer, creating and updating pages, maintaining cross-references, and ensuring consistency.
3.  **The Schema**: A configuration document that dictates how the wiki is structured, specifies conventions, and outlines workflows for ingestion, querying, and maintenance. This document enables the [[wiki/concepts/llm]] to act as a disciplined wiki maintainer.

## Operations

### Ingest
The process of adding a new source document to the wiki. The [[wiki/concepts/llm]] reads the source, extracts key takeaways, writes a summary page, updates the index, modifies relevant entity and concept pages, and appends an entry to the log. A single source may affect numerous wiki pages. The user can supervise this process, guiding the LLM on what to emphasize, or batch-ingest multiple sources with less oversight.

### Query
Asking questions against the wiki. The [[wiki/concepts/llm]] searches for relevant pages, synthesizes an answer with citations. Answers can take various forms (markdown, comparison tables, slide decks using [[wiki/concepts/marp]], charts) and, importantly, can be filed back into the wiki as new pages, allowing explorations to compound the knowledge base.

### Lint
A periodic health-check where the [[wiki/concepts/llm]] identifies contradictions, stale claims, orphan pages, missing cross-references, and data gaps. The LLM can also suggest new questions or sources to investigate, ensuring the wiki remains healthy and up-to-date.

## Indexing and Logging

Two special files (`index.md` and `log.md`) assist in navigating and tracking the wiki's evolution:

*   **index.md**: A content-oriented catalog of all wiki pages, each with a link, a one-line summary, and optional metadata. Organized by category, the [[wiki/concepts/llm]] updates it on every ingest and uses it to find relevant pages during queries, serving as a simple search mechanism at moderate scale.
*   **log.md**: A chronological, append-only record of all wiki operations (ingests, queries, lint passes). Consistent entry prefixes make it parseable, providing a timeline of the wiki's development and helping the LLM understand recent activities.

## Optional Tools

As the wiki grows, various tools can enhance efficiency:

*   **CLI Search Engines**: Tools like `qmd` (a local search engine for markdown) can provide advanced search capabilities beyond what `index.md` offers, using hybrid BM25/vector search and LLM re-ranking.
*   **Obsidian Web Clipper**: A browser extension to convert web articles into markdown, simplifying source ingestion.
*   **Image Management**: Downloading images locally allows the [[wiki/concepts/llm]] to view and reference them directly, though native LLM handling of inline images in markdown may require workarounds.
*   **Obsidian Graph View**: Visualizes the interconnections within the wiki, revealing relationships and identifying hubs or orphans.
*   **Marp**: A markdown-based slide deck format, usable via an [[wiki/concepts/obsidian]] plugin, for generating presentations from wiki content.
*   **Dataview**: An [[wiki/concepts/obsidian]] plugin that queries page frontmatter, enabling dynamic tables and lists based on metadata like tags, dates, and source counts.

## Advantages

The primary advantage of the LLM Wiki pattern is that the [[wiki/concepts/llm]] handles the tedious bookkeeping associated with maintaining a knowledge base. Tasks like updating cross-references, keeping summaries current, noting contradictions, and maintaining consistency, which often lead humans to abandon wikis, are performed efficiently by the LLM. This near-zero maintenance cost allows the wiki to stay continually updated and enriched.

The human role shifts from maintenance to curating sources, directing analysis, asking insightful questions, and synthesizing meaning, while the LLM manages the structural and organizational aspects. The concept shares a spirit with Vannevar Bush's [[wiki/concepts/memex]], addressing the maintenance challenge that Bush's original vision couldn't solve.

## Note on Implementation

This pattern is intentionally abstract. The specific directory structure, schema conventions, page formats, and tooling are highly adaptable to the user's domain, preferences, and chosen [[wiki/concepts/llm]]. The components mentioned are modular and optional, allowing for customization. The document's purpose is to communicate the core pattern, enabling the LLM agent to instantiate a tailored version collaboratively with the user.