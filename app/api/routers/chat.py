from typing import List, Dict

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from langchain_core.messages import (
    HumanMessage,
    AIMessage,
    SystemMessage,
    BaseMessage,
    messages_to_dict,
)

from app.api.schemas import ChatRequest, SyncHistoryRequest
from app.api.streaming import chat_generator

router = APIRouter(prefix="/api/chat", tags=["chat"])

_ROLE_TO_MESSAGE: Dict[str, type] = {
    "user": HumanMessage,
    "assistant": AIMessage,
    "system": SystemMessage,
}


def _to_langchain_messages(messages: List[Dict[str, str]]) -> List[BaseMessage]:
    """Converts [{role, content}] dicts to LangChain message objects."""
    return [
        _ROLE_TO_MESSAGE[msg["role"]](content=msg.get("content", ""))
        for msg in messages
        if msg.get("role") in _ROLE_TO_MESSAGE
    ]


@router.post("")
async def chat_stream(body: ChatRequest, req: Request):
    """Streams chat tokens and intermediate tool execution steps from the agent."""
    return StreamingResponse(
        chat_generator(body.query, body.session_id, req.app.state.history_manager),
        media_type="text/event-stream",
    )


@router.get("/{session_id}")
async def get_chat_history(session_id: str, req: Request):
    """Retrieves the raw conversation history messages for a given session."""
    messages = await req.app.state.session_store.load(session_id)
    return {"messages": messages_to_dict(messages)}


@router.delete("/{session_id}")
async def clear_chat_history(session_id: str, req: Request):
    """Clears history for a given session."""
    await req.app.state.history_manager.clear(session_id)
    return {
        "status": "ok",
        "message": f"Chat history for session {session_id} has been cleared",
    }


@router.post("/{session_id}/sync")
async def sync_chat_history(session_id: str, body: SyncHistoryRequest, req: Request):
    """Syncs/overwrites the conversation history for a given session."""
    langchain_messages = _to_langchain_messages(body.messages)
    store = req.app.state.session_store
    await store.save(session_id, langchain_messages)
    await store.flush()
    return {
        "status": "ok",
        "message": f"Chat history for session {session_id} synced successfully.",
    }
