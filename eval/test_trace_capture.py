from eval.trace_capture import (
    called_tool_names,
    final_answer,
    message_content,
    tool_batches,
    tool_outputs,
)


class AIMessage:
    def __init__(self, content="", tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls or []


class ToolMessage:
    def __init__(self, content="", tool_call_id="call_1", name="tool"):
        self.content = content
        self.tool_call_id = tool_call_id
        self.name = name


def test_message_content_flattens_text_parts():
    msg = AIMessage(content=[{"type": "text", "text": "Xin "}, {"text": "chào"}])
    assert message_content(msg) == "Xin chào"


def test_tool_batches_extracts_ai_tool_call_groups():
    messages = [
        AIMessage(
            tool_calls=[
                {
                    "name": "entity_search",
                    "args": {"entity_name": "VisionChat"},
                    "id": "a",
                },
                {
                    "name": "mongodb_query",
                    "args": {"collection": "projects"},
                    "id": "b",
                },
            ]
        ),
        ToolMessage(content="{}"),
        AIMessage(
            tool_calls=[
                {
                    "name": "generate_chart",
                    "args": {"chart_type": "pie"},
                    "id": "c",
                },
            ]
        ),
    ]

    assert tool_batches(messages) == [
        [
            {
                "name": "entity_search",
                "args": {"entity_name": "VisionChat"},
                "id": "a",
            },
            {"name": "mongodb_query", "args": {"collection": "projects"}, "id": "b"},
        ],
        [
            {"name": "generate_chart", "args": {"chart_type": "pie"}, "id": "c"},
        ],
    ]
    assert called_tool_names(messages) == [
        "entity_search",
        "mongodb_query",
        "generate_chart",
    ]


def test_tool_outputs_truncates_large_outputs():
    messages = [ToolMessage(name="mongodb_query", tool_call_id="x", content="a" * 20)]

    assert tool_outputs(messages, max_chars=5) == [
        {
            "name": "mongodb_query",
            "id": "x",
            "output": "aaaaa",
            "truncated": True,
            "char_length": 20,
        }
    ]


def test_final_answer_returns_last_non_empty_ai_text():
    messages = [
        AIMessage(content=""),
        AIMessage(content="Câu trả lời 1"),
        AIMessage(content=[{"text": "Câu trả lời 2"}]),
    ]

    assert final_answer(messages) == "Câu trả lời 2"
