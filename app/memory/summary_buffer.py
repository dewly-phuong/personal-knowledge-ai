import os
import logging
from typing import List
from langchain_core.messages import (
    BaseMessage,
    HumanMessage,
    AIMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_google_genai import ChatGoogleGenerativeAI

logger = logging.getLogger(__name__)

SUMMARY_PROMPT_TEMPLATE = """Tóm tắt ngắn gọn cuộc hội thoại dưới đây thành 2-3 câu bằng tiếng Việt.
Giữ lại: các entities quan trọng được hỏi (dịch vụ, pipelines, người), các quyết định hoặc thông tin đã xác nhận, context cần thiết cho câu hỏi tiếp theo.
Bỏ qua: các câu hỏi không liên quan, lời chào xã giao.

Hội thoại:
{conversation}

Tóm tắt:"""

MAX_RECENT_TURNS = 3


def _to_turns(messages: List[BaseMessage]) -> List[dict]:
    """Convert flat message list into a list of {human, ai} pairs, including tool outputs."""
    turns = []
    i = 0
    while i < len(messages):
        if isinstance(messages[i], HumanMessage):
            human_text = messages[i].content
            ai_texts = []
            j = i + 1
            while j < len(messages):
                if isinstance(messages[j], HumanMessage):
                    break
                elif isinstance(messages[j], AIMessage):
                    if messages[j].content:
                        ai_texts.append(messages[j].content)
                    if hasattr(messages[j], "tool_calls") and messages[j].tool_calls:
                        tool_names = ", ".join(
                            tc.get("name", "") for tc in messages[j].tool_calls
                        )
                        ai_texts.append(f"[Calls tools: {tool_names}]")
                elif isinstance(messages[j], ToolMessage):
                    ai_texts.append(
                        f"[Tool {messages[j].name} output: {messages[j].content[:100]}...]"
                    )
                j += 1
            turns.append({"human": human_text, "ai": "\n".join(ai_texts)})
            i = j
        else:
            i += 1
    return turns


async def compress_history(
    messages: List[BaseMessage],
    llm: ChatGoogleGenerativeAI = None,
    max_recent: int = MAX_RECENT_TURNS,
) -> List[BaseMessage]:
    """
    Receives raw messages, returns compressed history:
    [SystemMessage(summary)] + [last 3 turns]
    """
    turns = _to_turns(messages)
    if len(turns) <= max_recent:
        return messages

    old_turns = turns[:-max_recent]

    # Construct conversation text for summarization
    conversation_text = ""
    for t in old_turns:
        conversation_text += f"User: {t['human']}\nAssistant: {t['ai']}\n"

    # Initialize Gemini Flash specifically for fast, cheap summarization
    if llm is None:
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            temperature=0.0,
            google_api_key=os.getenv("GOOGLE_API_KEY"),
        )

    try:
        prompt = SUMMARY_PROMPT_TEMPLATE.format(conversation=conversation_text.strip())
        response = await llm.ainvoke(prompt)
        summary_text = response.content
        if isinstance(summary_text, list):
            summary_text = " ".join(
                [
                    part.get("text", "") if isinstance(part, dict) else str(part)
                    for part in summary_text
                ]
            )

        compressed = [
            SystemMessage(content=f"[Tóm tắt hội thoại trước]: {summary_text}")
        ]

        # Find the starting index of the last max_recent turns by counting HumanMessages
        start_idx = 0
        human_count = 0
        for idx in range(len(messages) - 1, -1, -1):
            if isinstance(messages[idx], HumanMessage):
                human_count += 1
                if human_count == max_recent:
                    start_idx = idx
                    break

        recent_messages = messages[start_idx:]
        compressed.extend(recent_messages)
        return compressed

    except Exception as e:
        logger.error(f"Error compressing history: {e}")
        # If compression fails, fall back to returning raw history to avoid blocking the user
        return messages
