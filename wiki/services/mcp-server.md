---
source_urls:
  - "file:///home/phun/workspace/dewly/python/personal-knowledge-ai/raw/local/qmd.md"
last_updated: "2026-06-11T07:32:28.560680+00:00"
entities:
  - "mcp-server"
---
# MCP Server

The MCP (Model Context Protocol) Server is a component of the [[wiki/services/qmd]] (Query Markup Documents) tool, designed for tighter integration with AI agents and clients like Claude Desktop. It allows QMD to expose its functionalities as a service, rather than just a command-line tool.

By default, the QMD MCP server uses standard I/O (stdio) and is launched as a subprocess by each client. For a shared, long-lived server that avoids repeated model loading, an HTTP transport option is available.

## Purpose

The MCP Server enables AI agents to interact with [[wiki/services/qmd]] programmatically, allowing them to leverage QMD's search, retrieval, and indexing capabilities. It provides a structured interface for agents to query information and retrieve documents, enhancing contextual decision-making in agentic workflows.

## Exposed Tools

The MCP Server exposes the following tools:

*   **`query`**: Searches with typed sub-queries (`lex`/`vec`/`hyde`), combined via RRF + reranking.
*   **`get`**: Retrieves a document by path or docid (with fuzzy matching suggestions).
*   **`multi_get`**: Batch retrieves documents by glob pattern, comma-separated list, or docids.
*   **`status`**: Provides index health and collection information.

## Configuration for AI Clients

### Claude Desktop

To configure MCP Server integration with Claude Desktop (e.g., `~/Library/Application Support/Claude/claude_desktop_config.json`):

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

### Claude Code

Install the QMD plugin (recommended):

```bash
claude plugin marketplace add tobi/qmd
claude plugin install qmd@qmd
```

Alternatively, configure MCP manually in `~/.claude/settings.json`:

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

## HTTP Transport

For a shared, long-lived instance that keeps LLM models loaded in VRAM across requests, the MCP Server can be run using HTTP transport.

### Running the HTTP Server

*   **Foreground (Ctrl-C to stop)**:
    ```sh
    qmd mcp --http                    # Default: localhost:8181
    qmd mcp --http --port 8080        # Custom port
    ```
*   **Background daemon**:
    ```sh
    qmd mcp --http --daemon           # Starts daemon, writes PID to ~/.cache/qmd/mcp.pid
    qmd mcp stop                      # Stops daemon via PID file
    qmd status                        # Shows "MCP: running (PID ...)" when active
    ```

### HTTP Endpoints

The HTTP server exposes two primary endpoints:

*   **`POST /mcp`**: MCP Streamable HTTP (JSON responses, stateless).
*   **`GET /health`**: Liveness check with uptime.

Embedding/reranking contexts are disposed after 5 minutes of idle time and transparently recreated on the next request (with a ~1-second penalty), but models remain loaded. Clients can point to `http://localhost:8181/mcp` to connect.

## MCP Tool Parameters

| Tool | Parameter | Type | Notes |
| :---------- | :---------- | :----- | :--------------------------------------------------------------------------------------- |
| `query` | `searches` | array | Typed sub-queries (`lex`/`vec`/`hyde`), 1–10. **Required.** First gets 2x weight. |
| `query` | `collections` | string[] | Filter by collection names (OR). **Array only** — singular `collection` is silently ignored. |
| `query` | `intent` | string | Disambiguation context (does not search on its own). |
| `query` | `limit` | number | Max results (default 10). |
| `query` | `minScore` | number | Minimum relevance 0–1 (default 0). |
| `query` | `candidateLimit` | number | Max candidates to rerank (default 40). |
| `query` | `rerank` | boolean | Run LLM reranking (default **true**); set `false` for RRF-only. |
| `get` | `file` | string | Path, docid (`#abc123`), or `path:from:count` (e.g., `#abc123:120:40`). |
| `get` | `fromLine` | number | Start line (1-indexed); overrides the `:from` suffix. |
| `get` | `maxLines` | number | Limit returned lines. |
| `get` | `lineNumbers` | boolean | Prefix lines with numbers (default **true**). |
| `multi_get` | `pattern` | string | Glob pattern or comma-separated list. |
| `multi_get` | `maxBytes` | number | Skip files larger than N (default 10240). |
| `multi_get` | `maxLines` | number | Limit lines per file. |
| `multi_get` | `lineNumbers` | boolean | Prefix lines with numbers (default **true**). |

Unknown parameters are silently ignored; users should double-check parameter names if results appear unscoped. The HTTP `/query` and `/search` endpoints return `qmd://collection/path` URIs in the `file` field, matching CLI and MCP output.