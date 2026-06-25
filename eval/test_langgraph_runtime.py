import asyncio
import time

from langchain_core.messages import AIMessage, HumanMessage


def test_rule_based_planner_groups_independent_entity_and_record_tasks():
    from app.agents.planner import RuleBasedTaskPlanner

    plan = RuleBasedTaskPlanner().plan(
        [HumanMessage(content="Project Helios là gì và có incident nào liên quan?")]
    )

    assert plan.intent == "research"
    first_group_tools = {task.tool_name for task in plan.parallel_groups[0]}
    assert {"entity_search", "mongodb_query"} <= first_group_tools


def test_search_executor_runs_parallel_groups_concurrently():
    from app.agents.planner import AgentTask
    from app.agents.search import execute_parallel_group

    starts: list[str] = []

    async def fake_runner(task: AgentTask) -> str:
        starts.append(task.task_id)
        await asyncio.sleep(0.05)
        return f"result:{task.task_id}"

    tasks = [
        AgentTask(
            task_id="entity-1",
            agent="search",
            tool_name="entity_search",
            args={"entity_name": "Project Helios", "query": "q"},
            source_label="Graph: Project Helios",
        ),
        AgentTask(
            task_id="records-1",
            agent="search",
            tool_name="mongodb_query",
            args={"collection": "incident_log", "filter_json": "{}"},
            source_label="MongoDB: incident_log",
        ),
    ]

    started = time.perf_counter()
    results = asyncio.run(execute_parallel_group(tasks, fake_runner))
    elapsed = time.perf_counter() - started

    assert elapsed < 0.09
    assert starts == ["entity-1", "records-1"]
    assert [result.output for result in results] == ["result:entity-1", "result:records-1"]


def test_langgraph_agent_returns_messages_sources_and_artifacts_with_injected_components():
    from app.agents.graph import create_langgraph_agent
    from app.agents.planner import AgentPlan, AgentTask

    class StaticPlanner:
        def plan(self, messages):
            return AgentPlan(
                intent="visual",
                parallel_groups=[
                    [
                        AgentTask(
                            task_id="records-1",
                            agent="search",
                            tool_name="mongodb_query",
                            args={"collection": "sales_summary_2026", "filter_json": "{}"},
                            source_label="MongoDB: sales_summary_2026",
                        )
                    ]
                ],
                needs_visual=True,
                visual_request={"chart_type": "bar", "title": "Sales"},
            )

    async def fake_tool_runner(task):
        return '[{"month": "2026-01", "total_revenue_vnd": 100}]'

    def fake_answerer(state):
        return "Doanh thu tháng 1 là 100 VND.\n\nNguồn:\n- MongoDB: sales_summary_2026"

    agent = create_langgraph_agent(
        planner=StaticPlanner(),
        tool_runner=fake_tool_runner,
        answerer=fake_answerer,
    )

    result = agent.invoke({"messages": [HumanMessage(content="Vẽ biểu đồ doanh thu")]})

    assert result["final_answer"].startswith("Doanh thu tháng 1")
    assert result["sources"] == ["MongoDB: sales_summary_2026"]
    assert result["artifacts"][0]["type"] == "chart_request"
    assert isinstance(result["messages"][-1], AIMessage)
