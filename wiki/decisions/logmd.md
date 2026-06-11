---
source_urls:
  - "file:///home/phun/workspace/dewly/python/personal-knowledge-ai/raw/local/llm-wiki.md"
last_updated: "2026-06-11T06:55:45.293429+00:00"
entities:
  - "log"
---
# log.md

`log.md` is a special, chronological, and append-only file within the [[wiki/concepts/llm-wiki]] architecture. It serves as a comprehensive record of significant events and operations performed on the wiki, aiding both human users and the LLM in understanding the wiki's evolution.

## Purpose
The primary purpose of `log.md` is to maintain a timeline of the wiki's development and operational history. It allows the LLM to track recent actions and helps in debugging, auditing, and understanding the context of knowledge accumulation. It ensures transparency of the LLM's actions and provides a historical context for the wiki's knowledge evolution.

## Structure and Contents
Entries in `log.md` document key operations and events, typically including:
*   **Ingestions**: Records when new [[wiki/concepts/sources]] are processed and integrated into the wiki.
*   **Queries**: Logs details about questions asked against the wiki and the generation of answers.
*   **Lint Passes**: Documents the execution of health checks and maintenance operations performed on the wiki.

Each entry is designed to be easily machine-readable, often starting with a consistent prefix like `## [YYYY-MM-DD] event_type | Description`. This convention facilitates parsing and filtering using standard command-line tools (e.g., `grep`, `tail`) to quickly retrieve specific historical data.

## Relation to Other Wiki Components
`log.md` works in conjunction with [[wiki/concepts/index]] to provide a complete overview of the wiki. While the [[wiki/concepts/index]] is content-oriented, offering a catalog of all pages and entities, `log.md` is process-oriented, documenting the chronological sequence of events and operations that have shaped the wiki. It provides a historical context that helps the LLM understand what actions have been taken recently.