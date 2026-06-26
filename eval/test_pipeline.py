import json
import subprocess

from eval import pipeline


def test_build_dataset_writes_manifest_from_existing_adapters(tmp_path):
    datasets = tmp_path / "datasets"
    datasets.mkdir()
    (datasets / "single_turn_goldens.json").write_text(
        json.dumps(
            [{"id": "ST001", "input": "Q", "expected_output": "A", "context": []}]
        ),
        encoding="utf-8",
    )

    exit_code = pipeline.main(
        [
            "build-dataset",
            "--datasets-dir",
            str(datasets),
            "--manifest",
            "eval_suite.json",
        ]
    )

    assert exit_code == 0
    manifest = json.loads((datasets / "eval_suite.json").read_text(encoding="utf-8"))
    assert manifest[0]["suite"] == "single_turn"


def test_validate_dataset_returns_nonzero_for_invalid_manifest(tmp_path):
    manifest = tmp_path / "eval_suite.json"
    manifest.write_text(
        json.dumps(
            [{"id": "ST001", "suite": "single_turn", "payload": {"input": "Q"}}]
        ),
        encoding="utf-8",
    )

    assert pipeline.main(["validate-dataset", "--manifest", str(manifest)]) == 1


def test_run_pipeline_invokes_pytest_report_and_gate(monkeypatch, tmp_path):
    datasets = tmp_path / "datasets"
    result = tmp_path / "result"
    reports = tmp_path / "reports"
    datasets.mkdir()
    result.mkdir()
    (datasets / "eval_suite.json").write_text(
        json.dumps(
            [
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
                }
            ]
        ),
        encoding="utf-8",
    )
    rules = tmp_path / "release-gates.yaml"
    rules.write_text("release_gates:\n", encoding="utf-8")

    calls = []

    def fake_run(cmd, check=False):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(pipeline.subprocess, "run", fake_run)

    exit_code = pipeline.main(
        [
            "run",
            "--datasets-dir",
            str(datasets),
            "--manifest",
            str(datasets / "eval_suite.json"),
            "--result-dir",
            str(result),
            "--reports-dir",
            str(reports),
            "--rules",
            str(rules),
            "--pytest-args",
            "eval/test_single_turn.py",
        ]
    )

    assert exit_code == 0
    assert any("pytest" in command for call in calls for command in call)
    assert any("eval.generate_report" in call for call in calls)
    assert any("eval.gate" in call for call in calls)
    assert list(result.glob("run_config-*.json"))


def test_run_pipeline_defaults_to_code_based_eval_first(monkeypatch, tmp_path):
    datasets = tmp_path / "datasets"
    result = tmp_path / "result"
    reports = tmp_path / "reports"
    datasets.mkdir()
    result.mkdir()
    (datasets / "eval_suite.json").write_text(
        json.dumps(
            [
                {
                    "id": "PFC001",
                    "suite": "parallel_function_calling",
                    "risk_level": "high",
                    "tags": ["golden", "tool_calling", "parallel"],
                    "metrics": [],
                    "source_dataset": "parallel_function_calling_questions.json",
                    "split": "test",
                    "human_label": None,
                    "payload": {
                        "id": "PFC001",
                        "question": "Q",
                        "expected_parallel_group_1": [{"tool": "mongodb_query"}],
                    },
                }
            ]
        ),
        encoding="utf-8",
    )
    rules = tmp_path / "release-gates.yaml"
    rules.write_text("release_gates:\n", encoding="utf-8")
    calls = []

    def fake_run(cmd, check=False):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(pipeline.subprocess, "run", fake_run)

    assert (
        pipeline.main(
            [
                "run",
                "--datasets-dir",
                str(datasets),
                "--manifest",
                str(datasets / "eval_suite.json"),
                "--result-dir",
                str(result),
                "--reports-dir",
                str(reports),
                "--rules",
                str(rules),
            ]
        )
        == 0
    )

    pytest_calls = [call for call in calls if "pytest" in call]
    assert len(pytest_calls) == 2
    suite_args = [item for item in pytest_calls[0] if item.startswith("eval/test_")]
    assert suite_args[0] == "eval/test_universal_knowledge_search.py"
    llm_suite_args = [item for item in pytest_calls[1] if item.startswith("eval/test_")]
    assert llm_suite_args == [
        "eval/test_single_turn.py",
        "eval/test_multi_turn.py",
        "eval/test_conversation_dataset.py",
    ]


def test_run_pipeline_stops_before_llm_eval_when_code_based_eval_fails(
    monkeypatch, tmp_path
):
    datasets = tmp_path / "datasets"
    result = tmp_path / "result"
    reports = tmp_path / "reports"
    datasets.mkdir()
    result.mkdir()
    (datasets / "eval_suite.json").write_text(
        json.dumps(
            [
                {
                    "id": "PFC001",
                    "suite": "parallel_function_calling",
                    "risk_level": "high",
                    "tags": ["golden", "tool_calling", "parallel"],
                    "metrics": [],
                    "source_dataset": "parallel_function_calling_questions.json",
                    "split": "test",
                    "human_label": None,
                    "payload": {
                        "id": "PFC001",
                        "question": "Q",
                        "expected_parallel_group_1": [{"tool": "mongodb_query"}],
                    },
                }
            ]
        ),
        encoding="utf-8",
    )
    calls = []

    def fake_run(cmd, check=False):
        calls.append(cmd)
        if "eval/test_universal_knowledge_search.py" in cmd:
            return subprocess.CompletedProcess(cmd, 1)
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(pipeline.subprocess, "run", fake_run)

    exit_code = pipeline.main(
        [
            "run",
            "--datasets-dir",
            str(datasets),
            "--manifest",
            str(datasets / "eval_suite.json"),
            "--result-dir",
            str(result),
            "--reports-dir",
            str(reports),
        ]
    )

    assert exit_code == 1
    pytest_calls = [call for call in calls if "pytest" in call]
    assert len(pytest_calls) == 1
    assert "eval/test_universal_knowledge_search.py" in pytest_calls[0]
    assert "eval/test_single_turn.py" not in pytest_calls[0]
    assert "eval/test_multi_turn.py" not in pytest_calls[0]
    assert "eval/test_conversation_dataset.py" not in pytest_calls[0]
    assert not any("eval.generate_report" in call for call in calls)
