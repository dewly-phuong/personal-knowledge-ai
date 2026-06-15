from typing import List, Optional
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage
from app.memory.session_store import SessionStore
from app.memory.summary_buffer import compress_history
import uuid

class HistoryManager:
    def __init__(self, store: SessionStore, llm=None):
        self.store = store
        self.llm = llm

    async def get_context(self, session_id: str) -> List[BaseMessage]:
        """
        Loads the raw conversation history from the store and returns a prompt-ready list of messages.
        (Context compression is handled downstream by Headroom).
        """
        raw_history = await self.store.load(session_id)
        if not raw_history:
            return []
        return raw_history

    async def append_turn(
        self,
        session_id: str,
        user_message: str,
        assistant_message: str,
        intermediate_steps: Optional[List[tuple]] = None
    ) -> None:
        """
        Loads current raw history, appends the new turn (including tool calls), and saves it.
        """
        raw_history = await self.store.load(session_id)
        raw_history.append(HumanMessage(content=user_message))
        
        if intermediate_steps:
            for action, observation in intermediate_steps:
                # 1. Append the AIMessage that initiated the tool call
                if hasattr(action, "message_log") and action.message_log:
                    raw_history.extend(action.message_log)
                else:
                    # Fallback in case message_log is not populated
                    tool_call_id = getattr(action, "tool_call_id", None) or f"call_{uuid.uuid4().hex[:8]}"
                    tool_input = action.tool_input
                    if isinstance(tool_input, str):
                        try:
                            import json
                            tool_input = json.loads(tool_input)
                        except Exception:
                            tool_input = {"query": tool_input}
                    elif not isinstance(tool_input, dict):
                        tool_input = {}
                    
                    tool_call = {
                        "name": action.tool,
                        "args": tool_input,
                        "id": tool_call_id
                    }
                    raw_history.append(AIMessage(content="", tool_calls=[tool_call]))
                
                # 2. Append the ToolMessage containing the tool output
                tool_call_id = getattr(action, "tool_call_id", None)
                if not tool_call_id and hasattr(action, "message_log") and action.message_log:
                    ai_msg = action.message_log[0]
                    if hasattr(ai_msg, "tool_calls") and ai_msg.tool_calls:
                        tool_call_id = ai_msg.tool_calls[0].get("id")
                
                if not tool_call_id:
                    tool_call_id = f"call_{uuid.uuid4().hex[:8]}"
                    
                raw_history.append(ToolMessage(
                    content=str(observation),
                    name=action.tool,
                    tool_call_id=tool_call_id
                ))
                
        raw_history.append(AIMessage(content=assistant_message))
        await self.store.save(session_id, raw_history)

    async def clear(self, session_id: str) -> None:
        """
        Clears the conversation cache and database records.
        """
        await self.store.clear(session_id)
