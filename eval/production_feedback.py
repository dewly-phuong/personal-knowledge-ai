from __future__ import annotations

import hashlib
import json
import pathlib
import re
from typing import Any


EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b")
PHONE_RE = re.compile(r"\b(?:\+?84|0)(?:[\s.-]?\d){8,10}\b")
OBJECT_ID_RE = re.compile(r"\b[0-9a-fA-F]{24}\b")


def candidate_regressions_from_feedback(
    feedbacks: list[dict[str, Any]],
    steps: list[dict[str, Any]],
    traces: list[dict[str, Any]] | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    step_by_id = {str(step.get("id")): step for step in steps if step.get("id")}
    steps_by_thread = _steps_by_thread(steps)
    trace_by_key = _trace_index(traces or [])
    candidates: list[dict[str, Any]] = []

    for feedback in feedbacks:
        if not _is_actionable_feedback(feedback):
            continue
        target_step = step_by_id.get(str(feedback.get("forId")))
        if target_step is None:
            continue

        trace = _matching_trace(feedback, target_step, trace_by_key)
        thread_steps = steps_by_thread.get(str(feedback.get("threadId")), [])
        candidates.append(_candidate_from_feedback(feedback, target_step, thread_steps, trace))
        if limit is not None and len(candidates) >= limit:
            break
    return candidates


def write_candidates_jsonl(path: pathlib.Path, candidates: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = "\n".join(json.dumps(row, ensure_ascii=False) for row in candidates)
    path.write_text(content + ("\n" if content else ""), encoding="utf-8")


def read_documents_file(path: pathlib.Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []
    if path.suffix == ".jsonl":
        return [json.loads(line) for line in text.splitlines() if line.strip()]
    data = json.loads(text)
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and isinstance(data.get("documents"), list):
        return data["documents"]
    raise ValueError(f"{path} must contain a JSON array, documents array, or JSONL rows")


def redact_sensitive(value: Any) -> Any:
    if isinstance(value, str):
        return _redact_text(value)
    if isinstance(value, list):
        return [redact_sensitive(item) for item in value]
    if isinstance(value, dict):
        return {key: redact_sensitive(item) for key, item in value.items()}
    return value


def _candidate_from_feedback(
    feedback: dict[str, Any],
    target_step: dict[str, Any],
    thread_steps: list[dict[str, Any]],
    trace: dict[str, Any] | None,
) -> dict[str, Any]:
    question = _question_for_step(target_step, thread_steps)
    actual = trace.get("actual") if trace else _actual_from_thread_steps(target_step, thread_steps)
    feedback_id = str(feedback.get("id") or "")
    step_id = str(target_step.get("id") or "")
    thread_id = str(feedback.get("threadId") or target_step.get("threadId") or "")
    return {
        "id": _candidate_id(thread_id, step_id, feedback_id),
        "source": "production_feedback",
        "thread_id": thread_id,
        "question": redact_sensitive(question),
        "actual_answer": redact_sensitive(_answer_for_step(target_step)),
        "expected": {
            "tools": [],
            "parallel_group_1": [],
            "sequential_group_2": [],
            "answer_checks": [],
            "sources": [],
            "needs_human_review": True,
        },
        "actual": redact_sensitive(actual or {}),
        "feedback": {
            "id": feedback_id,
            "forId": step_id,
            "value": feedback.get("value"),
            "comment": redact_sensitive(feedback.get("comment") or ""),
        },
        "metadata": {
            "feedback_id": feedback_id,
            "step_id": step_id,
            "trace_id": trace.get("id") if trace else None,
        },
    }


def _is_actionable_feedback(feedback: dict[str, Any]) -> bool:
    comment = str(feedback.get("comment") or "").strip()
    if comment:
        return True
    value = feedback.get("value")
    if isinstance(value, (int, float)):
        return value <= 0
    return str(value).strip().lower() in {
        "-1",
        "0",
        "false",
        "down",
        "thumbs_down",
        "negative",
    }


def _steps_by_thread(steps: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for step in steps:
        grouped.setdefault(str(step.get("threadId") or ""), []).append(step)
    return grouped


def _trace_index(traces: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    indexed = {}
    for trace in traces:
        thread_id = str(
            trace.get("thread_id")
            or trace.get("threadId")
            or (trace.get("metadata") or {}).get("thread_id")
            or ""
        )
        step_id = str(
            trace.get("step_id")
            or trace.get("stepId")
            or (trace.get("metadata") or {}).get("step_id")
            or ""
        )
        if thread_id and step_id:
            indexed[(thread_id, step_id)] = trace
    return indexed


def _matching_trace(
    feedback: dict[str, Any],
    target_step: dict[str, Any],
    trace_by_key: dict[tuple[str, str], dict[str, Any]],
) -> dict[str, Any] | None:
    thread_id = str(feedback.get("threadId") or target_step.get("threadId") or "")
    step_id = str(feedback.get("forId") or target_step.get("id") or "")
    return trace_by_key.get((thread_id, step_id))


def _question_for_step(
    target_step: dict[str, Any], thread_steps: list[dict[str, Any]]
) -> str:
    if target_step.get("input"):
        return str(target_step["input"])

    target_index = _step_index(target_step, thread_steps)
    for step in reversed(thread_steps[:target_index]):
        if _is_user_step(step):
            return str(step.get("output") or step.get("input") or "")
    return str(target_step.get("input") or "")


def _answer_for_step(target_step: dict[str, Any]) -> str:
    return str(target_step.get("output") or target_step.get("input") or "")


def _actual_from_thread_steps(
    target_step: dict[str, Any], thread_steps: list[dict[str, Any]]
) -> dict[str, Any]:
    tool_steps = [
        step
        for step in thread_steps
        if step.get("parentId") == target_step.get("id") or _is_tool_step(step)
    ]
    return {
        "tool_calls": [
            {"name": str(step.get("name") or step.get("type") or "tool"), "args": {}}
            for step in tool_steps
        ],
        "tool_outputs": [
            {
                "name": str(step.get("name") or step.get("type") or "tool"),
                "output": str(step.get("output") or ""),
            }
            for step in tool_steps
            if step.get("output")
        ],
        "final_answer": _answer_for_step(target_step),
    }


def _step_index(target_step: dict[str, Any], thread_steps: list[dict[str, Any]]) -> int:
    target_id = target_step.get("id")
    for index, step in enumerate(thread_steps):
        if step.get("id") == target_id:
            return index
    return len(thread_steps)


def _is_user_step(step: dict[str, Any]) -> bool:
    marker = f"{step.get('type', '')} {step.get('name', '')}".lower()
    return "user" in marker


def _is_tool_step(step: dict[str, Any]) -> bool:
    marker = f"{step.get('type', '')} {step.get('name', '')}".lower()
    return "tool" in marker


def _candidate_id(thread_id: str, step_id: str, feedback_id: str) -> str:
    digest = hashlib.sha1(
        f"{thread_id}:{step_id}:{feedback_id}".encode("utf-8")
    ).hexdigest()[:10]
    return f"PROD-{digest}"


def _redact_text(text: str) -> str:
    text = EMAIL_RE.sub("[REDACTED_EMAIL]", text)
    text = PHONE_RE.sub("[REDACTED_PHONE]", text)
    return OBJECT_ID_RE.sub("[REDACTED_OBJECT_ID]", text)
