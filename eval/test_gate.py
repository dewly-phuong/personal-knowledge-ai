import json

from eval.gate import evaluate_gates, main


def test_critical_gate_fails_below_min_pass_rate():
    decision = evaluate_gates(
        [{"metrics": [{"name": "Faithfulness", "score": 0.8, "passed": False}]}],
        {"release_gates": {"critical": {"faithfulness_pass_rate": {"min": 0.95}}}},
    )

    assert not decision.passed
    assert decision.failures[0]["metric"] == "faithfulness_pass_rate"


def test_gate_passes_when_critical_threshold_is_met():
    decision = evaluate_gates(
        [{"passed": True, "metrics": [{"name": "Faithfulness", "score": 1.0, "passed": True}]}],
        {
            "release_gates": {
                "critical": {
                    "task_success_rate": {"min": 1.0},
                    "faithfulness_pass_rate": {"min": 1.0},
                }
            }
        },
    )

    assert decision.passed
    assert decision.failures == []


def test_missing_critical_metric_fails_closed():
    decision = evaluate_gates(
        [{"metrics": [{"name": "Answer Relevancy", "score": 1.0, "passed": True}]}],
        {"release_gates": {"critical": {"faithfulness_pass_rate": {"min": 0.95}}}},
    )

    assert not decision.passed
    assert decision.failures[0]["reason"] == "metric missing from scores"


def test_gate_cli_returns_nonzero_for_failed_critical_gate(tmp_path):
    scores = tmp_path / "scores.jsonl"
    rules = tmp_path / "release-gates.yaml"
    scores.write_text(
        json.dumps(
            {
                "run_id": "run1",
                "passed": True,
                "metrics": [{"name": "Faithfulness", "score": 0.4, "passed": False}],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    rules.write_text(
        """
release_gates:
  critical:
    faithfulness_pass_rate:
      min: 0.95
""".strip(),
        encoding="utf-8",
    )

    assert main(["--scores", str(scores), "--rules", str(rules)]) == 1
