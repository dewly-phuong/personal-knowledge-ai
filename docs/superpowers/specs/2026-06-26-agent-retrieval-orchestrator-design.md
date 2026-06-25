# Agent Retrieval Orchestrator Design

## Goal

Refactor the agent retrieval architecture so every user question is answered from a complete, parallel search across all configured knowledge sources.

The agent should no longer contain source-specific routing rules in the system prompt. Instead, it should call one general `knowledge_search` tool, receive normalized results from every registered source, and synthesize the final Vietnamese answer only from those results.

This design also makes new data sources easy to add without rewriting the agent prompt or changing the agent factory.

## Current State

The current runtime is a single LangChain `create_agent` agent using Gemini 2.5 Pro. The agent registers three tools:

- `uploaded_file_context`
- `knowledge_search`
- `generate_chart`

`knowledge_search` currently combines wiki search, optional graph lookup, and optional MongoDB query. The agent prompt decides when to pass `entity_name`, `collection`, and `filter_json`. This makes the prompt long and specific to the current data model.

There are also older exported tools such as `mongodb_query`, `graph_traverse`, `ingest_source`, and `lint_wiki`, but the active agent no longer registers them directly.

## Target Behavior

For every user question, the agent should call `knowledge_search(query)` before answering.

`knowledge_search` should always fan out to all configured knowledge sources at the same time. Each source must return a normalized result. If a source has no matching data, its result must be present with `data = null` and `status = "empty"`. If a source fails, its result must be present with `data = null` and `status = "error"`.

The final answer should synthesize only sources with usable data. Empty or failed sources should not block the answer, and the agent must not infer missing internal facts from general knowledge.

If every source returns empty or error, the agent should clearly say that it could not find relevant data in the available knowledge sources.

## Architecture

Introduce a retrieval layer under the `knowledge_search` tool:

```text
Agent
  -> knowledge_search(query)
      -> KnowledgeSourceRegistry
          -> WikiKnowledgeSource
          -> GraphKnowledgeSource
          -> MongoKnowledgeSource
          -> UploadKnowledgeSource
          -> future sources
      -> SearchBundle
  -> answer synthesis
```

The agent remains a single conversational agent. The retrieval system becomes the extensibility boundary.

## Data Contracts

Use explicit models for retrieval input and output.

```python
@dataclass
class SearchContext:
    session_id: str | None = None
    upload_ids: list[str] | None = None
    limit: int = 100
    timeout_seconds: float = 8.0
```

```python
@dataclass
class SourceResult:
    source: str
    status: Literal["ok", "empty", "error"]
    data: Any | None
    summary: str
    metadata: dict[str, Any]
    error: str | None = None
```

```python
@dataclass
class SearchBundle:
    query: str
    results: list[SourceResult]
```

Each source implements one interface:

```python
class KnowledgeSource(Protocol):
    name: str

    async def search(self, query: str, context: SearchContext) -> SourceResult:
        ...
```

Adding a new source should mean creating a new `KnowledgeSource` implementation and registering it. The agent prompt should not change.

## Source Behavior

### Wiki Source

Runs the existing hybrid BM25 plus Qdrant wiki search. If no wiki pages exist or no useful match is found, returns `status = "empty"` and `data = null`.

### Graph Source

Runs entity discovery and graph lookup without requiring the agent to provide `entity_name`. It should infer candidate entity names from the query using lightweight matching against graph nodes first. It can later be upgraded with LLM extraction if needed, but the first implementation should avoid an extra model call.

If no candidate entity or relation is found, returns `status = "empty"` and `data = null`.

### Mongo Source

Searches structured MongoDB data without putting every collection schema into the system prompt.

The initial implementation should use collection discovery plus a source-owned schema catalog. The source can choose one of these strategies:

- Query text-indexed collections when indexes exist.
- Use collection metadata and simple keyword matching to select candidate collections.
- For candidate collections, run bounded queries with safe limits.

If no collection has relevant records, returns `status = "empty"` and `data = null`.

Mongo errors should be isolated to the Mongo source result and should not fail the whole `knowledge_search` call.

### Upload Source

Uses the current session upload context. If no session or no processed upload exists, returns `status = "empty"` and `data = null`.

### Future Sources

Future sources should not require agent prompt changes. They should expose name, search implementation, empty behavior, error behavior, and metadata.

## Parallelism and Timeouts

`knowledge_search` should run all registered source searches concurrently.

Each source should have a per-source timeout. A timeout returns:

```json
{
  "source": "source_name",
  "status": "error",
  "data": null,
  "summary": "Source timed out.",
  "metadata": {"timeout_seconds": 8.0},
  "error": "timeout"
}
```

The aggregate tool should complete even when one or more sources fail.

## Prompt Design

Replace the current source-specific prompt with a general policy:

- Reply in Vietnamese.
- For factual or internal-company questions, call `knowledge_search` before answering.
- Use only the data returned by tools.
- Treat `data = null`, `status = "empty"`, and `status = "error"` as unavailable evidence.
- If all sources are unavailable, state that no relevant data was found.
- Cite the sources that supplied usable data.
- For chart requests, call `knowledge_search` first, compute labels and values from returned data, then call `generate_chart`.

The prompt should not include current MongoDB collection names, field lists, hard-coded examples, or source-specific routing logic.

## Tool Surface

The active agent should keep a small tool surface:

- `knowledge_search`
- `generate_chart`

`uploaded_file_context` can be removed from the active agent once upload retrieval is implemented as `UploadKnowledgeSource`. It can remain exported for compatibility and tests.

Existing direct tools such as `mongodb_query` and `graph_traverse` may remain available for diagnostics, tests, or manual use, but should not be required by the agent's normal reasoning path.

## API and Streaming

The FastAPI and Chainlit streaming shape can remain mostly unchanged.

`knowledge_search` should return a text or JSON payload that is readable by the model and also traceable by eval code. The returned payload should include every source result, including null results.

The streaming layer should continue showing `knowledge_search` as one tool step. Later, it can render per-source substeps from the bundle metadata, but that is not required for the first implementation.

## Evaluation Impact

Existing evals and docs currently reference older tools such as `mongodb_query`, `wiki_search`, and `entity_search`. They should be updated to evaluate:

- The agent calls `knowledge_search` before factual answers.
- The `knowledge_search` bundle includes every registered source.
- Empty sources are represented as null results.
- The final answer cites only non-empty sources.
- The agent does not hallucinate when all sources are empty.
- Chart requests call `knowledge_search` before `generate_chart`.

Parallel function-calling evals should shift from multiple direct tool calls to one `knowledge_search` call that internally performs parallel source fan-out.

## Rollout Plan

Implement this in phases:

1. Add retrieval contracts and source registry.
2. Wrap existing wiki, graph, MongoDB, and upload logic as `KnowledgeSource` implementations.
3. Refactor `knowledge_search` to call the registry concurrently and return a `SearchBundle`.
4. Simplify `SYSTEM_PROMPT`.
5. Ensure `system_prompt` passed to `create_conversational_agent` is actually used.
6. Update evals and documentation to the new tool model.

## Risks

Always searching all sources can increase latency. This is mitigated with parallel execution, per-source timeout, and bounded result sizes.

MongoDB generic search may be less precise than prompt-directed `collection` and `filter_json` calls. The first implementation should keep safe bounded discovery, then improve source-owned schema metadata over time.

Returning too much data can overwhelm the model. Each source should summarize and cap its payload before it reaches the agent.

## Non-Goals

This design does not introduce multi-agent routing.

This design does not require an LLM planner before retrieval.

This design does not remove diagnostic tools immediately.

This design does not redesign ingestion, wiki compilation, graph extraction, or Chainlit persistence.
