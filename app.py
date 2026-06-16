import os
import re
import chainlit as cl
import logging
import httpx
import json
import plotly.graph_objects as go
import plotly.io as pio
from typing import Optional
from fastapi import Request, Response
from chainlit.types import ThreadDict

logger = logging.getLogger(__name__)

from app.memory.mongodb_data_layer import MongoDBDataLayer

@cl.data_layer
def get_data_layer():
    return MongoDBDataLayer()

@cl.password_auth_callback
def auth_callback(username: str, password: str) -> Optional[cl.User]:
    """Password auth handler for login"""
    if (username, password) == ("admin", "admin"):
        return cl.User(identifier="admin", metadata={"role": "ADMIN"})
    return None

@cl.on_logout
def on_logout(request: Request, response: Response):
    for cookie_name in request.cookies.keys():
        response.delete_cookie(cookie_name)

@cl.set_starters
async def set_chat_starters():
    return [
        cl.Starter(
            label="Tra cứu wiki",
            message="Tìm kiếm thông tin về qmd và các tính năng chính của nó",
        ),
        cl.Starter(
            label="Xem kết nối dịch vụ",
            message="Giải thích các mối quan hệ và dependencies xung quanh auth-service",
        ),
        cl.Starter(
            label="Kiểm tra chất lượng Wiki",
            message="Hãy chạy kiểm tra sức khỏe (lint) của wiki hiện tại",
        ),
    ]

@cl.on_chat_start
async def start():
    user = cl.user_session.get("user")
    logger.info(f"{user.identifier if user else 'Guest'} has started the conversation")
    session_id = cl.context.session.id
    cl.user_session.set("session_id", session_id)
    
    # Fetch and restore past chat history for this session
    api_url = f"http://localhost:8000/api/chat/{session_id}"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(api_url)
            if resp.status_code == 200:
                history_data = resp.json()
                messages = history_data.get("messages", [])
                for msg in messages:
                    msg_type = msg.get("type")
                    content = msg.get("data", {}).get("content", "")
                    if not content:
                        continue
                        
                    if msg_type == "human":
                        await cl.Message(content=content, author="User").send()
                    elif msg_type == "ai":
                        # Resolve citations if any exist in the response
                        resolved_content = resolve_citations(content)
                        await cl.Message(content=resolved_content, author="Assistant").send()
    except Exception as e:
        logger.warning(f"Failed to retrieve chat history on start: {e}")

@cl.on_chat_resume
async def on_chat_resume(thread: ThreadDict):
    """Sync backend history on resume. Charts are restored automatically by the data layer."""
    session_id = thread.get("id", cl.context.session.id)
    cl.user_session.set("session_id", session_id)

    sync_messages = []
    for step in thread["steps"]:
        step_type = step.get("type", "")
        step_output = step.get("output", "")
        if step_type == "user_message" and step_output:
            sync_messages.append({"role": "user", "content": step_output})
        elif step_type == "assistant_message" and step_output:
            sync_messages.append({"role": "assistant", "content": step_output})

    api_url = f"http://localhost:8000/api/chat/{session_id}/sync"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(api_url, json={"messages": sync_messages})
    except Exception as e:
        logger.warning(f"Failed to sync chat history on resume: {e}")

    user = cl.user_session.get("user")
    logger.info(f"{user.identifier if user else 'Guest'} has resumed chat")

@cl.on_chat_end
def on_chat_end():
    user = cl.user_session.get("user")
    logger.info(f"{user.identifier if user else 'Guest'} has ended the chat")

def resolve_citations(text: str) -> str:
    """
    Parses references like [Nguồn: wiki/services/auth-service.md] in the text,
    reads the front matter of the cited file, and replaces it with its original
    clickable source URL (e.g. Confluence/GitHub link).
    """
    # Pattern to match [Nguồn: wiki/...] or [Nguồn: wiki\...]
    pattern = r'\[Nguồn:\s*(wiki/[^\]]+)\]'
    matches = re.findall(pattern, text)
    
    for rel_path in matches:
        # Resolve path to local workspace file
        abs_path = os.path.abspath(rel_path)
        if os.path.exists(abs_path):
            try:
                with open(abs_path, "r", encoding="utf-8") as f:
                    content = f.read()
                
                # Parse front matter for source_docs: [...]
                source_url = None
                if content.startswith("---"):
                    parts = content.split("---", 2)
                    if len(parts) >= 3:
                        yaml_text = parts[1]
                        doc_match = re.search(r'source_docs:\s*\[(.*?)\]', yaml_text)
                        if doc_match:
                            urls = [u.strip().strip("'").strip('"') for u in doc_match.group(1).split(",") if u.strip()]
                            if urls:
                                source_url = urls[0]
                
                if source_url:
                    basename = os.path.basename(rel_path)
                    replacement = f"[Nguồn: {basename}]({source_url})"
                    text = text.replace(f"[Nguồn: {rel_path}]", replacement)
            except Exception as e:
                print(f"Error parsing front matter for {rel_path}: {e}")
                
    return text

@cl.on_message
async def on_message(message: cl.Message):
    session_id = cl.user_session.get("session_id")
    url = "http://localhost:8000/api/chat"
    payload = {"query": message.content, "session_id": session_id}

    active_steps: dict = {}
    thinking_buffer: list[str] = []  # accumulate thinking tokens; flush as a single collapsed step
    streamed_msg: cl.Message | None = None

    async def flush_thinking():
        """Send all buffered thinking content as a single non-streaming collapsed step."""
        nonlocal thinking_buffer
        if not thinking_buffer:
            return
        step = cl.Step(name="💭 Suy nghĩ", type="run")
        step.output = "".join(thinking_buffer)
        await step.send()
        thinking_buffer = []

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream("POST", url, json=payload) as response:
                if response.status_code != 200:
                    await cl.Message(content=f"Error from server: HTTP {response.status_code}").send()
                    return

                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    try:
                        data = json.loads(line[6:])
                        dtype = data.get("type")

                        # ── 1. Thinking — buffer silently, emit as collapsed toggle later ─
                        if dtype == "thinking":
                            thinking_buffer.append(data["token"])

                        # ── 2. Tool call start — flush thinking first ─────────────────────
                        elif dtype == "step_start":
                            await flush_thinking()
                            step_name = data.get("name")
                            # No parent_id: tool steps are top-level timeline items so they
                            # appear above the lazily-created response message.
                            step = cl.Step(name=step_name, type="tool")
                            step.input = data.get("input", "")
                            await step.send()
                            active_steps[step_name] = step

                        # ── 3. Tool call end ──────────────────────────────────────────────
                        elif dtype == "step_end":
                            last_name = list(active_steps.keys())[-1] if active_steps else None
                            if last_name:
                                step = active_steps.pop(last_name)
                                raw_out = data.get("output", "")
                                step.output = "Chart generated." if raw_out.startswith("CHART_JSON:") else raw_out
                                await step.update()

                        # ── 4. Chart — send immediately as own message BEFORE response ────
                        elif dtype == "chart":
                            await flush_thinking()
                            try:
                                fig = pio.from_json(data["chart_json"])
                                await cl.Message(
                                    content="📊",
                                    elements=[cl.Plotly(name="chart", figure=fig, display="inline", size="large")],
                                ).send()
                            except Exception as chart_err:
                                print(f"Error rendering chart: {chart_err}")

                        # ── 5. Text token — lazy-create response message (always LAST) ────
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

                        # ── 6. Done — resolve citations and finalise ──────────────────────
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

                        # ── 7. Error ──────────────────────────────────────────────────────
                        elif dtype == "error":
                            err = data.get("error", "Unknown error")
                            if streamed_msg:
                                await streamed_msg.stream_token(f"\n\n⚠️ {err}")
                            else:
                                await cl.Message(content=f"⚠️ {err}").send()

                    except json.JSONDecodeError as json_err:
                        print(f"Error parsing SSE chunk: {json_err} — line: {line[:120]}")

        if streamed_msg:
            await streamed_msg.update()

    except Exception as e:
        await cl.Message(
            content=f"Error connecting to chat API: {e}. Hãy đảm bảo server FastAPI đang chạy tại localhost:8000."
        ).send()
