---
source_urls:
  - "file:///home/phun/workspace/dewly/python/personal-knowledge-ai/raw/local/qmd.md"
last_updated: "2026-06-11T07:35:31.152162+00:00"
entities:
  - "tree-sitter"
---
# Tree-sitter

Tree-sitter is a parser generator tool and an incremental parsing library. It is used in [[wiki/services/qmd]] to perform AST-aware chunking for code files, enhancing the quality of document chunks and improving search results for codebases.

## Purpose within QMD

Within [[wiki/services/qmd]], Tree-sitter parses the source code of supported files to identify Abstract Syntax Tree (AST) nodes. These AST-derived break points are then merged with regex-based scores during the smart chunking process. This allows QMD to chunk code files at meaningful boundaries such as function, class, and import declarations, rather than arbitrary text positions.

## Supported Languages & AST Nodes

Tree-sitter's AST-aware chunking is enabled for `.ts`, `.tsx`, `.js`, `.jsx`, `.py`, `.go`, and `.rs` files when the `--chunk-strategy auto` option is used with `qmd embed`.

Key AST nodes used for scoring break points include:

*   **Class / interface / struct / impl / trait**: Score 100
*   **Function / method**: Score 90
*   **Type alias / enum**: Score 80
*   **Import / use declaration**: Score 60

If Tree-sitter grammars are not installed, QMD automatically falls back to regex-only chunking. Markdown and other file types always use regex-based chunking regardless of the strategy.

## Usage in QMD

To enable AST-aware chunking with Tree-sitter in QMD:

```sh
qmd embed --chunk-strategy auto