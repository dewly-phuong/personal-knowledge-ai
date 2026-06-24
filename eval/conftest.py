"""
eval/conftest.py

Pytest plugin tự động:
  - Ghi kết quả từng metric ra eval/result/scores.jsonl sau mỗi test
  - In summary pass-rate cuối session
  - Không cần sửa gì trong test_single_turn.py hay test_multi_turn.py

Cấu trúc scores.jsonl (một dòng = một lần chạy test):
  {
    "run_id":  "20250620_143000",
    "test_id": "ST001",
    "file":    "test_single_turn",
    "passed":  true,
    "metrics": [
      {"name": "AnswerRelevancy", "score": 0.87, "passed": true, "reason": "..."},
      ...
    ]
  }
"""

import json
import pathlib
import datetime
import contextvars
from collections import defaultdict
from typing import Any

import pytest

from eval.failure_modes import classify_failure_modes

# ---------------------------------------------------------------------------
# Cấu hình
# ---------------------------------------------------------------------------

RESULT_DIR = pathlib.Path(__file__).parent / "result"
RESULT_DIR.mkdir(exist_ok=True)
SCORES_FILE = RESULT_DIR / "scores.jsonl"
TRACES_FILE = RESULT_DIR / "traces.jsonl"

# run_id duy nhất cho toàn bộ session pytest này
RUN_ID = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

# Tích lũy để tính summary cuối session
_session_results: list[dict] = []
_metric_results_by_nodeid: dict[str, list[dict]] = defaultdict(list)
_current_nodeid: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "current_pytest_nodeid", default=None
)


# ---------------------------------------------------------------------------
# Deepeval capture patch
# ---------------------------------------------------------------------------


def _metric_to_dict(metric: Any) -> dict:
    return {
        "name": getattr(metric, "name", ""),
        "score": round(float(getattr(metric, "score", 0) or 0), 4),
        "threshold": float(getattr(metric, "threshold", 0) or 0),
        "passed": bool(getattr(metric, "success", False)),
        "reason": (getattr(metric, "reason", None) or "").strip(),
        "error": str(getattr(metric, "error", "") or ""),
    }


def _capture_test_results(test_results: list[Any]) -> None:
    nodeid = _current_nodeid.get()
    if not nodeid:
        return
    for result in test_results or []:
        for metric in getattr(result, "metrics_data", []) or []:
            _metric_results_by_nodeid[nodeid].append(_metric_to_dict(metric))


def _patch_deepeval_assert_test_capture() -> None:
    try:
        import deepeval
    except Exception:
        return

    globals_ = getattr(deepeval.assert_test, "__globals__", {})
    if globals_.get("_codex_metrics_capture_patched"):
        return

    original_execute = globals_.get("execute_test_cases")
    original_a_execute = globals_.get("a_execute_test_cases")

    if original_execute is not None:

        def execute_wrapper(*args, **kwargs):
            results = original_execute(*args, **kwargs)
            _capture_test_results(results)
            return results

        globals_["execute_test_cases"] = execute_wrapper

    if original_a_execute is not None:

        async def a_execute_wrapper(*args, **kwargs):
            results = await original_a_execute(*args, **kwargs)
            _capture_test_results(results)
            return results

        globals_["a_execute_test_cases"] = a_execute_wrapper

    globals_["_codex_metrics_capture_patched"] = True


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config):
    _patch_deepeval_assert_test_capture()


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_call(item):
    token = _current_nodeid.set(item.nodeid)
    _metric_results_by_nodeid.pop(item.nodeid, None)
    try:
        yield
    finally:
        _current_nodeid.reset(token)


# ---------------------------------------------------------------------------
# Hook: chạy sau mỗi test case (call phase)
# ---------------------------------------------------------------------------


def _build_trace_entry(score_entry: dict, trace_payload: dict) -> dict:
    entry = {
        "run_id": score_entry.get("run_id", RUN_ID),
        "test_id": score_entry.get("test_id", ""),
        "file": score_entry.get("file", ""),
        "suite": trace_payload.get("suite") or score_entry.get("file", ""),
        "category": trace_payload.get("category"),
        "question": trace_payload.get("question") or score_entry.get("input"),
        "passed": bool(score_entry.get("passed")),
        "duration": float(score_entry.get("duration") or 0),
        "expected": trace_payload.get("expected") or {},
        "actual": trace_payload.get("actual") or {},
        "metrics": list(score_entry.get("metrics") or []),
        "summary": score_entry.get("summary") or trace_payload.get("summary") or {},
        "usage": trace_payload.get("usage") or {},
    }
    entry["failure_modes"] = classify_failure_modes(entry)
    entry["diagnosis"] = [item["detail"] for item in entry["failure_modes"]]
    return entry


def _write_trace_entry(entry: dict) -> None:
    try:
        with open(TRACES_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as exc:
        print(f"WARNING: could not write diagnostic trace: {exc}")


def pytest_runtest_logreport(report):
    """Ghi kết quả metric sau mỗi test vào scores.jsonl."""
    if report.when != "call":
        return

    # Tách test_id (ví dụ: ST001, MT002) từ nodeid
    # nodeid dạng: eval/test_single_turn.py::test_single_turn[ST001]
    nodeid = report.nodeid
    test_id = nodeid.split("[")[-1].rstrip("]") if "[" in nodeid else nodeid
    file_name = nodeid.split("::")[0].split("/")[-1].replace(".py", "")

    entry = {
        "run_id": RUN_ID,
        "test_id": test_id,
        "file": file_name,
        "passed": report.passed,
        "duration": round(float(getattr(report, "duration", 0) or 0), 4),
        "metrics": list(_metric_results_by_nodeid.pop(nodeid, [])),
    }

    diagnostic_trace = None

    # Fallback cho các version Deepeval/pytest có gắn metric vào user_properties.
    for key, val in getattr(report, "user_properties", []):
        if key == "deepeval_results":
            for r in val:
                entry["metrics"].append(
                    {
                        "name": r.name,
                        "score": round(float(r.score), 4),
                        "threshold": float(getattr(r, "threshold", 0) or 0),
                        "passed": bool(r.success),
                        "reason": (r.reason or "").strip(),
                        "error": str(getattr(r, "error", "") or ""),
                    }
                )
        elif key == "diagnostic_trace":
            diagnostic_trace = val
        elif key == "conversation_eval_summary":
            entry["summary"] = val
            if val.get("turn_average_score") is not None:
                entry["metrics"].append(
                    {
                        "name": "Average Turn Score",
                        "score": round(float(val["turn_average_score"]), 4),
                        "threshold": 0.0,
                        "passed": bool(val.get("turns_passed", False)),
                        "reason": "Average score across per-turn single-turn evaluations.",
                        "error": "",
                    }
                )
            if val.get("conversation_score") is not None:
                entry["metrics"].append(
                    {
                        "name": "Conversation Score",
                        "score": round(float(val["conversation_score"]), 4),
                        "threshold": 0.0,
                        "passed": bool(val.get("conversation_passed", False)),
                        "reason": "Average score across whole-conversation evaluations.",
                        "error": "",
                    }
                )
        elif key == "parallel_eval_summary":
            entry["summary"] = val
            entry["input"] = val.get("question")
            parallel_passed = bool(val.get("parallel_batch_passed", False))
            required_passed = bool(val.get("required_tools_passed", False))
            sequential_passed = bool(val.get("sequential_tools_passed", True))
            entry["metrics"].append(
                {
                    "name": "Required Tool Coverage",
                    "score": 1.0 if required_passed else 0.0,
                    "threshold": 1.0,
                    "passed": required_passed,
                    "reason": (
                        "All required tools were called."
                        if required_passed
                        else f"Missing required tools: {val.get('missing_required_tools', {})}"
                    ),
                    "error": "",
                }
            )
            entry["metrics"].append(
                {
                    "name": "Parallel Batch Compliance",
                    "score": 1.0 if parallel_passed else 0.0,
                    "threshold": 1.0,
                    "passed": parallel_passed,
                    "reason": (
                        f"Actual tool batches: {val.get('actual_batches', [])}"
                    ),
                    "error": "",
                }
            )
            if val.get("sequential_tools_expected"):
                entry["metrics"].append(
                    {
                        "name": "Sequential Tool Coverage",
                        "score": 1.0 if sequential_passed else 0.0,
                        "threshold": 1.0,
                        "passed": sequential_passed,
                        "reason": (
                            "All expected post-retrieval tools were called."
                            if sequential_passed
                            else f"Missing sequential tools: {val.get('missing_sequential_tools', {})}"
                        ),
                        "error": "",
                    }
                )

    _session_results.append(entry)

    # Ghi ngay vào file (append) — không mất dữ liệu nếu session crash giữa chừng
    with open(SCORES_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    if diagnostic_trace:
        try:
            _write_trace_entry(_build_trace_entry(entry, diagnostic_trace))
        except Exception as exc:
            print(f"WARNING: could not build diagnostic trace: {exc}")


# ---------------------------------------------------------------------------
# Hook: chạy một lần sau khi toàn bộ session kết thúc
# ---------------------------------------------------------------------------


def pytest_sessionfinish(session, exitstatus):
    """In summary pass-rate theo từng metric ra terminal."""
    if not _session_results:
        return

    # Tính pass-rate theo metric
    metric_stats: dict[str, dict] = defaultdict(
        lambda: {"passed": 0, "total": 0, "scores": []}
    )
    for entry in _session_results:
        for m in entry["metrics"]:
            s = metric_stats[m["name"]]
            s["total"] += 1
            s["passed"] += int(m["passed"])
            s["scores"].append(m["score"])

    total_tests = len(_session_results)
    passed_tests = sum(1 for e in _session_results if e["passed"])

    print(f"\n{'=' * 60}")
    print(f"  EVAL SUMMARY — run {RUN_ID}")
    print(f"{'=' * 60}")
    print(
        f"  Tests : {passed_tests}/{total_tests} passed "
        f"({'%.0f' % (passed_tests / total_tests * 100)}%)"
    )
    print(f"{'─' * 60}")
    print(f"  {'Metric':<32} {'Avg':>5}  {'Pass':>9}")
    print(f"{'─' * 60}")

    for name, s in sorted(metric_stats.items()):
        avg = sum(s["scores"]) / len(s["scores"])
        rate = s["passed"] / s["total"]
        flag = "" if rate >= 0.8 else "  ← cần xem lại"
        print(
            f"  {name:<32} {avg:>5.2f}  {s['passed']}/{s['total']} ({rate:.0%}){flag}"
        )

    print(f"{'=' * 60}")
    print(f"  Chi tiết: {SCORES_FILE}")
    print(f"{'=' * 60}\n")
