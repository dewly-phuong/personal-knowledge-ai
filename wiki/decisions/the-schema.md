---
source_urls:
  - "file:///home/phun/workspace/dewly/python/personal-knowledge-ai/raw/local/llm-wiki.md"
last_updated: "2026-06-11T06:54:40.490091+00:00"
entities:
  - "the-schema"
---
# The Schema

The Schema is a foundational document within the [[wiki/concepts/llm-wiki|LLM Wiki]] architecture, acting as a crucial configuration file that dictates an [[wiki/concepts/llm-agent|LLM Agent]]'s behavior and operational workflows.

## Definition and Purpose
The schema is a specific document (e.g., `CLAUDE.md` for Claude Code or `AGENTS.md` for OpenAI Codex/Pi) that provides explicit instructions to the LLM on:
*   The established structure of the wiki, including page classifications and directory organization.
*   The conventions to be followed, such as YAML front matter requirements, heading hierarchies, and backlinking standards.
*   The workflows and procedures for various operations, including ingesting new sources, responding to queries, and performing wiki maintenance.

This document serves as the primary mechanism to transform a general-purpose LLM into a disciplined and consistent wiki maintainer, ensuring adherence to predefined rules and patterns.

## Architectural Role
Within the overall [[wiki/concepts/llm-wiki|LLM Wiki]] architecture, "The Schema" constitutes one of the three distinct layers:
1.  **Raw sources**: Immutable input documents like articles, papers, or data files.
2.  **The wiki**: The dynamic collection of LLM-generated and maintained markdown files.
3.  **The schema**: The static yet evolving blueprint that guides the LLM's interaction with the wiki and raw sources.

The schema is not static; it is designed to be co-evolved by the human user and the LLM over time. This collaborative refinement ensures that the wiki's structure and the LLM's processes remain optimized for the specific domain and user preferences. It is the core element that enables the wiki to become a persistent, compounding artifact, differentiating it from simple [[wiki/concepts/rag|RAG]] systems that re-derive knowledge on every query.

## Impact on Wiki Maintenance
By providing clear, predefined rules, the schema empowers the LLM to handle the often tedious "bookkeeping" aspects of maintaining a knowledge base. This includes:
*   Updating cross-references between pages.
*   Keeping summaries and entity pages current with new information.
*   Flagging potential contradictions between different sources or existing content.
*   Ensuring overall consistency and coherence across the entire wiki.

This automated maintenance frees human users to concentrate on curating sources, guiding analysis, asking insightful questions, and synthesizing higher-level understanding, while the LLM efficiently manages the structural and informational upkeep.