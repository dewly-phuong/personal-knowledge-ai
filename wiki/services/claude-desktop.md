---
source_urls:
  - "file:///home/phun/workspace/dewly/python/personal-knowledge-ai/raw/local/qmd.md"
last_updated: "2026-06-11T07:32:37.650639+00:00"
entities:
  - "claude-desktop"
---
# Claude Desktop

Claude Desktop is a desktop application designed to facilitate agentic workflows and provide an on-device environment for interacting with AI models. It is extensible through various integrations, including local search engines that adhere to the Model Context Protocol (MCP).

## Integrations

### QMD (Query Markup Documents)

Claude Desktop can integrate with [[wiki/services/qmd]], an on-device search engine, to enhance its ability to query and retrieve information from local knowledge bases, notes, and documentation. This integration allows Claude's agentic flows to access indexed markdown documents, meeting transcripts, and other structured data.

QMD integrates with Claude Desktop via the [[wiki/concepts/model-context-protocol]] server.

#### Configuration

**1. Claude Desktop (main application)**

To configure [[wiki/services/qmd]] as an MCP server for Claude Desktop, modify the `claude_desktop_config.json` file, typically located at `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "qmd": {
      "command": "qmd",
      "args": ["mcp"]
    }
  }
}
```

**2. Claude Code (plugin)**

For Claude Code, a plugin is available for simpler installation:

```bash
claude plugin marketplace add tobi/qmd
claude plugin install qmd@qmd
```

Alternatively, manual MCP configuration can be performed in `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "qmd": {
      "command": "qmd",
      "args": ["mcp"]
    }
  }
}
```

#### MCP Server Details

[[wiki/services/qmd]]'s MCP server, when configured for Claude Desktop, exposes tools such as `query`, `get`, `multi_get`, and `status`. It can run as a subprocess (default stdio transport) or as a shared, long-lived HTTP daemon (`qmd mcp --http`) to avoid repeated model loading and ensure LLM models remain loaded in VRAM across requests.

## Dependencies

*   [[wiki/services/qmd]]: The core local search engine service that integrates with Claude Desktop.
*   [[wiki/concepts/model-context-protocol]]: The communication protocol enabling seamless integration with QMD and other compatible tools.
*   Indirectly, through [[wiki/services/qmd]]:
    *   [[wiki/services/node-llama-cpp]]: Used by QMD for running local [[wiki/concepts/gguf-models]].
    *   [[wiki/services/huggingface]]: The primary source for the GGUF models utilized by QMD (e.g., `embeddinggemma`, `qwen3-reranker`, `qmd-query-expansion`).