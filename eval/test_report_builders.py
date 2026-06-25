from eval._report_builders import build_html, build_markdown


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


def test_build_markdown_includes_failed_case_diagnostic_details():
    diagnostics = {
        "failure_modes": {"PARALLELISM_REGRESSION": 1},
        "targets": {"prompt_routing": 1},
        "collections": {"revenue_2024": 1, "bug_tracker": 1},
        "tools": {"mongodb_query": 2},
        "suites": {},
        "failed_cases": [
            {
                "id": "PFC018",
                "question": "Board summary",
                "failure_modes": ["PARALLELISM_REGRESSION"],
                "targets": ["prompt_routing"],
                "tool_batches": [["mongodb_query:revenue_2024", "mongodb_query:bug_tracker"]],
                "tool_outputs": ["mongodb_query: No records found"],
                "final_answer": "Không đủ dữ liệu",
                "suggested_fix": "Review prompt routing rules for this scenario.",
            }
        ],
    }

    markdown = build_markdown([], [], "now", diagnostics=diagnostics)

    assert "Failure details" in markdown
    assert "PFC018" in markdown
    assert "mongodb_query:revenue_2024" in markdown
    assert "No records found" in markdown
    assert "Không đủ dữ liệu" in markdown
    assert "Review prompt routing rules" in markdown


def test_build_html_includes_diagnostic_details():
    diagnostics = {
        "failure_modes": {"PARALLELISM_REGRESSION": 1},
        "targets": {"prompt_routing": 1},
        "collections": {"bug_tracker": 1},
        "tools": {"mongodb_query": 1},
        "suites": {},
        "failed_cases": [
            {
                "id": "PFC018",
                "question": "Board summary",
                "failure_modes": ["PARALLELISM_REGRESSION"],
                "targets": ["prompt_routing"],
                "tool_batches": [["mongodb_query:bug_tracker"]],
                "tool_outputs": ["mongodb_query: No records found"],
                "final_answer": "Không đủ dữ liệu",
                "suggested_fix": "Review prompt routing rules for this scenario.",
            }
        ],
    }

    html = build_html([], [], "now", diagnostics=diagnostics)

    assert "Diagnostic details" in html
    assert "PFC018" in html
    assert "mongodb_query:bug_tracker" in html
