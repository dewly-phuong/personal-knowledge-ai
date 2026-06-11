---
source_urls:
  - "file:///home/phun/workspace/dewly/python/personal-knowledge-ai/raw/local/llm-wiki.md"
last_updated: "2026-06-11T06:56:23.283019+00:00"
entities:
  - "obsidian-web-clipper"
---
# Obsidian Web Clipper

## Purpose
The Obsidian Web Clipper is a browser extension that converts web articles into markdown format. Its primary purpose is to quickly ingest web content into a user's collection of [[wiki/concepts/raw-sources]], making it readily available for processing by an LLM or for direct use within [[wiki/services/obsidian]].

## Usage
This tool simplifies the process of curating digital content by transforming web pages into a structured, plain-text format suitable for knowledge bases. After clipping an article, it facilitates the immediate addition of that content to the user's raw source repository.

### Image Handling
While not a direct feature of the clipper itself, the document suggests an optional workflow with [[wiki/services/obsidian]] to enhance content:
*   **Attachment Folder**: In Obsidian settings, configure "Attachment folder path" to a fixed directory (e.g., `raw/assets/`).
*   **Download Hotkey**: Assign a hotkey (e.g., Ctrl+Shift+D) to "Download attachments for current file" in Obsidian's hotkey settings.
*   **Workflow**: After clipping an article and importing it into Obsidian, use the hotkey to download all referenced images to the local disk. This allows LLMs to access and reference images directly, bypassing reliance on potentially unstable external URLs.