---
source_urls:
  - "file:///home/phun/workspace/dewly/python/personal-knowledge-ai/raw/local/qmd.md"
last_updated: "2026-06-11T07:37:06.798561+00:00"
entities:
  - "smart-chunking"
---
# Smart Chunking

Smart Chunking is an algorithm used to segment documents into smaller, semantically coherent pieces, typically for the purpose of generating [[wiki/concepts/vector-embeddings]] for search and retrieval. Instead of cutting at arbitrary token boundaries, it employs a scoring mechanism to identify natural break points within text, ensuring that logical units like sections, paragraphs, and code blocks remain intact.

## Purpose

The primary goal of Smart Chunking is to produce higher-quality chunks that lead to better search results, especially in hybrid search systems. By maintaining semantic integrity, downstream processes like vector embedding and LLM reranking can interpret the document context more accurately.

## Mechanism

The Smart Chunking algorithm in [[wiki/services/qmd]] (Query Markup Documents) works by scanning a document for potential break points and assigning them scores based on their structural significance.

### Break Point Scoring Algorithm

1.  **Identify Potential Break Points**: The algorithm first scans the entire document to identify all possible locations where a chunk could end, such as headings, code block boundaries, blank lines, and line breaks.
2.  **Assign Base Scores**: Each potential break point is assigned a base score reflecting its semantic importance:
    *   `# Heading` (H1): 100
    *   `## Heading` (H2): 90
    *   `### Heading` (H3): 80
    *   `#### Heading` (H4): 70
    *   `##### Heading` (H5): 60
    *   `###### Heading` (H6): 50
    *   ```` ``` ```` (Code block boundary): 80
    *   `---` / `***` (Horizontal rule): 60
    *   Blank line (Paragraph boundary): 20
    *   `- item` / `1. item` (List item): 5
    *   Line break: 1
3.  **Windowed Selection**: When approaching the target chunk size (e.g., 900 tokens), the algorithm searches a specified window (e.g., 200 tokens) *before* the cutoff point.
4.  **Distance-Weighted Scoring**: Within this window, the final score for each break point is calculated using a decay function: `finalScore = baseScore × (1 - (distance/window)² × 0.7)`. This penalizes distant break points but still allows a highly scored, slightly more distant break (like a heading) to be chosen over a less significant, closer one (like a simple line break).
5.  **Optimal Cut**: The chunk is cut at the highest-scoring break point within the evaluation window.

### Code Fence Protection

Break points detected *inside* code blocks are ignored. This ensures that code snippets remain whole, preventing them from being fragmented across multiple chunks. If a single code block exceeds the maximum chunk size, it is generally kept as a whole chunk if possible.

### AST-Aware Chunking (for Code Files)

For supported programming language files (TypeScript, JavaScript, Python, Go, Rust), Smart Chunking can leverage [[wiki/concepts/tree-sitter]] parsers. This feature, enabled with the `--chunk-strategy auto` option, augments the regex-based scoring by adding AST-derived break points:

| AST Node Type                          | Score |
| :------------------------------------- | :---- |
| Class / interface / struct / impl / trait | 100   |
| Function / method                      | 90    |
| Type alias / enum                      | 80    |
| Import / use declaration               | 60    |

These AST-derived scores are merged with the standard regex scores, allowing for more semantically meaningful chunking in codebases by ensuring functions, classes, and other logical code constructs stay together. If [[wiki/concepts/tree-sitter]] grammars are not installed for a particular language, the system gracefully falls back to regex-only chunking.

## Usage

Smart Chunking is a core component of the `embed` operation in [[wiki/services/qmd]]. When users run `qmd embed`, documents are processed through this chunking mechanism before being fed to an embedding model (like `embeddinggemma-300M-Q8_0` used by [[wiki/services/node-llama-cpp]]) to generate their vector representations. The AST-aware chunking can be explicitly enabled using the `--chunk-strategy auto` flag during the `qmd embed` or `qmd query` commands.