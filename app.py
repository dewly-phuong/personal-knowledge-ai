"""
Chainlit application entry point.

Lifecycle hooks: auth, starters, chat start/resume/end.
Message handling delegates heavy work to app.chainlit_streaming.
"""

import logging
from typing import Optional

import chainlit as cl
import httpx
from fastapi import Request, Response
from chainlit.types import ThreadDict

from app.chainlit_citations import resolve_citations
from app.chainlit_streaming import handle_sse_stream
from app.chainlit_uploads import process_message_uploads
from app.memory.mongodb_data_layer import MongoDBDataLayer

logger = logging.getLogger(__name__)

_API_BASE = "http://localhost:8000"


# ── Data layer ────────────────────────────────────────────────────────────────


@cl.data_layer
def get_data_layer():
    return MongoDBDataLayer()


# ── Auth ──────────────────────────────────────────────────────────────────────


@cl.password_auth_callback
def auth_callback(username: str, password: str) -> Optional[cl.User]:
    if (username, password) == ("admin", "admin"):
        return cl.User(identifier="admin", metadata={"role": "ADMIN"})
    return None


@cl.on_logout
def on_logout(request: Request, response: Response):
    for cookie_name in request.cookies.keys():
        response.delete_cookie(cookie_name)


# ── Chat starters ─────────────────────────────────────────────────────────────


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


# ── Chat lifecycle ────────────────────────────────────────────────────────────


@cl.on_chat_start
async def start():
    user = cl.user_session.get("user")
    logger.info(f"{user.identifier if user else 'Guest'} has started the conversation")
    session_id = cl.context.session.id
    cl.user_session.set("session_id", session_id)

    api_url = f"{_API_BASE}/api/chat/{session_id}"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(api_url)
            if resp.status_code == 200:
                history_data = resp.json()
                for msg in history_data.get("messages", []):
                    msg_type = msg.get("type")
                    content = msg.get("data", {}).get("content", "")
                    if not content:
                        continue
                    if msg_type == "human":
                        await cl.Message(content=content, author="User").send()
                    elif msg_type == "ai":
                        await cl.Message(
                            content=resolve_citations(content), author="Assistant"
                        ).send()
    except Exception as e:
        logger.warning(f"Failed to retrieve chat history on start: {e}")


@cl.on_chat_resume
async def on_chat_resume(thread: ThreadDict):
    """Sync backend history on resume. Charts are restored automatically by the data layer."""
    session_id = thread.get("id", cl.context.session.id)
    cl.user_session.set("session_id", session_id)

    sync_messages = [
        {
            "role": "user" if step.get("type") == "user_message" else "assistant",
            "content": step.get("output", ""),
        }
        for step in thread["steps"]
        if step.get("type") in ("user_message", "assistant_message")
        and step.get("output")
    ]

    api_url = f"{_API_BASE}/api/chat/{session_id}/sync"
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


# ── Message handler ───────────────────────────────────────────────────────────


@cl.on_message
async def on_message(message: cl.Message):
    session_id = cl.user_session.get("session_id")
    user = cl.user_session.get("user")
    upload_ids = await process_message_uploads(message, session_id, user)

    payload = {
        "query": message.content,
        "session_id": session_id,
        "upload_ids": upload_ids,
    }

    thinking_buffer: list[str] = []
    active_steps: dict = {}

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream(
                "POST", f"{_API_BASE}/api/chat", json=payload
            ) as response:
                if response.status_code != 200:
                    await cl.Message(
                        content=f"Error from server: HTTP {response.status_code}"
                    ).send()
                    return
                streamed_msg = await handle_sse_stream(
                    response, thinking_buffer, active_steps
                )

        if streamed_msg:
            await streamed_msg.update()

    except Exception as e:
        await cl.Message(
            content=(
                f"Error connecting to chat API: {e}. "
                "Hãy đảm bảo server FastAPI đang chạy tại localhost:8000."
            )
        ).send()
