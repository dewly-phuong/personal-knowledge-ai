---
source_urls:
  - "file:///home/phun/workspace/dewly/python/personal-knowledge-ai/raw/local/qmd.md"
last_updated: "2026-06-11T07:35:48.496663+00:00"
entities:
  - "bun"
---
# Bun

Bun is a fast, all-in-one JavaScript runtime designed for speed and developer experience. It serves as a modern alternative to Node.js, offering a complete toolkit for building JavaScript applications, including a package manager, bundler, and test runner.

## Technical Definition

Bun is a JavaScript runtime built on the Zig programming language, utilizing the JavaScriptCore engine (from WebKit) for its speed. It provides a command-line interface for executing JavaScript and TypeScript code, managing dependencies, and bundling projects.

## Consumers

[[wiki/concepts/qmd]] is an example of a tool that can be installed and run using Bun. It supports Bun as a primary runtime environment, allowing users to:

*   Install QMD globally: `bun install -g @tobilu/qmd`
*   Run QMD commands directly: `bunx @tobilu/qmd ...`
*   Use QMD as a library within Bun applications.

## System Requirements

Bun version 1.0.0 or greater is required for certain applications like [[wiki/concepts/qmd]].

## Related Concepts

*   [[wiki/concepts/node-js]]: Another popular JavaScript runtime that Bun aims to provide a faster alternative to.