from typing import List, Optional
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, AnyMessage
from app.memory.session_store import SessionStore


class HistoryManager:
    def __init__(self, store: SessionStore, llm=None):
        self.store = store
        self.llm = llm

    async def get_context(self, session_id: str) -> List[BaseMessage]:
        """
        Returns stored conversation history ready to prepend to the agent's messages input.
        Context compression is handled downstream by Headroom.
        """
        return await self.store.load(session_id) or []

    async def append_turn(
        self,
        session_id: str,
        user_message: str,
        assistant_message: str,
        new_messages: Optional[List[AnyMessage]] = None,
    ) -> None:
        """
        Saves the turn to the store.

        If new_messages is provided (the full message list returned by create_agent),
        it replaces the stored history entirely — it already includes the human turn,
        all tool call/result messages, and the final AI reply.

        Otherwise falls back to appending human + AI messages only.
        """
        if new_messages:
            await self.store.save(session_id, list(new_messages))
            return

        raw_history = await self.store.load(session_id) or []
        raw_history.append(HumanMessage(content=user_message))
        raw_history.append(AIMessage(content=assistant_message))
        await self.store.save(session_id, raw_history)

    async def clear(self, session_id: str) -> None:
        await self.store.clear(session_id)
