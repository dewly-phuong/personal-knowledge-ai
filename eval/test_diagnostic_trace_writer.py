from eval.conftest import _build_trace_entry


def test_build_trace_entry_merges_metrics_and_failure_modes():
    score_entry = {
        "run_id": "run1",
        "test_id": "PFC001",
        "file": "test_parallel_function_calling",
        "passed": False,
        "duration": 1.25,
        "metrics": [{"name": "Required Tool Coverage", "passed": False, "score": 0}],
    }
    trace = {
        "suite": "parallel_function_calling",
        "question": "q",
        "expected": {"tools": [{"name": "mongodb_query"}]},
        "actual": {"tool_calls": []},
    }

    entry = _build_trace_entry(score_entry, trace)

    assert entry["run_id"] == "run1"
    assert entry["test_id"] == "PFC001"
    assert entry["suite"] == "parallel_function_calling"
    assert entry["passed"] is False
    assert entry["metrics"] == score_entry["metrics"]
    assert entry["failure_modes"][0]["mode"] == "MISSING_REQUIRED_TOOL"
