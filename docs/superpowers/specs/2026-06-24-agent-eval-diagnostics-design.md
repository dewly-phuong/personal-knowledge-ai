# Agent Eval Diagnostics Design

## Context

The project already has a useful evaluation base:

- `eval/test_single_turn.py` checks answer relevance, faithfulness, graph reasoning, domain faithfulness, and optional tool correctness.
- `eval/test_multi_turn.py` checks turn-level and conversation-level behavior.
- `eval/test_parallel_function_calling.py` checks whether independent tool calls are emitted in the same batch.
- `eval/conftest.py` writes metric results to `eval/result/scores.jsonl`.
- `app/api/streaming.py` already uses a Langfuse LangChain callback for production traces.

The current weakness is not lack of scores. The weakness is diagnosis. A failed eval should explain whether the issue came from routing, tool arguments, retrieval, graph lookup, MongoDB data access, grounding, answer synthesis, chart aggregation, citation formatting, or conversation memory.

## Goal

Build an evaluation workflow that helps improve the agent after each run by producing actionable failure causes, not only pass/fail metrics.

The rollout order is:

1. Phase B: add trace-first diagnostic eval.
2. Phase A: improve reports using the diagnostic artifact.
3. Phase C: connect production traces and user feedback into the eval loop.

## Non-Goals

- Do not replace the existing DeepEval tests.
- Do not introduce a separate hosted eval platform in the first phase.
- Do not require human labeling for every test run.
- Do not fine-tune or change the serving model as part of this design.
- Do not expose hidden chain-of-thought. The trace should record observable messages, tool calls, tool outputs, retrieval context, usage, and diagnostic labels.

## Phase B: Trace-First Diagnostic Eval

### Diagnostic Trace Artifact

Each eval case should write a normalized record to `eval/result/traces.jsonl`.

Required fields:

```json
{
  "run_id": "20260624_153000",
  "test_id": "PFC003",
  "suite": "parallel_function_calling",
  "category": "entity_plus_project_plus_tickets",
  "question": "DataPulse đang ở giai đoạn nào...",
  "expected": {
    "tools": [],
    "parallel_group_1": [],
    "sequential_group_2": [],
    "answer_checks": [],
    "sources": []
  },
  "actual": {
    "tool_batches": [],
    "tool_calls": [],
    "tool_outputs": [],
    "retrieval_context": [],
    "final_answer": "",
    "citations": []
  },
  "metrics": [],
  "failure_modes": [],
  "diagnosis": [],
  "usage": {
    "input_tokens": 0,
    "output_tokens": 0,
    "duration_seconds": 0.0
  }
}
```

The trace record should be append-only, like `scores.jsonl`, so interrupted test sessions still preserve partial results.

### Failure Taxonomy

The diagnostic layer should assign stable failure labels:

- `ROUTING_MISS`: the agent chose the wrong tool family.
- `MISSING_REQUIRED_TOOL`: an expected required tool was not called.
- `UNEXPECTED_TOOL`: the agent called an unrelated tool that increases noise or cost.
- `PARALLELISM_REGRESSION`: independent tools were called sequentially instead of in the same batch.
- `SEQUENTIAL_STEP_MISS`: a required second-phase tool call, such as `generate_chart`, was missing.
- `TOOL_ARGUMENT_ERROR`: the right tool was called with wrong collection, entity, filter, projection, chart type, labels, or values.
- `TOOL_ERROR`: a tool returned an exception or explicit error string.
- `TOOL_EMPTY_RESULT`: a tool returned no records where the case expected data.
- `RETRIEVAL_EMPTY`: the agent had no retrieval context for a question that required internal data.
- `RETRIEVAL_NOISY`: retrieval context exists but does not contain the expected source/entity/fact.
- `GRAPH_MISS`: entity or relationship context was missing or unsupported.
- `MONGO_QUERY_MISS`: MongoDB query missed expected records because of collection or filter mismatch.
- `GROUNDING_ERROR`: final answer includes facts not supported by tool outputs or retrieval context.
- `ANSWER_INCOMPLETE`: final answer omits required answer checks even though supporting data exists.
- `CITATION_MISSING`: final answer lacks the required source block or source details.
- `LANGUAGE_VIOLATION`: final answer is not fully Vietnamese.
- `CHART_AGGREGATION_ERROR`: chart values are missing, not numeric, or not derived from retrieved data.
- `MEMORY_ERROR`: multi-turn answer ignores necessary prior conversation context.

Each failure mode must include a short diagnosis sentence and, where possible, an improvement target:

- `prompt_routing`
- `tool_schema`
- `tool_implementation`
- `retriever_index`
- `dataset_expected`
- `answer_synthesis`
- `citation_format`
- `memory_management`

### Trace Capture

The eval runner should collect observable agent events:

- AI messages with tool calls grouped by batch.
- Tool names and arguments.
- Tool outputs, with large outputs truncated for report display but preserved enough for diagnosis.
- Retrieval context registered through `app.tools.retrieval_context`.
- Final answer.
- Token usage and duration where available.

The existing `test_parallel_function_calling.py` already extracts tool batches from `AIMessage.tool_calls`. That logic should be generalized into a reusable helper, then used by single-turn, multi-turn, and parallel tests.

### Deterministic Checks First

The classifier should prefer deterministic checks before LLM judging:

- Required tool coverage.
- Parallel batch compliance.
- Sequential tool coverage.
- Tool argument matching for collection/entity/chart fields.
- Presence of source/citation block.
- Vietnamese language heuristic.
- Empty or error tool output detection.

LLM-as-judge should be reserved for:

- retrieval noise,
- answer completeness,
- grounding,
- graph reasoning quality,
- memory quality.

This keeps the diagnostic layer cheaper and more stable.

### Expected Answer Checks

Datasets that already contain `expected_answer_checks` should use them directly. For single-turn and multi-turn synthetic datasets, add optional fields over time:

```json
{
  "expected_answer_checks": [
    "Nêu DataPulse đạt 32% progress",
    "Nêu budget 1,800M VNĐ",
    "Nêu nguồn MongoDB projects"
  ],
  "expected_sources": [
    "wiki/services/datapulse.md",
    "MongoDB projects"
  ]
}
```

This turns vague answer quality failures into missing-fact failures.

## Phase A: Diagnostic Report Improvements

After `traces.jsonl` exists, update `eval/generate_report.py` and report builders to include:

- failure mode summary,
- suite/category pass rates,
- top failing tools,
- top failing MongoDB collections,
- top missing sources,
- examples of representative failures,
- recommended action grouped by improvement target.

The report should answer:

- Which behaviors regressed?
- Which tool or data source caused most failures?
- Are failures mainly routing, retrieval, grounding, or synthesis?
- Which prompt/tool/schema change is the best next fix?

The existing metric tables should remain, but become secondary to failure diagnosis.

## Phase C: Production Feedback Loop

Once local diagnostics are stable, connect production data:

- Langfuse traces from `app/api/streaming.py`.
- Chainlit feedback stored in MongoDB `cl_feedbacks`.
- Conversation history from the Mongo-backed Chainlit data layer.

Production failures should be converted into candidate eval cases:

1. Select low-rated or commented user turns.
2. Pull the corresponding trace/tool steps.
3. Redact sensitive fields where needed.
4. Add expected tool/source/check annotations.
5. Save into a regression dataset.
6. Run the same diagnostic pipeline before prompt/model/tool changes.

Human review is useful here, but only for sampled or high-impact cases.

## Architecture

Add small, focused eval modules:

- `eval/trace_schema.py`: typed helpers for normalized trace records.
- `eval/trace_capture.py`: converts LangChain messages and pytest metadata into trace records.
- `eval/failure_modes.py`: deterministic classifier and LLM-backed optional checks.
- `eval/diagnostic_report.py`: aggregation helpers for failure modes and improvement targets.

Existing test files should call these helpers without changing their core test purpose.

## Data Flow

1. Pytest test invokes the agent.
2. Test extracts messages, tool calls, retrieval context, and final answer.
3. DeepEval metrics run as they do today.
4. `conftest.py` writes score records.
5. Diagnostic helper writes `traces.jsonl`.
6. Report generator combines `scores.jsonl` and `traces.jsonl` by `run_id`, `test_id`, and suite/file label.
7. Developer reads the report and fixes the highest-impact failure target.

## Error Handling

- If trace writing fails, the test should continue and log a warning.
- If LLM-based diagnosis fails, deterministic failure labels should still be emitted.
- If expected fields are absent from older datasets, the classifier should skip those checks rather than fail the test.
- If tool output is huge, store a truncated preview plus metadata such as character length.

## Testing Strategy

Unit tests:

- Tool batch extraction from LangChain messages.
- Argument matching for MongoDB, entity, and chart tool calls.
- Failure taxonomy classification for synthetic passing/failing traces.
- Report aggregation by failure mode and target.

Integration tests:

- Run one single-turn case and verify a trace row is written.
- Run one parallel function-calling case and verify missing/parallel failures are diagnosable.
- Generate a report from fixture `scores.jsonl` and `traces.jsonl`.

Manual verification:

- Inspect one failed PFC case and confirm the report points to a concrete fix.
- Inspect one answer-quality failure and confirm it distinguishes retrieval failure from synthesis failure.

## Success Criteria

Phase B is successful when:

- Every eval run writes `eval/result/traces.jsonl`.
- A failing case has at least one stable `failure_mode`.
- PFC failures identify missing tools, wrong args, or parallelism regressions.
- Single-turn failures can distinguish retrieval/grounding/answer completeness issues.
- The diagnostic layer does not require changing production agent behavior.

Phase A is successful when:

- The generated report shows failure mode distribution and recommended improvement targets.
- A developer can choose the next prompt/tool/retrieval fix from the report without opening raw pytest logs first.

Phase C is successful when:

- Negative Chainlit feedback can be converted into a replayable eval case.
- Production traces become regression coverage before prompt or model changes.
