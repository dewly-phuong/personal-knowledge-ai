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


def diagnostic_summary(records: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    modes: Counter[str] = Counter()
    targets: Counter[str] = Counter()
    tools: Counter[str] = Counter()
    suites: Counter[str] = Counter()

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

    return {
        "failure_modes": dict(modes),
        "targets": dict(targets),
        "tools": dict(tools),
        "suites": dict(suites),
    }
