"""
SSE streaming handler for the Chainlit on_message event.

Parses the server-sent event stream from the FastAPI backend and dispatches
each event type (thinking, step_start, step_end, chart, token, done, error)
to the appropriate Chainlit UI call.
"""

import json
import logging

import chainlit as cl
import plotly.io as pio

from app.chainlit_citations import resolve_citations

logger = logging.getLogger(__name__)


async def handle_sse_stream(response, thinking_buffer: list, active_steps: dict):
    """
    Reads SSE lines from `response` and drives the Chainlit UI.

    Returns the final streamed_msg (cl.Message | None).
    """
    streamed_msg: cl.Message | None = None

    async def flush_thinking():
        nonlocal thinking_buffer
        if not thinking_buffer:
            return
        step = cl.Step(name="💭 Suy nghĩ", type="run")
        step.output = "".join(thinking_buffer)
        await step.send()
        thinking_buffer.clear()

    async for line in response.aiter_lines():
        if not line.startswith("data: "):
            continue
        try:
            data = json.loads(line[6:])
            dtype = data.get("type")

            if dtype == "thinking":
                thinking_buffer.append(data["token"])

            elif dtype == "step_start":
                await flush_thinking()
                step = cl.Step(name=data.get("name"), type="tool")
                step.input = data.get("input", "")
                await step.send()
                active_steps[data.get("name")] = step

            elif dtype == "step_end":
                last_name = list(active_steps.keys())[-1] if active_steps else None
                if last_name:
                    step = active_steps.pop(last_name)
                    raw_out = data.get("output", "")
                    step.output = (
                        "Chart generated."
                        if raw_out.startswith("CHART_JSON:")
                        else raw_out
                    )
                    await step.update()

            elif dtype == "chart":
                await flush_thinking()
                try:
                    fig = pio.from_json(data["chart_json"])
                    await cl.Message(
                        content="📊",
                        elements=[
                            cl.Plotly(
                                name="chart",
                                figure=fig,
                                display="inline",
                                size="large",
                            )
                        ],
                    ).send()
                except Exception as chart_err:
                    logger.warning(f"Error rendering chart: {chart_err}")

            elif dtype == "token":
                await flush_thinking()
                if streamed_msg is None:
                    streamed_msg = cl.Message(content="")
                    await streamed_msg.send()
                token_val = data["token"]
                if isinstance(token_val, list):
                    token_val = "".join(
                        p["text"] if isinstance(p, dict) and "text" in p else str(p)
                        for p in token_val
                    )
                elif isinstance(token_val, dict) and "text" in token_val:
                    token_val = token_val["text"]
                await streamed_msg.stream_token(token_val)

            elif dtype == "done":
                await flush_thinking()
                final_output = data.get("output", "")
                resolved = resolve_citations(final_output)
                if streamed_msg is not None:
                    streamed_msg.content = resolved
                    await streamed_msg.update()
                else:
                    streamed_msg = cl.Message(content=resolved)
                    await streamed_msg.send()

            elif dtype == "error":
                err = data.get("error", "Unknown error")
                if streamed_msg:
                    await streamed_msg.stream_token(f"\n\n⚠️ {err}")
                else:
                    await cl.Message(content=f"⚠️ {err}").send()

        except json.JSONDecodeError as json_err:
            print(f"Error parsing SSE chunk: {json_err} — line: {line[:120]}")

    return streamed_msg
