"""
Parallel function-calling evaluation.

This test suite validates that the agent emits multiple independent tool calls
in the same AIMessage tool-call batch for records in:

    eval/datasets/parallel_function_calling_questions.json

Run all cases:
    uv run pytest eval/test_parallel_function_calling.py -v

Run a subset:
    PFC_IDS=PFC001,PFC005 uv run pytest eval/test_parallel_function_calling.py -v

Prerequisites:
    GOOGLE_API_KEY must be set.
    MongoDB must contain the imported company collections used by mongodb_query.
"""

import json
import os
from collections import Counter
from pathlib import Path
from typing import Any

import pytest
from dotenv import load_dotenv

load_dotenv()

DATASET_PATH = Path(__file__).parent / "datasets" / "parallel_function_calling_questions.json"


def _load_records() -> list[dict[str, Any]]:
    if not DATASET_PATH.exists():
        return []

    records = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    selected = {
        item.strip()
        for item in os.getenv("PFC_IDS", "").split(",")
        if item.strip()
    }
    if selected:
        records = [record for record in records if record.get("id") in selected]
    return records


_records = _load_records()

_skip_reason: str | None = (
    f"Dataset empty or no PFC_IDS matched — missing {DATASET_PATH}"
    if not _records
    else "GOOGLE_API_KEY not set"
    if not os.getenv("GOOGLE_API_KEY")
    else None
)


def _message_content(msg: Any) -> str:
    content = getattr(msg, "content", "")
    if isinstance(content, list):
        return " ".join(
            part.get("text", "") if isinstance(part, dict) else str(part)
            for part in content
        )
    return str(content or "")


def _tool_batches(messages: list[Any]) -> list[list[dict[str, Any]]]:
    batches: list[list[dict[str, Any]]] = []
    for msg in messages:
        if type(msg).__name__ != "AIMessage":
            continue
        calls = []
        for call in getattr(msg, "tool_calls", []) or []:
            if isinstance(call, dict) and call.get("name"):
                calls.append(
                    {
                        "name": call.get("name"),
                        "args": call.get("args") or {},
                        "id": call.get("id"),
                    }
                )
        if calls:
            batches.append(calls)
    return batches


def _called_tool_names(messages: list[Any]) -> list[str]:
    names: list[str] = []
    for batch in _tool_batches(messages):
        names.extend(call["name"] for call in batch)
    return names


def _expected_parallel_calls(record: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "tool": item["tool"],
            "args_hint": item.get("args_hint") or {},
            "optional": bool(item.get("optional")),
        }
        for item in record.get("expected_parallel_group_1") or []
    ]


def _matches_expected_call(
    actual: dict[str, Any], expected: dict[str, Any], used_collections: set[str]
) -> bool:
    if actual["name"] != expected["tool"]:
        return False

    hint = expected.get("args_hint") or {}
    args = actual.get("args") or {}

    # Multiple mongodb_query calls share the same tool name. Match by collection
    # so the assertion checks the independent retrieval branches, not just names.
    expected_collection = hint.get("collection")
    if expected_collection:
        if args.get("collection") != expected_collection:
            return False
        collection_key = f"{actual.get('id')}:{expected_collection}"
        if collection_key in used_collections:
            return False
        used_collections.add(collection_key)
        return True

    expected_entity = hint.get("entity_name")
    if expected_entity:
        actual_entity = str(args.get("entity_name", "")).lower()
        return expected_entity.lower() in actual_entity or actual_entity in expected_entity.lower()

    return True


def _batch_satisfies_expected(
    batch: list[dict[str, Any]], expected_calls: list[dict[str, Any]]
) -> bool:
    unmatched = list(expected_calls)
    used_collections: set[str] = set()

    for actual in batch:
        for index, expected in enumerate(unmatched):
            if _matches_expected_call(actual, expected, used_collections):
                unmatched.pop(index)
                break

    return not unmatched


def _parallel_expectation_satisfied(
    batches: list[list[dict[str, Any]]],
    required_calls: list[dict[str, Any]],
    record: dict[str, Any],
) -> bool:
    if any(_batch_satisfies_expected(batch, required_calls) for batch in batches):
        return True

    if record.get("parallel_mode") != "lookup_then_fanout":
        return False

    lookup_collections = set(record.get("lookup_collections") or [])
    fanout_calls = [
        call
        for call in required_calls
        if (call.get("args_hint") or {}).get("collection") not in lookup_collections
    ]
    lookup_calls = [
        call
        for call in required_calls
        if (call.get("args_hint") or {}).get("collection") in lookup_collections
    ]

    if not lookup_calls or not fanout_calls:
        return False

    flattened = [call for batch in batches for call in batch]
    has_lookup = _batch_satisfies_expected(flattened, lookup_calls)
    has_all_required = _batch_satisfies_expected(flattened, required_calls)
    has_parallel_work = any(len(batch) >= 2 for batch in batches)
    return has_lookup and has_all_required and has_parallel_work


def _format_batches(batches: list[list[dict[str, Any]]]) -> str:
    if not batches:
        return "no tool-call batches"
    lines = []
    for index, batch in enumerate(batches, 1):
        parts = []
        for call in batch:
            args = call.get("args") or {}
            collection = args.get("collection")
            entity = args.get("entity_name")
            suffix = f"({collection or entity})" if collection or entity else ""
            parts.append(f"{call['name']}{suffix}")
        lines.append(f"batch {index}: " + ", ".join(parts))
    return "\n".join(lines)


def _compact_batches(batches: list[list[dict[str, Any]]]) -> list[list[str]]:
    compact: list[list[str]] = []
    for batch in batches:
        compact_batch = []
        for call in batch:
            args = call.get("args") or {}
            collection = args.get("collection")
            entity = args.get("entity_name")
            suffix = f":{collection or entity}" if collection or entity else ""
            compact_batch.append(f"{call['name']}{suffix}")
        compact.append(compact_batch)
    return compact


@pytest.mark.parametrize(
    "record",
    _records or [None],
    ids=[r.get("id", f"PFC{i + 1:03d}") for i, r in enumerate(_records)]
    if _records
    else ["skip"],
)
def test_parallel_function_calling(
    record: dict[str, Any] | None, request: pytest.FixtureRequest
):
    if _skip_reason or record is None:
        pytest.skip(_skip_reason or "no records")

    from app.agent import create_conversational_agent

    agent = create_conversational_agent(temperature=0)
    result = agent.invoke({"messages": [{"role": "user", "content": record["question"]}]})
    messages = result.get("messages", [])

    expected_calls = _expected_parallel_calls(record)
    required_calls = [call for call in expected_calls if not call.get("optional")]
    expected_counts = Counter(call["tool"] for call in required_calls)
    actual_counts = Counter(_called_tool_names(messages))
    missing_counts = expected_counts - actual_counts

    assert not missing_counts, (
        f"{record['id']} did not call expected tools. "
        f"Missing: {dict(missing_counts)}\n{_format_batches(_tool_batches(messages))}"
    )

    batches = _tool_batches(messages)
    parallel_satisfied = _parallel_expectation_satisfied(batches, required_calls, record)
    sequential_expected = Counter(
        item["tool"] for item in record.get("expected_sequential_group_2", [])
    )
    missing_sequential = sequential_expected - actual_counts

    request.node.user_properties.append(
        (
            "parallel_eval_summary",
            {
                "question": record["question"],
                "category": record.get("category"),
                "difficulty": record.get("difficulty"),
                "parallel_mode": record.get("parallel_mode", "same_batch"),
                "required_tools": [call["tool"] for call in required_calls],
                "optional_tools": [
                    call["tool"] for call in expected_calls if call.get("optional")
                ],
                "actual_batches": _compact_batches(batches),
                "parallel_batch_passed": parallel_satisfied,
                "required_tools_passed": not missing_counts,
                "sequential_tools_expected": list(sequential_expected.elements()),
                "sequential_tools_passed": not missing_sequential,
                "missing_required_tools": dict(missing_counts),
                "missing_sequential_tools": dict(missing_sequential),
            },
        )
    )

    assert parallel_satisfied, (
        f"{record['id']} did not emit expected calls in one parallel batch.\n"
        f"Question: {record['question']}\n"
        f"Expected: {[call['tool'] for call in required_calls]}\n"
        f"Optional: {[call['tool'] for call in expected_calls if call.get('optional')]}\n"
        f"Actual:\n{_format_batches(batches)}"
    )

    if "expected_sequential_group_2" in record:
        final_answer = ""
        for msg in reversed(messages):
            if type(msg).__name__ == "AIMessage":
                final_answer = _message_content(msg)
                if final_answer:
                    break
        assert not missing_sequential, (
            f"{record['id']} did not call expected sequential tools. "
            f"Missing: {dict(missing_sequential)}\n{_format_batches(batches)}\n"
            f"Final answer:\n{final_answer}"
        )
