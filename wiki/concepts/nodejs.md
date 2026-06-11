---
source_urls:
  - "file:///home/phun/workspace/dewly/python/personal-knowledge-ai/raw/local/qmd.md"
last_updated: "2026-06-11T07:35:37.518179+00:00"
entities:
  - "nodejs"
---
# Node.js

Node.js is a JavaScript runtime environment.

## Role in QMD

Node.js serves as a primary runtime environment for [[wiki/concepts/QMD]], an on-device search engine for markdown notes and documentation.

*   **System Requirements**: QMD specifies Node.js version >= 22 as a system requirement.
*   **Installation**: QMD can be installed globally using npm (Node Package Manager), which is distributed with Node.js.
*   **SDK Usage**: Developers can integrate QMD as a library within their own Node.js applications.
*   **Feature Support**: Advanced features such as AST-aware chunking for code files within QMD have been tested and are supported on Node.js.
*   **Alternatives**: [[wiki/concepts/Bun]] is also supported as an alternative runtime environment for QMD.