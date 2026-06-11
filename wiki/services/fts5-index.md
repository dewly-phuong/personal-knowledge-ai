yaml
---
source_urls:
  - "file:///home/phun/workspace/dewly/python/personal-knowledge-ai/raw/local/qmd.md"
last_updated: "2026-06-11T07:36:04.386951+00:00"
entities:
  - "fts5-index"
---
# FTS5 Index

FTS5 is a full-text search engine extension for SQLite, providing capabilities for efficient keyword-based searching. It implements the [[wiki/concepts/bm25|BM25]] ranking algorithm, which is commonly used for relevance scoring in search systems.

## Usage in QMD

The [[wiki/services/qmd|QMD (Query Markup Documents)]] search engine leverages FTS5 for its BM25 full-text search capabilities. In QMD's hybrid search pipeline, FTS5 is one of the primary search backends used for lexical (keyword) queries, contributing to the initial retrieval phase alongside vector semantic search.

### Scoring

In QMD, FTS5 (BM25) raw scores are converted using `Math.abs(score)`, resulting in a normalized score range of 0 to approximately 25+. These scores are then fused with other backend scores using Reciprocal Rank Fusion (RRF).

### Data Storage

QMD utilizes an FTS5 full-text index, specifically referred to as `documents_fts` in its SQLite database schema, to store and index markdown content for fast full-text searching across collections.

## Related Concepts

*   [[wiki/concepts/bm25|BM25]] - The ranking algorithm employed by FTS5 for determining document relevance.
*   [[wiki/services/qmd|QMD]] - An on-device search engine that integrates FTS5 as a core component for full-text search.