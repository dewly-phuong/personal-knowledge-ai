import json
from typing import AsyncGenerator

from langchain_core.messages import HumanMessage

from app.agent import create_conversational_agent
from app.memory.history_manager import HistoryManager
from app.services.cost_tracker import CostTracker

_cost_tracker = CostTracker()


async def chat_generator(
    query: str,
    session_id: str,
    history_manager: HistoryManager,
) -> AsyncGenerator[str, None]:
    """
    Async SSE generator — streams thinking tokens, tool steps, text tokens,
    chart payloads, and the final done event to the Chainlit frontend.
    """
    chat_history = await history_manager.get_context(session_id)
    agent = create_conversational_agent(temperature=1.0)
    input_messages = list(chat_history) + [HumanMessage(content=query)]

    total_input = 0
    total_output = 0
    output = ""
    new_messages = []

    try:
        async for event in agent.astream_events(
            {"messages": input_messages}, version="v2"
        ):
            kind = event.get("event")

            # ── 1. Streaming model output (text + thinking) ───────────────────
            if kind == "on_chat_model_stream":
                chunk = event.get("data", {}).get("chunk")
                if chunk and hasattr(chunk, "content"):
                    content = chunk.content
                    if isinstance(content, list):
                        for part in content:
                            if not isinstance(part, dict):
                                continue
                            ptype = part.get("type", "")
                            if ptype == "text" and part.get("text"):
                                yield f"data: {json.dumps({'type': 'token', 'token': part['text']})}\n\n"
                            elif ptype == "thinking" and part.get("thinking"):
                                yield f"data: {json.dumps({'type': 'thinking', 'token': part['thinking']})}\n\n"
                    elif isinstance(content, str) and content:
                        yield f"data: {json.dumps({'type': 'token', 'token': content})}\n\n"
                # langchain-google-genai also exposes thinking in additional_kwargs
                if chunk and hasattr(chunk, "additional_kwargs"):
                    thinking_text = chunk.additional_kwargs.get("thinking", "")
                    if thinking_text:
                        yield f"data: {json.dumps({'type': 'thinking', 'token': thinking_text})}\n\n"

            # ── 2. Tool call start ────────────────────────────────────────────
            elif kind == "on_tool_start":
                tool_input = event.get("data", {}).get("input", "")
                if not isinstance(tool_input, str):
                    tool_input = json.dumps(tool_input, ensure_ascii=False)
                yield f"data: {json.dumps({'type': 'step_start', 'name': event.get('name', 'tool'), 'input': tool_input})}\n\n"

            # ── 3. Tool call end ──────────────────────────────────────────────
            elif kind == "on_tool_end":
                raw_output = event.get("data", {}).get("output", "")
                tool_output = (
                    str(raw_output.content)
                    if hasattr(raw_output, "content")
                    else str(raw_output)
                )
                if tool_output.startswith("CHART_JSON:"):
                    chart_json = tool_output[len("CHART_JSON:") :]
                    yield f"data: {json.dumps({'type': 'chart', 'chart_json': chart_json})}\n\n"
                yield f"data: {json.dumps({'type': 'step_end', 'output': tool_output})}\n\n"

            # ── 4. Token usage accumulation ───────────────────────────────────
            elif kind == "on_chat_model_end":
                response = event.get("data", {}).get("output")
                if (
                    response
                    and hasattr(response, "usage_metadata")
                    and response.usage_metadata
                ):
                    usage = response.usage_metadata
                    total_input += usage.get("input_tokens", 0)
                    total_output += usage.get("output_tokens", 0)

            # ── 5. Final graph output — extract last AI message ───────────────
            elif kind == "on_chain_end" and event.get("name") == "LangGraph":
                result = event.get("data", {}).get("output", {})
                msgs = result.get("messages", [])
                if msgs:
                    last = msgs[-1]
                    raw_content = getattr(last, "content", "")
                    output = (
                        "".join(
                            p["text"] if isinstance(p, dict) and "text" in p else str(p)
                            for p in raw_content
                        )
                        if isinstance(raw_content, list)
                        else str(raw_content)
                    )
                    new_messages = msgs

    except Exception as e:
        yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"

    cost = _cost_tracker.add(total_input, total_output)
    if output or new_messages:
        await history_manager.append_turn(session_id, query, output, new_messages)
    yield f"data: {json.dumps({'type': 'done', 'output': output, 'usage': {'input': total_input, 'output': total_output}, 'cost': cost})}\n\n"
