import json

from eval.test_single_turn import (
    _graph_reasoning,
    _has_graph_context,
    _single_turn_metrics,
)


def test_has_graph_context_false_when_graph_source_empty():
    outputs = [
        {
            "name": "knowledge_search",
            "output": json.dumps(
                {
                    "query": "q",
                    "results": [
                        {"source": "wiki", "status": "ok", "data": {"text": "A"}},
                        {"source": "graph", "status": "empty", "data": None},
                    ],
                }
            ),
        }
    ]

    assert _has_graph_context(outputs) is False


def test_single_turn_metrics_skip_graph_reasoning_without_graph_context(monkeypatch):
    monkeypatch.setenv("SKIP_TOOL_CORRECTNESS", "1")
    outputs = [
        {
            "name": "knowledge_search",
            "output": json.dumps(
                {
                    "query": "q",
                    "results": [
                        {"source": "wiki", "status": "ok", "data": {"text": "A"}},
                        {"source": "graph", "status": "empty", "data": None},
                    ],
                }
            ),
        }
    ]

    metrics = _single_turn_metrics(
        retrieval_context=["wiki context"], outputs=outputs, expected_tools=None
    )

    assert _graph_reasoning not in metrics


def test_single_turn_metrics_include_graph_reasoning_with_graph_context(monkeypatch):
    monkeypatch.setenv("SKIP_TOOL_CORRECTNESS", "1")
    outputs = [
        {
            "name": "knowledge_search",
            "output": json.dumps(
                {
                    "query": "q",
                    "results": [
                        {
                            "source": "graph",
                            "status": "ok",
                            "data": {"nodes": [{"id": "VisionChat"}]},
                        }
                    ],
                }
            ),
        }
    ]

    metrics = _single_turn_metrics(
        retrieval_context=["graph context"], outputs=outputs, expected_tools=None
    )

    assert _graph_reasoning in metrics
