from __future__ import annotations

from collections import Counter
from typing import Any


Failure = dict[str, str]


def classify_failure_modes(trace: dict[str, Any]) -> list[Failure]:
    failures: list[Failure] = []
    expected = trace.get("expected") or {}
    actual = trace.get("actual") or {}

    _add_missing_required_tools(failures, expected, actual)
    _add_summary_failures(failures, trace)
    _add_parallelism_failures(failures, expected, actual)
    _add_sequential_failures(failures, expected, actual)
    _add_argument_failures(failures, expected, actual)
    _add_tool_output_failures(failures, actual)
    _add_answer_failures(failures, trace)
    return _dedupe_failures(failures)


def _add_summary_failures(failures: list[Failure], trace: dict[str, Any]) -> None:
    summary = trace.get("summary") or {}
    if summary.get("required_tools_passed") is False:
        missing = summary.get("missing_required_tools") or {}
        failures.append(
            {
                "mode": "MISSING_REQUIRED_TOOL",
                "target": "prompt_routing",
                "detail": f"Missing required tools: {missing}.",
            }
        )
    if summary.get("parallel_batch_passed") is False:
        failures.append(
            {
                "mode": "PARALLELISM_REGRESSION",
                "target": "prompt_routing",
                "detail": "Required first-group tools were called, but not in the same batch.",
            }
        )
    if summary.get("sequential_tools_passed") is False:
        missing = summary.get("missing_sequential_tools") or {}
        failures.append(
            {
                "mode": "SEQUENTIAL_STEP_MISS",
                "target": "prompt_routing",
                "detail": f"Missing required sequential tools: {missing}.",
            }
        )


def _add_missing_required_tools(
    failures: list[Failure], expected: dict[str, Any], actual: dict[str, Any]
) -> None:
    expected_tools = _expected_tool_names(expected.get("tools") or [])
    expected_tools.extend(
        _expected_tool_names(expected.get("parallel_group_1") or [])
    )
    if not expected_tools:
        return

    missing = Counter(expected_tools) - Counter(_actual_tool_names(actual))
    if missing:
        failures.append(
            {
                "mode": "MISSING_REQUIRED_TOOL",
                "target": "prompt_routing",
                "detail": (
                    "Missing required tools: "
                    + ", ".join(sorted(missing.elements()))
                    + "."
                ),
            }
        )


def _add_parallelism_failures(
    failures: list[Failure], expected: dict[str, Any], actual: dict[str, Any]
) -> None:
    required = [
        item
        for item in expected.get("parallel_group_1") or []
        if not item.get("optional")
    ]
    if len(required) < 2:
        return

    if any(_batch_satisfies(batch, required) for batch in actual.get("tool_batches") or []):
        return

    flattened = actual.get("tool_calls") or []
    if _batch_satisfies(flattened, required):
        failures.append(
            {
                "mode": "PARALLELISM_REGRESSION",
                "target": "prompt_routing",
                "detail": "Required first-group tools were called, but not in the same batch.",
            }
        )


def _add_sequential_failures(
    failures: list[Failure], expected: dict[str, Any], actual: dict[str, Any]
) -> None:
    expected_seq = _expected_tool_names(expected.get("sequential_group_2") or [])
    if not expected_seq:
        return
    missing = Counter(expected_seq) - Counter(_actual_tool_names(actual))
    if missing:
        failures.append(
            {
                "mode": "SEQUENTIAL_STEP_MISS",
                "target": "prompt_routing",
                "detail": (
                    "Missing required sequential tools: "
                    + ", ".join(sorted(missing.elements()))
                    + "."
                ),
            }
        )


def _add_argument_failures(
    failures: list[Failure], expected: dict[str, Any], actual: dict[str, Any]
) -> None:
    expected_calls = []
    expected_calls.extend(expected.get("tools") or [])
    expected_calls.extend(expected.get("parallel_group_1") or [])
    expected_calls.extend(expected.get("sequential_group_2") or [])

    for expected_call in expected_calls:
        hint = _item_value(expected_call, "args_hint") or {}
        tool = _item_value(expected_call, "tool") or _item_value(expected_call, "name")
        if not tool or not hint:
            continue
        matching_actual = [
            call for call in actual.get("tool_calls") or [] if call.get("name") == tool
        ]
        if not matching_actual:
            continue
        for field in ("collection", "entity_name", "chart_type"):
            expected_value = hint.get(field)
            if expected_value is None:
                continue
            if not any(_arg_matches(call, field, expected_value) for call in matching_actual):
                got = _first_arg_value(matching_actual, field)
                failures.append(
                    {
                        "mode": "TOOL_ARGUMENT_ERROR",
                        "target": "tool_schema",
                        "detail": f"{tool} expected {field} {expected_value} but got {got}.",
                    }
                )


def _add_tool_output_failures(failures: list[Failure], actual: dict[str, Any]) -> None:
    for output in actual.get("tool_outputs") or []:
        text = str(output.get("output") or "")
        name = output.get("name") or "tool"
        if text.startswith("Error") or " Syntax Error" in text:
            failures.append(
                {
                    "mode": "TOOL_ERROR",
                    "target": "tool_implementation",
                    "detail": f"{name} returned an error output.",
                }
            )
        elif text.startswith("No records found"):
            failures.append(
                {
                    "mode": "TOOL_EMPTY_RESULT",
                    "target": "tool_schema",
                    "detail": f"{name} returned no records.",
                }
            )


def _add_answer_failures(failures: list[Failure], trace: dict[str, Any]) -> None:
    actual = trace.get("actual") or {}
    final = str(actual.get("final_answer") or "")
    if trace.get("passed") is False and final and "Nguồn:" not in final:
        failures.append(
            {
                "mode": "CITATION_MISSING",
                "target": "citation_format",
                "detail": "Final answer is missing the required 'Nguồn:' citation block.",
            }
        )

    failed_metrics = [
        str(metric.get("name") or "")
        for metric in trace.get("metrics") or []
        if metric.get("passed") is False
    ]
    if any("Faithfulness" in name for name in failed_metrics):
        failures.append(
            {
                "mode": "GROUNDING_ERROR",
                "target": "answer_synthesis",
                "detail": "A faithfulness metric failed; inspect unsupported answer claims.",
            }
        )
    if any("Relevancy" in name or "Completeness" in name for name in failed_metrics):
        failures.append(
            {
                "mode": "ANSWER_INCOMPLETE",
                "target": "answer_synthesis",
                "detail": "An answer relevance or completeness metric failed.",
            }
        )


def _expected_tool_names(items: list[dict[str, Any]]) -> list[str]:
    names: list[str] = []
    for item in items:
        if _item_value(item, "optional"):
            continue
        name = _item_value(item, "tool") or _item_value(item, "name")
        if name:
            names.append(str(name))
    return names


def _item_value(item: Any, key: str) -> Any:
    if isinstance(item, dict):
        return item.get(key)
    return getattr(item, key, None)


def _actual_tool_names(actual: dict[str, Any]) -> list[str]:
    return [call.get("name", "") for call in actual.get("tool_calls") or []]


def _batch_satisfies(
    actual_calls: list[dict[str, Any]], expected_calls: list[dict[str, Any]]
) -> bool:
    unmatched = list(expected_calls)
    for actual in actual_calls:
        for index, expected in enumerate(unmatched):
            tool = expected.get("tool") or expected.get("name")
            if actual.get("name") != tool:
                continue
            hint = expected.get("args_hint") or {}
            if all(_arg_matches(actual, field, value) for field, value in hint.items()):
                unmatched.pop(index)
                break
    return not unmatched


def _arg_matches(actual: dict[str, Any], field: str, expected_value: Any) -> bool:
    actual_value = (actual.get("args") or {}).get(field)
    if actual_value == expected_value:
        return True
    if actual_value is None:
        return False
    actual_text = str(actual_value).lower()
    expected_text = str(expected_value).lower()
    return expected_text in actual_text or actual_text in expected_text


def _first_arg_value(calls: list[dict[str, Any]], field: str) -> str:
    for call in calls:
        if field in (call.get("args") or {}):
            return str((call.get("args") or {}).get(field))
    return "<missing>"


def _dedupe_failures(failures: list[Failure]) -> list[Failure]:
    seen: set[tuple[str, str, str]] = set()
    result: list[Failure] = []
    for failure in failures:
        key = (failure["mode"], failure["target"], failure["detail"])
        if key in seen:
            continue
        seen.add(key)
        result.append(failure)
    return result
