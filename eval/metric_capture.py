from typing import Any

from deepeval import assert_test


def metric_to_dict(metric: Any) -> dict[str, Any]:
    return {
        "name": getattr(metric, "name", ""),
        "score": round(float(getattr(metric, "score", 0) or 0), 4),
        "threshold": float(getattr(metric, "threshold", 0) or 0),
        "passed": bool(getattr(metric, "success", False)),
        "reason": (getattr(metric, "reason", None) or "").strip(),
        "error": str(getattr(metric, "error", "") or ""),
    }


def metric_snapshot(metrics: list[Any]) -> list[dict[str, Any]]:
    return [metric_to_dict(metric) for metric in metrics]


def assert_test_with_metric_capture(
    *,
    request: Any,
    test_case: Any,
    metrics: list[Any],
    run_async: bool = False,
) -> None:
    try:
        assert_test(test_case=test_case, metrics=metrics, run_async=run_async)
    finally:
        request.node.user_properties.append(
            ("deepeval_metric_snapshot", metric_snapshot(metrics))
        )
