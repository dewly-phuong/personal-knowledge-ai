from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.runnables import RunnableLambda
from langgraph.graph import END, START, StateGraph

from app.agents.answer import FallbackAnswerer, ModelAnswerer
from app.agents.planner import ModelTaskPlanner, RuleBasedTaskPlanner
from app.agents.search import ToolRunner, default_tool_runner, execute_parallel_group
from app.agents.state import AgentState
from app.agents.visual import build_visual_artifacts


def create_langgraph_agent(
    *,
    llm=None,
    planner=None,
    tool_runner: ToolRunner | None = None,
    answerer=None,
    system_prompt: str = "",
    recursion_limit: int | None = None,
):
    planner = planner or (
        ModelTaskPlanner(llm) if llm is not None else RuleBasedTaskPlanner()
    )
    tool_runner = tool_runner or default_tool_runner
    answerer = answerer or (
        ModelAnswerer(llm, system_prompt) if llm is not None else FallbackAnswerer()
    )

    def planner_node(state: AgentState) -> dict[str, Any]:
        return {"plan": planner.plan(list(state.get("messages", [])))}

    async def aplanner_node(state: AgentState) -> dict[str, Any]:
        return planner_node(state)

    def search_node(state: AgentState) -> dict[str, Any]:
        return _run_async(asearch_node(state))

    async def asearch_node(state: AgentState) -> dict[str, Any]:
        plan = state["plan"]
        all_results = []
        tool_messages = []
        for group in plan.parallel_groups:
            tool_calls = [
                {"name": task.tool_name, "args": task.args, "id": task.task_id}
                for task in group
            ]
            tool_messages.append(AIMessage(content="", tool_calls=tool_calls))
            group_results = await execute_parallel_group(group, tool_runner)
            all_results.extend(group_results)
            for result in group_results:
                tool_messages.append(
                    ToolMessage(
                        content=result.output or result.error,
                        name=result.tool_name,
                        tool_call_id=result.task_id,
                    )
                )

        sources = []
        for result in all_results:
            if result.source_label not in sources:
                sources.append(result.source_label)

        return {
            "retrieval_results": all_results,
            "sources": sources,
            "messages": tool_messages,
        }

    def visual_node(state: AgentState) -> dict[str, Any]:
        artifacts = build_visual_artifacts(
            state["plan"], list(state.get("retrieval_results", []))
        )
        messages = []
        if state["plan"].needs_visual:
            chart_count = int(state["plan"].visual_request.get("chart_count", 1) or 1)
            tool_calls = [
                {
                    "name": "generate_chart",
                    "args": {
                        "chart_type": state["plan"].visual_request.get("chart_type", "bar"),
                        "title": state["plan"].visual_request.get("title", "Chart"),
                        "labels": [],
                        "values": [],
                    },
                    "id": f"chart-{index + 1}",
                }
                for index in range(chart_count)
            ]
            messages.append(AIMessage(content="", tool_calls=tool_calls))
            messages.extend(
                ToolMessage(
                    content="Chart request prepared from retrieved data.",
                    name="generate_chart",
                    tool_call_id=call["id"],
                )
                for call in tool_calls
            )
        return {
            "artifacts": artifacts,
            "messages": messages,
        }

    async def avisual_node(state: AgentState) -> dict[str, Any]:
        return visual_node(state)

    def answer_node(state: AgentState) -> dict[str, Any]:
        answer = answerer(dict(state))
        return {"final_answer": answer, "messages": [AIMessage(content=answer)]}

    async def aanswer_node(state: AgentState) -> dict[str, Any]:
        if hasattr(answerer, "ainvoke"):
            answer = await answerer.ainvoke(dict(state))
            return {"final_answer": answer, "messages": [AIMessage(content=answer)]}
        return answer_node(state)

    graph = StateGraph(AgentState)
    graph.add_node("planner", RunnableLambda(planner_node, afunc=aplanner_node))
    graph.add_node("search_agent", RunnableLambda(search_node, afunc=asearch_node))
    graph.add_node("visual_agent", RunnableLambda(visual_node, afunc=avisual_node))
    graph.add_node("answer_agent", RunnableLambda(answer_node, afunc=aanswer_node))

    graph.add_edge(START, "planner")
    graph.add_edge("planner", "search_agent")
    graph.add_edge("search_agent", "visual_agent")
    graph.add_edge("visual_agent", "answer_agent")
    graph.add_edge("answer_agent", END)

    compiled = graph.compile()
    if recursion_limit is not None:
        return compiled.with_config({"recursion_limit": recursion_limit})
    return compiled


def _run_async(coro):
    return __import__("asyncio").run(coro)
