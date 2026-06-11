---
source_urls:
  - "file:///home/phun/workspace/dewly/python/personal-knowledge-ai/raw/local/llm-wiki.md"
last_updated: "2026-06-11T06:54:51.493707+00:00"
entities:
  - "ingest"
---
# Ingest

The `Ingest` pipeline describes the process by which an [[wiki/concepts/llm-agent]] integrates new information from [[wiki/concepts/raw-sources]] into a persistent [[wiki/concepts/wiki]]. This process is designed to incrementally build and maintain the knowledge base, ensuring information is compiled once and kept current, rather than re-derived on every query.

## Triggers

The `Ingest` pipeline is primarily triggered by user action:
*   A user drops a new source document into the raw collection.
*   The user explicitly instructs the [[wiki/concepts/llm-agent]] to process the newly added source(s).

## Sequence Steps

Upon triggering, the `Ingest` pipeline typically follows these steps:
1.  **Read Source**: The [[wiki/concepts/llm-agent]] reads and analyzes the new source document.
2.  **Discuss Takeaways**: Optionally, the [[wiki/concepts/llm-agent]] may discuss key takeaways with the user, allowing for human guidance on emphasis and interpretation. This is common in a single-source, supervised ingestion workflow.
3.  **Create/Update Summary**: The [[wiki/concepts/llm-agent]] writes a new summary page in the [[wiki/concepts/wiki]] for the ingested source or updates an existing one if the source is a revision.
4.  **Update Index**: The [[wiki/concepts/index]] page, which catalogs all wiki content, is updated to reflect the new or modified page.
5.  **Integrate Content**: Relevant [[wiki/concepts/entity]] and [[wiki/concepts/concept]] pages across the [[wiki/concepts/wiki]] are updated or created based on the information extracted from the source. This includes adding new facts, revising existing descriptions, noting contradictions, and establishing cross-references. A single source may touch 10-15 wiki pages.
6.  **Append Log Entry**: An entry detailing the ingestion event (date, source title) is appended to the `[[wiki/concepts/log]]` file for chronological tracking.

## Failure Modes

*   **Contradictory Information**: If new ingestion sources contradict existing [[wiki/concepts/wiki]] content, the system is designed to flag these rather than silently overwrite. This is noted via a warning callout.
*   **Missing Context/Guidance**: In less supervised batch-ingestion scenarios, the [[wiki/concepts/llm-agent]] might misinterpret information or fail to prioritize key details without human intervention.
*   **Schema Adherence Issues**: The [[wiki/concepts/llm-agent]] might fail to adhere strictly to the wiki's defined [[wiki/concepts/schema]], leading to inconsistent page structures or missing metadata.

## Rollback Procedures

Given that the [[wiki/concepts/wiki]] is essentially a Git repository of Markdown files:
*   **Version Control**: Standard Git operations (e.g., `git revert`, `git checkout`) can be used to roll back any set of changes made during an ingestion.
*   **Human Review**: The incremental and supervised nature of ingestion (especially one-at-a-time processing) allows for immediate human review and correction, effectively acting as a pre-commit rollback.

## Related Services and Concepts

*   [[wiki/concepts/llm-agent]]: The orchestrating agent responsible for executing the ingestion steps.
*   [[wiki/concepts/raw-sources]]: The immutable collection of source documents from which information is ingested.
*   [[wiki/concepts/wiki]]: The structured, interlinked collection of Markdown files that is built and maintained by this pipeline.
*   [[wiki/concepts/index]]: A special file updated during ingestion, serving as a content-oriented catalog of the wiki.
*   [[wiki/concepts/log]]: A special file updated during ingestion, serving as a chronological record of wiki events.
*   [[wiki/concepts/schema]]: The guiding document that dictates the wiki's structure, conventions, and workflows, which the [[wiki/concepts/llm-agent]] adheres to during ingestion.