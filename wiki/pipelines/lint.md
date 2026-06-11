---
source_urls:
  - "file:///home/phun/workspace/dewly/python/personal-knowledge-ai/raw/local/llm-wiki.md"
last_updated: "2026-06-11T06:55:21.776579+00:00"
entities:
  - "lint"
---
# Lint

The `Lint` operation is a periodic health-check process within the [[wiki/concepts/LLM Wiki]] architecture, executed by the [[wiki/concepts/LLM Agent]]. Its primary purpose is to maintain the integrity and quality of the wiki by identifying and flagging issues that accumulate over time.

## Sequence Steps

When a lint pass is initiated, the [[wiki/concepts/LLM Agent]] performs the following checks across the wiki:

1.  **Contradiction Detection**: Identifies instances where information in different wiki pages directly contradicts each other.
2.  **Stale Claims Identification**: Locates claims or data that have been superseded by newer sources or information ingested via the [[wiki/pipelines/Ingest]] pipeline.
3.  **Orphan Page Discovery**: Finds pages that have no inbound links from other wiki pages, indicating potential isolation or irrelevance.
4.  **Missing Concept Pages**: Flags important concepts that are mentioned across the wiki but do not yet have their own dedicated page.
5.  **Cross-reference Verification**: Checks for missing or incorrect cross-references between related pages.
6.  **Data Gap Analysis**: Points out areas where information is scarce or missing, potentially suggesting new questions for investigation or sources to seek.

## Triggers

The `Lint` pipeline is typically triggered **periodically** or on demand, as part of routine [[wiki/concepts/LLM Wiki]] maintenance.

## Failure Modes

The primary "failure" in a lint operation would be the **inability to identify issues** or **incorrectly flagging non-issues**. However, the output of `Lint` is not a hard failure, but rather a set of **suggestions for improvement**. If the LLM misses contradictions or other problems, the wiki's overall quality and consistency will degrade over time.

## Rollback Procedures

There are no direct rollback procedures for a `Lint` pass itself, as it is primarily a diagnostic operation. The results of a lint pass (e.g., suggested fixes, new questions) are then acted upon by the [[wiki/concepts/LLM Agent]] through subsequent [[wiki/pipelines/Ingest]] or [[wiki/pipelines/Query]] operations. If an LLM-suggested fix introduces new errors, those would be caught in a future lint pass.

## Related Services and Concepts

*   [[wiki/concepts/LLM Wiki]]: The overarching system that this pipeline maintains.
*   [[wiki/concepts/LLM Agent]]: The entity responsible for executing the linting process.
*   [[wiki/pipelines/Ingest]]: The pipeline responsible for adding new information to the wiki, which can introduce contradictions or stale data that `Lint` detects.
*   [[wiki/pipelines/Query]]: The pipeline used for asking questions against the wiki, which can also generate new content that benefits from linting.
*   [[wiki/concepts/Index]]: The structured catalog that `Lint` can analyze for missing pages or incorrect categorizations.
*   [[wiki/concepts/Log]]: The chronological record that may include past ingestions or queries relevant to identifying stale information.