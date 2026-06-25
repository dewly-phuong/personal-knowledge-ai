from __future__ import annotations

from typing import Annotated, Any, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

from app.agents.planner import AgentPlan
from app.agents.search import ToolExecutionResult


class AgentState(TypedDict, total=False):
    messages: Annotated[list[BaseMessage], add_messages]
    session_id: str
    upload_ids: list[str]
    plan: AgentPlan
    retrieval_results: list[ToolExecutionResult]
    sources: list[str]
    artifacts: list[dict[str, Any]]
    final_answer: str
