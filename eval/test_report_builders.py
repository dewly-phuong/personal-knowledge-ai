from eval._report_builders import build_markdown


def test_build_markdown_includes_parallel_and_diagnostics():
    parallel = [
        {
            "id": "PFC001",
            "passed": True,
            "duration": 1.2,
            "input": "question",
            "summary": {},
            "metrics": [
                {
                    "name": "Parallel Batch Compliance",
                    "score": 1.0,
                    "threshold": 1.0,
                    "passed": True,
                    "reason": "ok",
                }
            ],
        }
    ]
    diagnostics = {
        "failure_modes": {"TOOL_ARGUMENT_ERROR": 2},
        "targets": {"tool_schema": 2},
        "tools": {},
        "suites": {},
    }

    markdown = build_markdown(
        [],
        [],
        "now",
        parallel=parallel,
        diagnostics=diagnostics,
    )

    assert "Parallel function calling" in markdown
    assert "Diagnostic summary" in markdown
    assert "TOOL_ARGUMENT_ERROR" in markdown
    assert "tool_schema" in markdown
