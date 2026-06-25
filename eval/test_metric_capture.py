import pytest

import eval.conftest as conftest
from eval.metric_capture import assert_test_with_metric_capture


class _Metric:
    name = "Faithfulness"
    score = 0.42
    threshold = 0.5
    success = False
    reason = "unsupported claim"
    error = ""


class _Request:
    class Node:
        user_properties = []

    node = Node()


def test_assert_test_with_metric_capture_records_metrics_when_assertion_fails(
    monkeypatch,
):
    request = _Request()
    request.node.user_properties = []

    def failing_assert_test(**_kwargs):
        raise AssertionError("metric failed")

    monkeypatch.setattr("eval.metric_capture.assert_test", failing_assert_test)

    with pytest.raises(AssertionError):
        assert_test_with_metric_capture(
            request=request,
            test_case=object(),
            metrics=[_Metric()],
            run_async=False,
        )

    assert request.node.user_properties == [
        (
            "deepeval_metric_snapshot",
            [
                {
                    "name": "Faithfulness",
                    "score": 0.42,
                    "threshold": 0.5,
                    "passed": False,
                    "reason": "unsupported claim",
                    "error": "",
                }
            ],
        )
    ]


def test_pytest_report_writes_deepeval_metric_snapshot_to_scores(tmp_path, monkeypatch):
    scores = tmp_path / "scores.jsonl"
    monkeypatch.setattr(conftest, "SCORES_FILE", scores)
    conftest._session_results.clear()

    class Report:
        when = "call"
        nodeid = "eval/test_single_turn.py::test_single_turn[ST001]"
        passed = False
        duration = 1.25
        user_properties = [
            (
                "deepeval_metric_snapshot",
                [
                    {
                        "name": "Faithfulness",
                        "score": 0.42,
                        "threshold": 0.5,
                        "passed": False,
                        "reason": "unsupported claim",
                        "error": "",
                    }
                ],
            )
        ]

    conftest.pytest_runtest_logreport(Report())

    row = scores.read_text(encoding="utf-8")
    assert '"metrics": [{"name": "Faithfulness"' in row


def test_pytest_report_ignores_non_eval_tests_without_metrics(tmp_path, monkeypatch):
    scores = tmp_path / "scores.jsonl"
    monkeypatch.setattr(conftest, "SCORES_FILE", scores)
    conftest._session_results.clear()

    class Report:
        when = "call"
        nodeid = "eval/test_metric_capture.py::test_helper"
        passed = True
        duration = 0.01
        user_properties = []

    conftest.pytest_runtest_logreport(Report())

    assert not scores.exists()


def test_pytest_report_ignores_skipped_eval_tests(tmp_path, monkeypatch):
    scores = tmp_path / "scores.jsonl"
    monkeypatch.setattr(conftest, "SCORES_FILE", scores)
    conftest._session_results.clear()

    class Report:
        when = "call"
        nodeid = "eval/test_single_turn.py::test_single_turn[ST001]"
        passed = False
        skipped = True
        duration = 0.01
        user_properties = []

    conftest.pytest_runtest_logreport(Report())

    assert not scores.exists()
