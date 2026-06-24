from __future__ import annotations

from typing import Any


def message_content(msg: Any) -> str:
    content = getattr(msg, "content", "")
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, dict):
                parts.append(str(part.get("text") or part.get("thinking") or ""))
            else:
                parts.append(str(part))
        return "".join(parts)
    return str(content or "")


def tool_batches(messages: list[Any]) -> list[list[dict[str, Any]]]:
    batches: list[list[dict[str, Any]]] = []
    for msg in messages:
        if type(msg).__name__ != "AIMessage":
            continue
        calls: list[dict[str, Any]] = []
        for call in getattr(msg, "tool_calls", []) or []:
            if isinstance(call, dict) and call.get("name"):
                calls.append(
                    {
                        "name": call.get("name"),
                        "args": call.get("args") or {},
                        "id": call.get("id"),
                    }
                )
        if calls:
            batches.append(calls)
    return batches


def called_tool_names(messages: list[Any]) -> list[str]:
    return [call["name"] for batch in tool_batches(messages) for call in batch]


def tool_outputs(messages: list[Any], max_chars: int = 4000) -> list[dict[str, Any]]:
    outputs: list[dict[str, Any]] = []
    for msg in messages:
        if type(msg).__name__ != "ToolMessage":
            continue
        content = message_content(msg)
        outputs.append(
            {
                "name": getattr(msg, "name", "tool"),
                "id": getattr(msg, "tool_call_id", None),
                "output": content[:max_chars],
                "truncated": len(content) > max_chars,
                "char_length": len(content),
            }
        )
    return outputs


def final_answer(messages: list[Any]) -> str:
    for msg in reversed(messages):
        if type(msg).__name__ != "AIMessage":
            continue
        content = message_content(msg)
        if content:
            return content
    return ""
