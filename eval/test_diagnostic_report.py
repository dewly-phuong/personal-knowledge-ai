import json

from eval.diagnostic_report import diagnostic_summary, parse_traces_file


def test_parse_traces_file_selects_latest_run(tmp_path):
    path = tmp_path / "traces.jsonl"
    rows = [
        {"run_id": "old", "test_id": "A", "failure_modes": []},
        {
            "run_id": "new",
            "test_id": "B",
            "failure_modes": [
                {"mode": "CITATION_MISSING", "target": "citation_format"}
            ],
        },
    ]
    path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")

    assert parse_traces_file(path) == [rows[1]]


def test_diagnostic_summary_counts_modes_and_targets():
    records = [
        {"passed": False, "actual": {"final_answer": "Thiếu nguồn"}},
        {"passed": False, "actual": {"final_answer": "Cũng thiếu nguồn"}},
        {
            "passed": False,
            "expected": {
                "parallel_group_1": [
                    {"tool": "mongodb_query", "args_hint": {"collection": "projects"}}
                ]
            },
            "actual": {
                "tool_calls": [
                    {"name": "mongodb_query", "args": {"collection": "employees"}}
                ]
            },
        },
    ]

    summary = diagnostic_summary(records)

    assert summary["failure_modes"] == {
        "CITATION_MISSING": 2,
        "TOOL_ARGUMENT_ERROR": 1,
    }
    assert summary["targets"] == {"citation_format": 2, "tool_schema": 1}


def test_diagnostic_summary_recomputes_failed_records_and_ignores_passed_warnings():
    records = [
        {
            "passed": True,
            "failure_modes": [
                {"mode": "TOOL_EMPTY_RESULT", "target": "tool_schema"}
            ],
        },
        {
            "passed": False,
            "summary": {
                "parallel_batch_passed": False,
                "required_tools_passed": True,
            },
            "actual": {"tool_batches": [[{"name": "mongodb_query", "args": {}}]]},
        },
    ]

    summary = diagnostic_summary(records)

    assert summary["failure_modes"] == {"PARALLELISM_REGRESSION": 1}
    assert summary["targets"] == {"prompt_routing": 1}
