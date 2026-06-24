import json

from eval.generate_report import parse_scores_file


def test_parse_scores_file_includes_parallel_function_calling(tmp_path):
    path = tmp_path / "scores.jsonl"
    row = {
        "run_id": "run1",
        "test_id": "PFC001",
        "file": "test_parallel_function_calling",
        "passed": True,
        "duration": 1.5,
        "input": "question",
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
    path.write_text(json.dumps(row), encoding="utf-8")

    grouped = parse_scores_file(path)

    assert grouped["parallel"][0]["id"] == "PFC001"
    assert grouped["parallel"][0]["label"] == "parallel"
