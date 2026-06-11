---
source_urls:
  - "file:///home/phun/workspace/dewly/python/personal-knowledge-ai/raw/local/qmd.md"
last_updated: "2026-06-11T07:32:54.092863+00:00"
entities:
  - "claude-code"
---
# Claude Code

Claude Code is an AI agentic platform designed to facilitate interactions with Language Models (LLMs) by providing contextual understanding and document retrieval capabilities. It integrates with external tools and services, such as [[wiki/services/qmd|Query Markup Documents (QMD)]], to enhance its search and information retrieval workflows.

## Purpose

Claude Code serves as an environment where AI agents can leverage local search engines and knowledge bases. By integrating with services like QMD, it enables LLMs to make more informed contextual choices when selecting and processing documents, thereby improving the quality and relevance of agentic flows.

## Integration with QMD (Query Markup Documents)

Claude Code can integrate with [[wiki/services/qmd]] through its Model Context Protocol (MCP) server, allowing it to utilize QMD's search and retrieval functionalities.

### Installation

The recommended method for integrating QMD with Claude Code is via its plugin marketplace:

```bash
claude plugin marketplace add tobi/qmd
claude plugin install qmd@qmd
```

### Manual MCP Configuration

Alternatively, QMD's MCP server can be configured manually in Claude Code's settings. For Claude Desktop, this typically involves modifying `~/Library/Application Support/Claude/claude_desktop_config.json`. For Claude Code itself, the configuration file is `~/.claude/settings.json`:

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

### Supported QMD Tools

Once integrated, Claude Code can expose the following QMD tools to its AI agents:

*   `query`: Performs hybrid search with typed sub-queries (lexical, vector, HyDE), combined via RRF (Reciprocal Rank Fusion) and LLM reranking.
*   `get`: Retrieves a specific document by path or docid.
*   `multi_get`: Batch retrieves documents using glob patterns, comma-separated lists, or docids.
*   `status`: Provides information about the QMD index health and collection status.

### HTTP Transport for MCP

For shared, long-lived server instances of QMD that avoid repeated model loading, Claude Code can connect to QMD's HTTP transport. This requires QMD to be running as an HTTP daemon, typically on `http://localhost:8181/mcp`.

## Running Environments

Claude Code operates in desktop environments. It is explicitly mentioned in the context of "Claude Desktop configuration" with a macOS-specific path (`~/Library/Application Support/Claude/`).

## Dependencies

*   [[wiki/services/qmd]] (for search and document retrieval capabilities)