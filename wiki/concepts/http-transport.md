---
source_urls:
  - "file:///home/phun/workspace/dewly/python/personal-knowledge-ai/raw/local/qmd.md"
last_updated: "2026-06-11T07:33:03.658246+00:00"
entities:
  - "http-transport"
---
# HTTP Transport

HTTP Transport is an alternative communication mechanism for the [[wiki/concepts/mcp-server|MCP Server]] in [[wiki/services/qmd|QMD]], designed to provide a shared, long-lived server instance that avoids repeated [[wiki/concepts/llm-reranking|LLM model]] loading. It offers a persistent daemon mode as an alternative to the default [[wiki/concepts/stdio-transport|stdio]] (subprocess) transport.

## Technical Definition

The HTTP Transport allows the [[wiki/services/qmd|QMD]] Model Context Protocol (MCP) server to run as a standalone, long-lived daemon accessible via HTTP. This ensures that expensive resources, such as LLM models loaded into VRAM, remain active across multiple requests, significantly reducing latency compared to launching a new subprocess for each client interaction.

## Architectural Design

Instead of launching the MCP server as a subprocess that uses standard input/output (stdio) for communication, the HTTP Transport mode deploys a persistent server.

*   **Communication Protocol**: Exposes two HTTP endpoints:
    *   `POST /mcp`: For MCP Streamable HTTP, handling JSON requests and responses in a stateless manner.
    *   `GET /health`: A liveness check endpoint that reports the server's uptime.
*   **Model Loading**: LLM models (for embeddings and reranking) are loaded into VRAM once and persist across requests. While embedding/reranking contexts might be disposed after 5 minutes of idle time, the base models remain loaded, incurring only a minor (~1s) recreation penalty for the context on the next request.
*   **Deployment Modes**: Can be run in the foreground (blocking the terminal) or as a background daemon.
    *   Foreground: `qmd mcp --http` (defaults to `localhost:8181`)
    *   Custom Port: `qmd mcp --http --port 8080`
    *   Daemon: `qmd mcp --http --daemon` (writes PID to `~/.cache/qmd/mcp.pid`)
    *   Stopping Daemon: `qmd mcp stop`
*   **Client Connection**: MCP clients configured for HTTP transport point to `http://localhost:8181/mcp` (or the specified custom port) to connect.

## Consumers

Clients that can connect to a persistent [[wiki/concepts/mcp-server|MCP Server]] via HTTP include:

*   **AI Agents**: Specifically, environments like Claude Desktop and Claude Code, which can be configured to use an MCP server running on a specific HTTP endpoint.
*   Any application or script capable of making HTTP `POST` requests to the `/mcp` endpoint and interpreting the JSON stream.

## Related Concepts

*   [[wiki/services/qmd]]
*   [[wiki/concepts/mcp-server]]
*   [[wiki/concepts/stdio-transport]]
*   [[wiki/concepts/llm-reranking]]