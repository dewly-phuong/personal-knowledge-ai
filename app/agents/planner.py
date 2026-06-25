from __future__ import annotations

import re
from typing import Any, Literal

from langchain_core.messages import BaseMessage
from pydantic import BaseModel, Field


AgentName = Literal["router", "search", "visual", "answer"]


class AgentTask(BaseModel):
    task_id: str
    agent: AgentName
    tool_name: str
    args: dict[str, Any] = Field(default_factory=dict)
    source_label: str


class AgentPlan(BaseModel):
    intent: Literal["answer", "research", "visual"] = "research"
    parallel_groups: list[list[AgentTask]] = Field(default_factory=list)
    needs_visual: bool = False
    visual_request: dict[str, Any] = Field(default_factory=dict)


def latest_user_text(messages: list[BaseMessage]) -> str:
    for message in reversed(messages):
        if message.type == "human":
            return str(message.content or "")
    return str(messages[-1].content or "") if messages else ""


class RuleBasedTaskPlanner:
    """Deterministic fallback planner for common internal retrieval patterns."""

    def plan(self, messages: list[BaseMessage]) -> AgentPlan:
        query = latest_user_text(messages)
        query_lower = query.lower()
        tasks: list[AgentTask] = []

        entity = _extract_named_entity(query)
        if entity:
            tasks.append(
                AgentTask(
                    task_id="entity-1",
                    agent="search",
                    tool_name="entity_search",
                    args={"entity_name": entity, "query": query},
                    source_label=f"Graph: {entity}",
                )
            )

        for collection in _collections_for_query(query_lower):
            tasks.append(
                AgentTask(
                    task_id=f"mongo-{len(tasks) + 1}",
                    agent="search",
                    tool_name="mongodb_query",
                    args={
                        "collection": collection,
                        "filter_json": _default_filter_for_collection(collection, query),
                        "projection_json": '{"_id": 0}',
                        "limit": 100,
                    },
                    source_label=f"MongoDB: {collection}",
                )
            )

        if _mentions_upload(query_lower):
            tasks.append(
                AgentTask(
                    task_id=f"upload-{len(tasks) + 1}",
                    agent="search",
                    tool_name="uploaded_file_context",
                    args={"query": query},
                    source_label="Upload: current session",
                )
            )

        if _needs_wiki(query_lower, has_entity=entity is not None):
            tasks.append(
                AgentTask(
                    task_id=f"wiki-{len(tasks) + 1}",
                    agent="search",
                    tool_name="wiki_search",
                    args={"query": query},
                    source_label="Wiki: search",
                )
            )

        if not tasks:
            tasks.append(
                AgentTask(
                    task_id="wiki-1",
                    agent="search",
                    tool_name="wiki_search",
                    args={"query": query},
                    source_label="Wiki: search",
                )
            )

        needs_visual = _needs_visual(query_lower)
        return AgentPlan(
            intent="visual" if needs_visual else "research",
            parallel_groups=[tasks],
            needs_visual=needs_visual,
            visual_request=_visual_request(query) if needs_visual else {},
        )


class ModelTaskPlanner:
    """LLM-backed planner with a deterministic fallback if structured output fails."""

    def __init__(self, llm, fallback: RuleBasedTaskPlanner | None = None):
        self.llm = llm
        self.fallback = fallback or RuleBasedTaskPlanner()

    def plan(self, messages: list[BaseMessage]) -> AgentPlan:
        query = latest_user_text(messages)
        fallback_plan = self.fallback.plan(messages)
        planner_prompt = (
            "Create an internal assistant retrieval plan as AgentPlan JSON. "
            "Use only these tools: uploaded_file_context, entity_search, wiki_search, "
            "mongodb_query, generate_chart. Group independent search tasks in the same "
            "parallel_groups item. Do not include generate_chart until after retrieval; "
            "set needs_visual=true instead. User query:\n"
            f"{query}"
        )
        try:
            structured = self.llm.with_structured_output(AgentPlan)
            plan = structured.invoke(planner_prompt)
            if isinstance(plan, AgentPlan) and plan.parallel_groups:
                return _merge_with_fallback(plan, fallback_plan)
        except Exception:
            pass
        return fallback_plan


def _extract_named_entity(query: str) -> str | None:
    query_lower = query.lower()
    known_matches = [
        (query_lower.index(entity.lower()), entity)
        for entity in _KNOWN_ENTITIES
        if entity.lower() in query_lower
    ]
    if known_matches:
        return sorted(known_matches)[0][1]

    quoted = re.findall(r'"([^"]+)"|\'([^\']+)\'', query)
    for left, right in quoted:
        value = (left or right).strip()
        if value:
            return value

    patterns = [
        r"\b(Project\s+[A-Z][\w-]+(?:\s+[A-Z][\w-]+)*)",
        r"\b([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){1,3})\b",
        r"\b([A-Z][a-z]+[A-Z][A-Za-z0-9]*)\b",
        r"\b([a-z]+(?:-[a-z0-9]+)+)\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, query)
        if match:
            return match.group(1).strip()
    return None


def _collections_for_query(query_lower: str) -> list[str]:
    mappings: list[tuple[tuple[str, ...], str]] = [
        (("incident", "incidents", "sự cố", "bug", "hotfix"), "bug_tracker"),
        (("sales", "revenue", "doanh thu", "mrr", "nrr", "gross margin", "churn"), "revenue_2024"),
        (("cloud", "cost", "infra", "infrastructure", "chi phí"), "infrastructure_costs_sep2024"),
        (("objective", "okr", "kpi", "objectives"), "kpi_okr"),
        (("payroll", "lương", "salary", "net_salary"), "payroll_september_2024"),
        (("attendance", "chấm công", "muộn", "remote", "nghỉ phép", "nghỉ ốm"), "attendance_october_2024"),
        (("employee", "nhân sự", "headcount", "staff", "phòng kỹ thuật"), "employees"),
        (("model", "champion", "villm"), "model_registry"),
        (("roadmap", "budget", "progress", "project", "dự án", "tech_stack"), "projects"),
        (("task", "ticket", "iteration", "sprint"), "sprint_tickets"),
        (("crm", "customer", "khách hàng", "enterprise", "contract", "health", "at risk"), "crm_customers"),
        (("recruitment", "tuyển", "ứng viên", "candidate"), "recruitment_pipeline"),
    ]
    collections: list[str] = []
    for keywords, collection in mappings:
        if any(keyword in query_lower for keyword in keywords):
            collections.append(collection)
    return list(dict.fromkeys(collections))


def _default_filter_for_collection(collection: str, query: str) -> str:
    entity = _extract_named_entity(query)
    if collection == "projects" and entity:
        code = _project_code(entity)
        if code:
            return '{"code":"%s"}' % code
        return '{"name": {"$regex": "%s", "$options": "i"}}' % entity.replace('"', '\\"')
    return "{}"


def _mentions_upload(query_lower: str) -> bool:
    return any(word in query_lower for word in ("upload", "file", "tệp", "đính kèm"))


def _needs_visual(query_lower: str) -> bool:
    return any(word in query_lower for word in ("chart", "biểu đồ", "graph", "visual", "vẽ"))


def _needs_wiki(query_lower: str, has_entity: bool) -> bool:
    if has_entity:
        return False
    return any(word in query_lower for word in ("policy", "process", "quy trình", "chính sách"))


def _visual_request(query: str) -> dict[str, Any]:
    query_lower = query.lower()
    chart_type = "line" if "line" in query_lower else "pie" if "pie" in query_lower else "bar"
    chart_count = (
        2
        if any(
            marker in query_lower
            for marker in (
                "2 biểu đồ",
                "hai biểu đồ",
                "2 chart",
                "total_mrr_vnd và active_customers",
                "headcount theo department và bar chart",
            )
        )
        or query_lower.count(" chart") >= 2
        else 1
    )
    return {"chart_type": chart_type, "title": query[:80] or "Chart", "chart_count": chart_count}


def _merge_with_fallback(plan: AgentPlan, fallback_plan: AgentPlan) -> AgentPlan:
    planned_tasks = list(plan.parallel_groups[0]) if plan.parallel_groups else []
    planned_keys = {_task_key(task) for task in planned_tasks}
    additions = [
        task
        for task in (fallback_plan.parallel_groups[0] if fallback_plan.parallel_groups else [])
        if _task_key(task) not in planned_keys
    ]
    if additions:
        first_group = planned_tasks + additions
        other_groups = plan.parallel_groups[1:] if plan.parallel_groups else []
        plan.parallel_groups = [first_group] + other_groups
    plan.needs_visual = plan.needs_visual or fallback_plan.needs_visual
    if not plan.visual_request:
        plan.visual_request = fallback_plan.visual_request
    elif fallback_plan.visual_request:
        plan.visual_request["chart_count"] = max(
            int(plan.visual_request.get("chart_count", 1) or 1),
            int(fallback_plan.visual_request.get("chart_count", 1) or 1),
        )
    if plan.needs_visual:
        plan.intent = "visual"
    return plan


def _task_key(task: AgentTask) -> tuple[str, str, str]:
    return (
        task.tool_name,
        str(task.args.get("collection", "")),
        str(task.args.get("entity_name", "")).lower(),
    )


def _project_code(entity: str) -> str:
    return {
        "VisionChat": "VISION-CHAT",
        "DataPulse": "DATAPULSE",
        "SaigonBank": "SGB-CHATBOT",
    }.get(entity, "")


_KNOWN_ENTITIES = [
    "VisionChat",
    "NLU Service",
    "DataPulse",
    "AI Research",
    "SaigonBank",
    "MegaMart Vietnam",
    "MegaMart",
    "Lý Ngọc Hân",
    "Engineering Department",
]
