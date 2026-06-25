import json

from eval.dataset_manifest import (
    build_manifest,
    sync_adapters,
    validate_manifest,
    write_manifest,
)


def test_build_manifest_wraps_existing_suite_payloads(tmp_path):
    datasets = tmp_path / "datasets"
    datasets.mkdir()
    (datasets / "single_turn_goldens.json").write_text(
        json.dumps(
            [
                {
                    "id": "ST001",
                    "input": "VisionChat accuracy?",
                    "expected_output": "92.3%",
                    "context": [],
                }
            ]
        ),
        encoding="utf-8",
    )
    (datasets / "parallel_function_calling_questions.json").write_text(
        json.dumps(
            [
                {
                    "id": "PFC001",
                    "question": "Fetch project and chart data",
                    "expected_parallel_group_1": [{"tool": "mongodb_query"}],
                }
            ]
        ),
        encoding="utf-8",
    )

    records = build_manifest(datasets)

    assert [record["id"] for record in records] == ["ST001", "PFC001"]
    assert records[0]["suite"] == "single_turn"
    assert records[0]["payload"]["input"] == "VisionChat accuracy?"
    assert records[0]["metrics"] == [
        "answer_relevancy",
        "faithfulness",
        "graph_reasoning",
        "domain_faithfulness",
        "tool_correctness",
    ]
    assert records[1]["suite"] == "parallel_function_calling"
    assert records[1]["risk_level"] == "high"


def test_validate_manifest_reports_unknown_suite_and_missing_fields():
    errors = validate_manifest(
        [
            {"id": "X001", "suite": "unknown", "payload": {}},
            {"id": "ST001", "suite": "single_turn", "payload": {"input": "Q"}},
        ]
    )

    assert "X001: unknown suite unknown" in errors
    assert "ST001: payload missing expected_output" in errors


def test_sync_adapters_round_trips_suite_payloads(tmp_path):
    datasets = tmp_path / "datasets"
    datasets.mkdir()
    records = [
        {
            "id": "ST001",
            "suite": "single_turn",
            "risk_level": "medium",
            "tags": ["golden"],
            "metrics": [],
            "source_dataset": "single_turn_goldens.json",
            "split": "test",
            "human_label": None,
            "payload": {
                "id": "ST001",
                "input": "Q",
                "expected_output": "A",
                "context": [],
            },
        },
        {
            "id": "PROD-001",
            "suite": "production_replay",
            "risk_level": "high",
            "tags": ["production", "regression"],
            "metrics": [],
            "source_dataset": "production_regression_candidates.jsonl",
            "split": "production_audit",
            "human_label": None,
            "payload": {"id": "PROD-001", "question": "Q"},
        },
    ]

    sync_adapters(records, datasets)

    single = json.loads((datasets / "single_turn_goldens.json").read_text())
    prod = [
        json.loads(line)
        for line in (datasets / "production_regression_candidates.jsonl")
        .read_text()
        .splitlines()
    ]
    assert single == [records[0]["payload"]]
    assert prod == [records[1]["payload"]]


def test_write_manifest_rejects_invalid_records(tmp_path):
    out = tmp_path / "eval_suite.json"

    errors = write_manifest(
        [{"id": "ST001", "suite": "single_turn", "payload": {"input": "Q"}}],
        out,
    )

    assert "ST001: payload missing expected_output" in errors
    assert not out.exists()
