from __future__ import annotations

import json
import pathlib
from collections import Counter
from typing import Any

from eval.failure_modes import classify_failure_modes


def parse_traces_file(path: pathlib.Path, run_id: str = "latest") -> list[dict]:
    rows = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not rows:
        return []
    if run_id == "latest":
        selected_run_id = rows[-1].get("run_id")
        return [row for row in rows if row.get("run_id") == selected_run_id]
    if run_id == "all":
        return rows
    return [row for row in rows if row.get("run_id") == run_id]


def diagnostic_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    modes: Counter[str] = Counter()
    targets: Counter[str] = Counter()
    tools: Counter[str] = Counter()
    collections: Counter[str] = Counter()
    suites: Counter[str] = Counter()
    failed_cases: list[dict[str, Any]] = []

    for record in records:
        if record.get("suite"):
            suites[str(record["suite"])] += 1
        failures = classify_failure_modes(record) if record.get("passed") is False else []
        for failure in failures:
            if failure.get("mode"):
                modes[str(failure["mode"])] += 1
            if failure.get("target"):
                targets[str(failure["target"])] += 1
        actual = record.get("actual") or {}
        for call in actual.get("tool_calls") or []:
            if call.get("name"):
                tools[str(call["name"])] += 1
            collection = _arg_value(call, "collection")
            if collection:
                collections[str(collection)] += 1
        if record.get("passed") is False:
            failed_cases.append(_failed_case_summary(record, failures))

    return {
        "failure_modes": dict(modes),
        "targets": dict(targets),
        "tools": dict(tools),
        "collections": dict(collections),
        "suites": dict(suites),
        "failed_cases": failed_cases,
    }


def _failed_case_summary(
    record: dict[str, Any], failures: list[dict[str, str]]
) -> dict[str, Any]:
    actual = record.get("actual") or {}
    targets = _ordered_unique(failure["target"] for failure in failures if failure.get("target"))
    return {
        "id": str(record.get("test_id") or record.get("id") or "<unknown>"),
        "question": _short_text(record.get("question") or record.get("input") or ""),
        "failure_modes": _ordered_unique(
            failure["mode"] for failure in failures if failure.get("mode")
        ),
        "targets": targets,
        "tool_batches": _compact_batches(actual.get("tool_batches") or []),
        "tool_outputs": _tool_output_previews(actual.get("tool_outputs") or []),
        "final_answer": _short_text(actual.get("final_answer") or ""),
        "suggested_fix": _suggested_fix(targets),
    }


def _compact_batches(batches: list[list[dict[str, Any]]]) -> list[list[str]]:
    return [[_compact_tool_call(call) for call in batch] for batch in batches]


def _compact_tool_call(call: dict[str, Any]) -> str:
    name = str(call.get("name") or "<tool>")
    collection = _arg_value(call, "collection")
    return f"{name}:{collection}" if collection else name


def _tool_output_previews(outputs: list[dict[str, Any]], limit: int = 5) -> list[str]:
    previews = []
    for output in outputs[:limit]:
        name = str(output.get("name") or "<tool>")
        previews.append(f"{name}: {_short_text(output.get('output') or '')}")
    return previews


def _arg_value(call: dict[str, Any], key: str) -> Any:
    args = call.get("args") or {}
    if isinstance(args, dict):
        return args.get(key)
    return None


def _ordered_unique(values) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = str(value)
        if text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _short_text(value: Any, limit: int = 500) -> str:
    text = str(value).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _suggested_fix(targets: list[str]) -> str:
    for target in targets:
        if target == "prompt_routing":
            return "Review prompt routing rules for this scenario."
        if target == "tool_schema":
            return "Tighten tool argument hints or collection schema guidance."
        if target == "answer_synthesis":
            return "Review answer synthesis and grounding instructions."
        if target == "citation_format":
            return "Review source citation formatting rules."
        if target == "memory_management":
            return "Review multi-turn memory and history handling."
    return "Inspect trace and update the responsible component."
