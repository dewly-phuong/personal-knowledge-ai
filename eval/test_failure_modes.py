from eval.failure_modes import classify_failure_modes


def test_classifies_missing_required_tool():
    trace = {
        "expected": {"tools": [{"name": "mongodb_query"}]},
        "actual": {"tool_calls": [{"name": "entity_search", "args": {}}]},
    }

    failures = classify_failure_modes(trace)

    assert failures == [
        {
            "mode": "MISSING_REQUIRED_TOOL",
            "target": "prompt_routing",
            "detail": "Missing required tools: mongodb_query.",
        }
    ]


def test_classifies_missing_required_tool_from_object_item():
    class ToolCall:
        name = "mongodb_query"

    trace = {
        "expected": {"tools": [ToolCall()]},
        "actual": {"tool_calls": []},
    }

    failures = classify_failure_modes(trace)

    assert failures == [
        {
            "mode": "MISSING_REQUIRED_TOOL",
            "target": "prompt_routing",
            "detail": "Missing required tools: mongodb_query.",
        }
    ]


def test_classifies_parallelism_regression():
    trace = {
        "expected": {
            "parallel_group_1": [
                {"tool": "entity_search", "args_hint": {"entity_name": "DataPulse"}},
                {"tool": "mongodb_query", "args_hint": {"collection": "projects"}},
            ]
        },
        "actual": {
            "tool_batches": [
                [{"name": "entity_search", "args": {"entity_name": "DataPulse"}}],
                [{"name": "mongodb_query", "args": {"collection": "projects"}}],
            ],
            "tool_calls": [
                {"name": "entity_search", "args": {"entity_name": "DataPulse"}},
                {"name": "mongodb_query", "args": {"collection": "projects"}},
            ],
        },
    }

    failures = classify_failure_modes(trace)

    assert {
        "mode": "PARALLELISM_REGRESSION",
        "target": "prompt_routing",
        "detail": "Required first-group tools were called, but not in the same batch.",
    } in failures


def test_classifies_parallelism_regression_from_summary():
    trace = {
        "summary": {
            "parallel_batch_passed": False,
            "required_tools_passed": True,
        },
        "actual": {
            "tool_batches": [
                [{"name": "mongodb_query", "args": {"collection": "employees"}}],
                [
                    {
                        "name": "mongodb_query",
                        "args": {"collection": "attendance_october_2024"},
                    }
                ],
            ],
        },
    }

    failures = classify_failure_modes(trace)

    assert {
        "mode": "PARALLELISM_REGRESSION",
        "target": "prompt_routing",
        "detail": "Required first-group tools were called, but not in the same batch.",
    } in failures


def test_classifies_tool_argument_error_for_collection():
    trace = {
        "expected": {
            "parallel_group_1": [
                {"tool": "mongodb_query", "args_hint": {"collection": "projects"}}
            ]
        },
        "actual": {
            "tool_batches": [
                [{"name": "mongodb_query", "args": {"collection": "employees"}}]
            ],
            "tool_calls": [
                {"name": "mongodb_query", "args": {"collection": "employees"}}
            ],
        },
    }

    failures = classify_failure_modes(trace)

    assert {
        "mode": "TOOL_ARGUMENT_ERROR",
        "target": "tool_schema",
        "detail": "mongodb_query expected collection projects but got employees.",
    } in failures


def test_classifies_citation_missing_for_failed_answer():
    trace = {
        "passed": False,
        "actual": {"final_answer": "Đây là câu trả lời không có block nguồn."},
    }

    failures = classify_failure_modes(trace)

    assert {
        "mode": "CITATION_MISSING",
        "target": "citation_format",
        "detail": "Final answer is missing the required 'Nguồn:' citation block.",
    } in failures
