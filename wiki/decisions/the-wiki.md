---
source_urls:
  - "file:///home/phun/workspace/dewly/python/personal-knowledge-ai/raw/local/llm-wiki.md"
last_updated: "2026-06-11T06:54:25.869896+00:00"
entities:
  - "the-wiki"
---
# The Wiki

"The Wiki" (also referred to as "LLM Wiki") is a pattern for building and maintaining personal knowledge bases using Large Language Models ([[wiki/concepts/llm]]). Unlike traditional Retrieval Augmented Generation ([[wiki/concepts/rag]]) systems where an [[wiki/concepts/llm]] retrieves knowledge from raw documents at query time, this approach involves the [[wiki/concepts/llm]] incrementally building and maintaining a persistent, structured, and interlinked collection of markdown files.

The core idea is that knowledge is compiled once and then kept current by the [[wiki/concepts/llm]], rather than being re-derived on every query. The wiki becomes a persistent, compounding artifact where cross-references are maintained, contradictions are flagged, and synthesis reflects all ingested sources. Humans primarily curate sources, direct analysis, and ask questions, while the [[wiki/concepts/llm]] handles the summarizing, cross-referencing, filing, and bookkeeping.

## Applications

This pattern can be applied to various contexts, including:
*   **Personal**: Tracking goals, health, psychology, and self-improvement by filing journal entries, articles, and podcast notes.
*   **Research**: Deep-diving on a topic over time by ingesting papers, articles, and reports to build a comprehensive wiki with an evolving thesis.
*   **Reading a book**: Building companion wikis for characters, themes, and plot threads as chapters are read.
*   **Business/Team**: Creating an internal wiki fed by Slack threads, meeting transcripts, project documents, and customer calls, with potential human review loops.
*   **Other**: Competitive analysis, due diligence, trip planning, course notes, and hobby deep-dives.

## Architecture

The architecture consists of three distinct layers:

1.  **Raw Sources**: This layer comprises curated collections of source documents (articles, papers, images, data files). These are immutable and serve as the ultimate source of truth, from which the [[wiki/concepts/llm]] reads but never modifies.
2.  **The Wiki**: This is a directory of [[wiki/concepts/llm]]-generated markdown files, including summaries, entity pages, concept pages, comparisons, and overviews. The [[wiki/concepts/llm]] solely owns this layer, creating pages, updating them with new sources, maintaining cross-references, and ensuring consistency.
3.  **The Schema**: A document (e.g., `CLAUDE.md` or `AGENTS.md`) that instructs the [[wiki/concepts/llm]] on the wiki's structure, conventions, and workflows for ingestion, query answering, and maintenance. This configuration file is co-evolved by the user and the [[wiki/concepts/llm]].

## Operations

Key operations for maintaining and interacting with The Wiki include:

*   **Ingest**: Processing new source documents. The [[wiki/concepts/llm]] reads the source, extracts key takeaways, writes a summary page, updates an index, modifies relevant entity and concept pages across the wiki, and appends an entry to a chronological log. A single source may affect multiple wiki pages.
*   **Query**: Asking questions against the wiki. The [[wiki/concepts/llm]] searches for and synthesizes answers from relevant pages, providing citations. Important insights from queries (e.g., comparisons, analyses) can be filed back into the wiki as new pages, allowing explorations to compound the knowledge base.
*   **Lint**: Periodically health-checking the wiki for contradictions, stale claims, orphan pages, missing cross-references, and data gaps. The [[wiki/concepts/llm]] can suggest new questions or sources to investigate.

## Indexing and Logging

Two special files aid in navigating and tracking the wiki's evolution:

*   **index.md**: A content-oriented catalog of all wiki pages, each listed with a link, a one-line summary, and optional metadata. It is organized by category (entities, concepts, sources) and updated on every ingest. The [[wiki/concepts/llm]] uses it to find relevant pages for queries, reducing the need for embedding-based [[wiki/concepts/rag]] at moderate scales.
*   **log.md**: An append-only, chronological record of all actions, such as ingests, queries, and lint passes. Consistent prefixes for log entries enable easy parsing and provide a timeline of the wiki's evolution.

## Optional Tools and Tips

*   **CLI Tools**: For larger wikis, tools like a search engine (e.g., [[wiki/concepts/qmd]]) can improve efficiency. The [[wiki/concepts/llm]] can interact with such tools via a command-line interface or a server.
*   **Obsidian Web Clipper**: A browser extension to convert web articles into markdown for easy ingestion. [[wiki/concepts/obsidian]] can serve as the IDE for browsing the wiki.
*   **Image Handling**: Downloading images locally can allow the [[wiki/concepts/llm]] to view and reference them, although [[wiki/concepts/llm]]s may require a multi-step process for integrating image context with text.
*   **Obsidian's Graph View**: Visualizes connections between pages, helping identify hubs and orphans.
*   **Marp**: A markdown-based slide deck format, supported by an [[wiki/concepts/obsidian]] plugin, for generating presentations directly from wiki content.
*   **Dataview**: An [[wiki/concepts/obsidian]] plugin that queries page frontmatter, enabling dynamic tables and lists based on metadata.
*   **Git**: The wiki, being a collection of markdown files, can be managed as a [[wiki/concepts/git]] repository, providing version history, branching, and collaboration capabilities.

## Rationale

The effectiveness of The Wiki pattern stems from offloading the tedious "bookkeeping" aspects of knowledge management to an [[wiki/concepts/llm]]. Humans often abandon wikis due to the escalating maintenance burden. [[wiki/concepts/llm]]s, however, do not get bored, forget to update cross-references, or hesitate to modify multiple files in a single pass. This reduces the cost of maintenance to near zero, ensuring the wiki remains current and valuable.

This concept relates in spirit to Vannevar Bush's 1945 vision of the [[wiki/concepts/memex]], a personal, curated knowledge store with associative trails. The [[wiki/concepts/llm]] addresses the challenge Bush couldn't solve: who performs the continuous maintenance of these connections.