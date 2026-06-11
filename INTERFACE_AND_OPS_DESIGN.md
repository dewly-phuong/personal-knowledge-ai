# Interface and Ops Architecture: Real-time Thinking, Hyperlinked Citations, Scheduler, and Cost Monitoring

## Understanding Summary
* **What is being built**: Sprint 4:
  * **Chainlit Step Visualization (`T25`)**: Update the FastAPI chat stream to yield tool call start/end events, and update Chainlit (`app.py`) to catch these events and render them dynamically as nested, expandable `cl.Step` blocks (showing thinking process).
  * **Source Citation Rendering (`T26`)**: Add helper logic to parse references in agent outputs (like `[Nguồn: wiki/services/auth-service.md]`), read the front matter of the referenced wiki page, retrieve the original source URL (e.g. Confluence/GitHub link), and rewrite the reference to a clickable hyperlink.
  * **Scheduled Sync (`T27`)**: Integrate `APScheduler` in the FastAPI startup lifespan to run a sync and health audit task once every 24 hours.
  * **Manual Sync Tool (`T27/T30`)**: Implement a `sync_knowledge_base` LangChain tool to manually trigger a sync of local files on-demand.
  * **Cost Monitoring (`T28`)**: Hook token counts from agent execution to track, aggregate, and log estimated Gemini API costs (storing stats in Redis).
* **Why it exists**: To provide a production-ready, clean user experience with real-time reasoning steps, correct citation hyperlinks, automated daily scheduling, and cost monitoring.
* **Who it is for**: Developers and operators of the Personal Knowledge AI application.
* **Key constraints**:
  * Parse YAML front matter of wiki files on-the-fly to resolve citation URLs.
  * Integrate APScheduler inside the FastAPI server process.
  * Limit scheduled sync to run once every 24 hours (daily).

## Assumptions
1. **Redis Availability**: A Redis instance is running at `localhost:6379`.
2. **Pricing model**: Using Gemini 2.5 Pro pricing ($0.075 / 1M input tokens, $0.30 / 1M output tokens).

## Decision Log
1. **Sync Interval**: The scheduled background sync job will run once every 24 hours (daily).
2. **Manual Sync Tool**: Implement `sync_knowledge_base` as a registered tool.
3. **Citation Resolution**: Parse local markdown front matter dynamically to map citations to remote Confluence/GitHub URLs.
4. **Token Usage**: Hook into the `on_llm_end` event inside LangChain callback to capture Gemini token counts and record them in Redis.

## Final Design

### 1. Step Event Streaming
The `QueueCallbackHandler` in `main.py` is extended to capture tool executions:
* `on_tool_start`: Yields `{"type": "step_start", "name": tool_name, "input": input_str}`
* `on_tool_end`: Yields `{"type": "step_end", "output": str(output)}`
The Chainlit `app.py` catches these events to instantiate and update `cl.Step` instances.

### 2. Citations Resolution
A helper function `resolve_citations(text: str) -> str` parses `\[Nguồn: (wiki/[^\]]+)\]`. It reads the referenced file's front matter, extracts the first URL in `source_docs`, and rewrites the citation to a clickable hyperlink: `[Nguồn: filename](url)`.

### 3. Daily Scheduler Setup
FastAPI lifespan starts a `BackgroundScheduler` which executes `run_ingest_pipeline("local", dir_path="raw/local")` daily and updates a health report file in `wiki/health_report.md`.

### 4. Cost Tracker
Redis keys:
* `cost:daily:YYYY-MM-DD` -> hash mapping `input`, `output`, and `cost`.
* `cost:monthly:YYYY-MM` -> hash mapping `input`, `output`, and `cost`.
FastAPI exposes `/api/cost` to retrieve these metrics.
