---
source_urls:
  - "file:///home/phun/workspace/dewly/python/personal-knowledge-ai/raw/local/qmd.md"
last_updated: "2026-06-11T07:37:17.231168+00:00"
entities:
  - "ast-aware-chunking"
---
# AST-Aware Chunking

## Technical Definition

AST-aware chunking is an advanced document chunking strategy that utilizes an Abstract Syntax Tree (AST) to identify semantic boundaries within code files. Unlike traditional regex-based chunking, which relies on text patterns, AST-aware chunking parses the source code structure to ensure that logical units like functions, classes, and import declarations are kept intact within a single chunk. This approach produces higher-quality chunks, leading to more accurate and contextually relevant search results for codebases.

For other file types like Markdown, [[wiki/services/qmd]] (which implements AST-aware chunking) continues to use regex-based chunking.

## Architectural Design

The AST-aware chunking mechanism, as implemented in [[wiki/services/qmd]], integrates with [[wiki/concepts/tree-sitter]] grammars. When the `--chunk-strategy auto` option is enabled, QMD parses supported code files (TypeScript, JavaScript, Python, Go, Rust) using tree-sitter. It then generates AST-derived break points which are merged with regex-based break point scores. This hybrid approach ensures that both structural and textual semantics are considered when creating chunks.

**Break Points and Scores (AST-derived):**

| AST Node | Score |
|----------|-------|
| Class / interface / struct / impl / trait | 100 |
| Function / method | 90 |
| Type alias / enum | 80 |
| Import / use declaration | 60 |

These scores are combined with regex-based scores (e.g., headings, code blocks) to determine optimal chunk boundaries. If tree-sitter grammars are not installed, the system gracefully falls back to regex-only chunking.

## Consumers

*   **[[wiki/services/qmd]] CLI users**: Can enable AST-aware chunking via the `--chunk-strategy auto` flag during the `qmd embed` or `qmd query` commands for improved code search.
*   **QMD SDK / Library users**: Can configure chunking strategy through the `embed()` method's `chunkStrategy` option.
*   **AI Agents**: Agents leveraging QMD for code-related tasks benefit from the higher-quality chunks, leading to better contextual understanding and response generation.

## Related Concepts

*   [[wiki/concepts/chunking]]
*   [[wiki/concepts/tree-sitter]]
*   [[wiki/services/qmd]]