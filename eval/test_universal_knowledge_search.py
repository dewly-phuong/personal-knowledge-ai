"""
Universal knowledge-search trace evaluation for the current agent architecture.

This eval verifies the model follows the high-level retrieval policy:
  - factual/internal questions call `knowledge_search` before answering;
  - `knowledge_search` returns one normalized result for every registered source;
  - empty/error sources expose `data=null`;
  - chart requests search knowledge before calling `generate_chart`.

The test is intentionally gated because it invokes the live agent/model.

Run:
    RUN_LIVE_AGENT_EVAL=1 uv run pytest eval/test_universal_knowledge_search.py -q

Run a single case:
    RUN_LIVE_AGENT_EVAL=1 uv run pytest eval/test_universal_knowledge_search.py -q -k UKS001
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

import pytest
from dotenv import load_dotenv

from eval.trace_capture import (
    called_tool_names,
    final_answer,
    tool_batches,
    tool_outputs,
)

load_dotenv()


@dataclass(frozen=True)
class UniversalSearchCase:
    case_id: str
    question: str
    expects_chart: bool = False


CASES = [
    UniversalSearchCase(
        case_id="UKS001",
        question="Độ chính xác của mô hình NLP ViLLM-v2 của VisionChat là bao nhiêu?",
    ),
    UniversalSearchCase(
        case_id="UKS002",
        question="Tổng hợp thông tin về doanh thu hoặc MRR của VisionChat trong dữ liệu hiện có.",
    ),
    UniversalSearchCase(
        case_id="UKS003",
        question="Vẽ biểu đồ doanh thu theo tháng nếu dữ liệu hiện có hỗ trợ.",
        expects_chart=True,
    ),
]


@pytest.mark.parametrize("case", CASES, ids=[case.case_id for case in CASES])
def test_agent_uses_universal_knowledge_search(case: UniversalSearchCase, request):
    if os.getenv("RUN_LIVE_AGENT_EVAL") != "1":
        pytest.skip("Set RUN_LIVE_AGENT_EVAL=1 to invoke the live agent/model.")
    if not os.getenv("GOOGLE_API_KEY"):
        pytest.skip("GOOGLE_API_KEY not set.")

    from app.agent import create_conversational_agent

    agent = create_conversational_agent()
    result = agent.invoke({"messages": [{"role": "user", "content": case.question}]})
    messages = result.get("messages", [])

    batches = tool_batches(messages)
    tool_names = called_tool_names(messages)
    outputs = tool_outputs(messages, max_chars=500_000)
    knowledge_payloads, parse_errors = _knowledge_search_payloads(outputs)
    answer = final_answer(messages)
    metrics = _evaluate_trace(
        case=case,
        answer=answer,
        tool_names=tool_names,
        knowledge_payloads=knowledge_payloads,
        parse_errors=parse_errors,
    )

    request.node.user_properties.append(
        (
            "diagnostic_trace",
            {
                "suite": "universal_knowledge_search",
                "question": case.question,
                "expected": {
                    "first_tool": "knowledge_search",
                    "source_names": sorted(_registered_source_names()),
                    "expects_chart": case.expects_chart,
                },
                "actual": {
                    "tool_batches": batches,
                    "tool_calls": [call for batch in batches for call in batch],
                    "tool_outputs": outputs,
                    "final_answer": answer,
                },
            },
        )
    )
    request.node.user_properties.append(("deepeval_metric_snapshot", metrics))

    failed = [metric for metric in metrics if not metric["passed"]]
    assert not failed, "; ".join(
        f"{metric['name']}: {metric['reason']}" for metric in failed
    )


def _knowledge_search_payloads(
    outputs: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    payloads: list[dict[str, Any]] = []
    errors: list[str] = []
    for output in outputs:
        if output.get("name") != "knowledge_search":
            continue
        try:
            payload = json.loads(str(output.get("output") or ""))
        except json.JSONDecodeError as exc:
            errors.append(f"knowledge_search returned non-JSON output: {exc}")
            continue
        if not isinstance(payload, dict):
            errors.append("knowledge_search output must be a JSON object.")
            continue
        payloads.append(payload)
    return payloads, errors


def _evaluate_trace(
    *,
    case: UniversalSearchCase,
    answer: str,
    tool_names: list[str],
    knowledge_payloads: list[dict[str, Any]],
    parse_errors: list[str],
) -> list[dict[str, Any]]:
    metrics = [
        _binary_metric(
            "Final Answer Presence",
            bool(answer.strip()),
            "Agent returned a non-empty final answer."
            if answer.strip()
            else "Agent returned no final answer.",
        ),
        _binary_metric(
            "Knowledge Search First Tool",
            bool(tool_names) and tool_names[0] == "knowledge_search",
            "knowledge_search was the first tool call."
            if bool(tool_names) and tool_names[0] == "knowledge_search"
            else f"First tool was {tool_names[0] if tool_names else None}.",
        ),
        _binary_metric(
            "Knowledge Search JSON Output",
            bool(knowledge_payloads) and not parse_errors,
            "All knowledge_search outputs were parseable JSON objects."
            if bool(knowledge_payloads) and not parse_errors
            else "; ".join(parse_errors)
            or "No parseable knowledge_search output found.",
        ),
    ]

    metrics.extend(_bundle_contract_metrics(knowledge_payloads))
    if case.expects_chart:
        chart_order_passed = (
            "knowledge_search" in tool_names
            and "generate_chart" in tool_names
            and tool_names.index("knowledge_search")
            < tool_names.index("generate_chart")
        )
        metrics.append(
            _binary_metric(
                "Chart Tool Ordering",
                chart_order_passed,
                "knowledge_search ran before generate_chart."
                if chart_order_passed
                else f"Actual tool order: {tool_names}",
            )
        )
    return metrics


def _bundle_contract_metrics(payloads: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not payloads:
        return [
            _binary_metric(
                "Knowledge Source Coverage",
                False,
                "No knowledge_search payload was available.",
            ),
            _binary_metric(
                "Knowledge Source Status Contract",
                False,
                "No knowledge_search payload was available.",
            ),
            _binary_metric(
                "Empty/Error Source Null Data",
                False,
                "No knowledge_search payload was available.",
            ),
        ]

    return [
        _binary_metric(
            "Knowledge Source Coverage",
            all(_source_coverage_passed(payload) for payload in payloads),
            "Every knowledge_search payload returned all registered sources."
            if all(_source_coverage_passed(payload) for payload in payloads)
            else "At least one knowledge_search payload missed a registered source.",
        ),
        _binary_metric(
            "Knowledge Source Status Contract",
            all(_status_contract_passed(payload) for payload in payloads),
            "Every source result used the normalized status contract."
            if all(_status_contract_passed(payload) for payload in payloads)
            else "At least one source result violated the normalized status contract.",
        ),
        _binary_metric(
            "Empty/Error Source Null Data",
            all(_empty_error_data_null_passed(payload) for payload in payloads),
            "Every empty/error source returned data=null."
            if all(_empty_error_data_null_passed(payload) for payload in payloads)
            else "At least one empty/error source returned non-null data.",
        ),
    ]


def _source_coverage_passed(payload: dict[str, Any]) -> bool:
    results = payload.get("results")
    if not isinstance(results, list):
        return False

    expected_sources = _registered_source_names()
    actual_sources = {
        result.get("source") for result in results if isinstance(result, dict)
    }
    return expected_sources <= actual_sources


def _status_contract_passed(payload: dict[str, Any]) -> bool:
    if not isinstance(payload.get("query"), str) or not payload["query"].strip():
        return False
    results = payload.get("results")
    if not isinstance(results, list):
        return False
    for result in results:
        if not isinstance(result, dict):
            return False
        if result.get("status") not in {"ok", "empty", "error"}:
            return False
        if not isinstance(result.get("summary"), str):
            return False
        if result["status"] == "error" and not result.get("error"):
            return False
    return True


def _empty_error_data_null_passed(payload: dict[str, Any]) -> bool:
    results = payload.get("results")
    if not isinstance(results, list):
        return False
    return all(
        not isinstance(result, dict)
        or result.get("status") not in {"empty", "error"}
        or result.get("data") is None
        for result in results
    )


def _binary_metric(name: str, passed: bool, reason: str) -> dict[str, Any]:
    return {
        "name": name,
        "score": 1.0 if passed else 0.0,
        "threshold": 1.0,
        "passed": passed,
        "reason": reason,
        "error": "",
    }


def _registered_source_names() -> set[str]:
    from app.retrieval.sources import build_default_registry

    return {source.name for source in build_default_registry().sources}
