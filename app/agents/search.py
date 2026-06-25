from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from pydantic import BaseModel

from app.agents.planner import AgentTask


ToolRunner = Callable[[AgentTask], Awaitable[str] | str]


class ToolExecutionResult(BaseModel):
    task_id: str
    agent: str
    tool_name: str
    source_label: str
    output: str
    error: str = ""


async def execute_parallel_group(
    tasks: list[AgentTask], tool_runner: ToolRunner
) -> list[ToolExecutionResult]:
    async def run_one(task: AgentTask) -> ToolExecutionResult:
        try:
            maybe_result = tool_runner(task)
            if asyncio.iscoroutine(maybe_result) or isinstance(maybe_result, Awaitable):
                output = await maybe_result
            else:
                output = maybe_result
            return ToolExecutionResult(
                task_id=task.task_id,
                agent=task.agent,
                tool_name=task.tool_name,
                source_label=task.source_label,
                output=str(output),
            )
        except Exception as exc:
            return ToolExecutionResult(
                task_id=task.task_id,
                agent=task.agent,
                tool_name=task.tool_name,
                source_label=task.source_label,
                output="",
                error=str(exc),
            )

    return list(await asyncio.gather(*(run_one(task) for task in tasks)))


async def default_tool_runner(task: AgentTask) -> str:
    tool = _tool_registry().get(task.tool_name)
    if tool is None:
        raise ValueError(f"Unknown tool: {task.tool_name}")

    args: dict[str, Any] = dict(task.args or {})
    if hasattr(tool, "ainvoke"):
        result = await tool.ainvoke(args)
    elif hasattr(tool, "invoke"):
        result = await asyncio.to_thread(tool.invoke, args)
    else:
        result = await asyncio.to_thread(tool, **args)

    return str(getattr(result, "content", result))


def _tool_registry():
    from app.tools import (
        entity_search,
        generate_chart,
        mongodb_query,
        uploaded_file_context,
        wiki_search,
    )

    return {
        "uploaded_file_context": uploaded_file_context,
        "entity_search": entity_search,
        "wiki_search": wiki_search,
        "mongodb_query": mongodb_query,
        "generate_chart": generate_chart,
    }
