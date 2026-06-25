from __future__ import annotations

from typing import Any, Callable

from app.agents.planner import latest_user_text


Answerer = Callable[[dict[str, Any]], str]


class ModelAnswerer:
    def __init__(self, llm, system_prompt: str):
        self.llm = llm
        self.system_prompt = system_prompt

    def __call__(self, state: dict[str, Any]) -> str:
        prompt = self._build_prompt(state)
        response = self.llm.invoke(prompt)
        return _message_text(response)

    async def ainvoke(self, state: dict[str, Any]) -> str:
        prompt = self._build_prompt(state)
        response = await self.llm.ainvoke(prompt)
        return _message_text(response)

    def _build_prompt(self, state: dict[str, Any]) -> str:
        messages = state.get("messages", [])
        query = latest_user_text(messages)
        retrieval_context = _format_retrieval_context(state)
        return (
            f"{self.system_prompt}\n\n"
            "<retrieved_context>\n"
            f"{retrieval_context}\n"
            "</retrieved_context>\n\n"
            "Use only retrieved_context to answer. Include the required Vietnamese "
            "source citation block.\n\n"
            f"User question: {query}"
        )


class FallbackAnswerer:
    def __call__(self, state: dict[str, Any]) -> str:
        results = state.get("retrieval_results") or []
        if not results:
            return (
                "Tôi không tìm thấy thông tin cụ thể trong dữ liệu nội bộ được truy xuất.\n\n"
                "Nguồn:\n- Không có nguồn hợp lệ"
            )

        lines = ["Dữ liệu nội bộ đã truy xuất:"]
        for result in results:
            snippet = result.output[:800] if result.output else result.error
            lines.append(f"- {result.source_label}: {snippet}")

        sources = "\n".join(f"- {source}" for source in state.get("sources", []))
        return "\n".join(lines) + f"\n\nNguồn:\n{sources}"

    async def ainvoke(self, state: dict[str, Any]) -> str:
        return self(state)


def _format_retrieval_context(state: dict[str, Any]) -> str:
    parts: list[str] = []
    for result in state.get("retrieval_results") or []:
        status = f"ERROR: {result.error}" if result.error else result.output
        parts.append(
            f"[{result.task_id}] {result.source_label} via {result.tool_name}\n{status}"
        )
    if state.get("artifacts"):
        parts.append(f"[visual_artifacts]\n{state['artifacts']}")
    return "\n\n".join(parts)


def _message_text(message: Any) -> str:
    content = getattr(message, "content", message)
    if isinstance(content, list):
        return "".join(
            part.get("text", "") if isinstance(part, dict) else str(part)
            for part in content
        )
    return str(content or "")
