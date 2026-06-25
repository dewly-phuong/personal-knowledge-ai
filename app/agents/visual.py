from __future__ import annotations

import json
from typing import Any

from app.agents.planner import AgentPlan
from app.agents.search import ToolExecutionResult


def build_visual_artifacts(
    plan: AgentPlan, retrieval_results: list[ToolExecutionResult]
) -> list[dict[str, Any]]:
    if not plan.needs_visual:
        return []

    request = dict(plan.visual_request or {})
    artifact: dict[str, Any] = {
        "type": "chart_request",
        "chart_type": request.get("chart_type", "bar"),
        "title": request.get("title", "Chart"),
        "sources": [result.source_label for result in retrieval_results],
    }

    chart_json = _extract_chart_json(retrieval_results)
    if chart_json:
        artifact["type"] = "chart"
        artifact["chart_json"] = chart_json

    return [artifact]


def _extract_chart_json(retrieval_results: list[ToolExecutionResult]) -> str:
    for result in retrieval_results:
        output = result.output.strip()
        if output.startswith("CHART_JSON:"):
            return output[len("CHART_JSON:") :]
        try:
            parsed = json.loads(output)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict) and parsed.get("chart_json"):
            return str(parsed["chart_json"])
    return ""
