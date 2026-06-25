import json

from eval.export_feedback_regressions import main
from eval.production_feedback import (
    candidate_regressions_from_feedback,
    read_documents_file,
    write_candidates_jsonl,
)


def test_candidate_regressions_use_negative_feedback_trace_and_redact_sensitive_data(
    tmp_path,
):
    feedbacks = [
        {
            "id": "fb1",
            "forId": "assistant-1",
            "threadId": "thread-1",
            "value": -1,
            "comment": "Sai payroll của alice@example.com, gọi lại 0901234567",
        },
        {
            "id": "fb2",
            "forId": "assistant-2",
            "threadId": "thread-1",
            "value": 1,
            "comment": "",
        },
    ]
    steps = [
        {
            "id": "user-1",
            "threadId": "thread-1",
            "type": "user_message",
            "output": "Payroll của alice@example.com tháng 9 là bao nhiêu?",
        },
        {
            "id": "assistant-1",
            "threadId": "thread-1",
            "type": "assistant_message",
            "input": "Payroll của alice@example.com tháng 9 là bao nhiêu?",
            "output": "Alice nhận 10m. Mongo _id 6a2faeb4627525170a7016f4",
        },
    ]
    traces = [
        {
            "thread_id": "thread-1",
            "step_id": "assistant-1",
            "actual": {
                "tool_calls": [
                    {
                        "name": "mongodb_query",
                        "args": {"collection": "payroll_september_2024"},
                    }
                ],
                "tool_outputs": [
                    {"name": "mongodb_query", "output": "alice@example.com 10000000"}
                ],
            },
        }
    ]

    candidates = candidate_regressions_from_feedback(feedbacks, steps, traces)

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate["id"].startswith("PROD-")
    assert candidate["question"] == "Payroll của [REDACTED_EMAIL] tháng 9 là bao nhiêu?"
    assert candidate["actual_answer"] == (
        "Alice nhận 10m. Mongo _id [REDACTED_OBJECT_ID]"
    )
    assert candidate["feedback"]["comment"] == (
        "Sai payroll của [REDACTED_EMAIL], gọi lại [REDACTED_PHONE]"
    )
    assert candidate["actual"]["tool_calls"][0]["name"] == "mongodb_query"
    assert candidate["expected"]["needs_human_review"] is True


def test_candidate_regressions_include_commented_positive_feedback():
    candidates = candidate_regressions_from_feedback(
        feedbacks=[
            {
                "id": "fb1",
                "forId": "assistant-1",
                "threadId": "thread-1",
                "value": 1,
                "comment": "Thiếu nguồn wiki",
            }
        ],
        steps=[
            {
                "id": "assistant-1",
                "threadId": "thread-1",
                "input": "VisionChat là gì?",
                "output": "VisionChat là sản phẩm AI.",
            }
        ],
        traces=[],
    )

    assert candidates[0]["feedback"]["value"] == 1
    assert candidates[0]["question"] == "VisionChat là gì?"


def test_write_candidates_jsonl(tmp_path):
    out = tmp_path / "production_regressions.jsonl"
    write_candidates_jsonl(
        out,
        [{"id": "PROD-1", "question": "Q"}, {"id": "PROD-2", "question": "A"}],
    )

    rows = [json.loads(line) for line in out.read_text().splitlines()]

    assert rows == [{"id": "PROD-1", "question": "Q"}, {"id": "PROD-2", "question": "A"}]


def test_read_documents_file_supports_json_array_and_jsonl(tmp_path):
    json_path = tmp_path / "feedbacks.json"
    jsonl_path = tmp_path / "steps.jsonl"
    json_path.write_text(json.dumps([{"id": "fb1"}]), encoding="utf-8")
    jsonl_path.write_text('{"id": "s1"}\n{"id": "s2"}\n', encoding="utf-8")

    assert read_documents_file(json_path) == [{"id": "fb1"}]
    assert read_documents_file(jsonl_path) == [{"id": "s1"}, {"id": "s2"}]


def test_export_feedback_regressions_cli_writes_candidates_from_files(tmp_path):
    feedbacks_path = tmp_path / "feedbacks.json"
    steps_path = tmp_path / "steps.json"
    out_path = tmp_path / "candidates.jsonl"
    feedbacks_path.write_text(
        json.dumps(
            [
                {
                    "id": "fb1",
                    "forId": "assistant-1",
                    "threadId": "thread-1",
                    "value": -1,
                }
            ]
        ),
        encoding="utf-8",
    )
    steps_path.write_text(
        json.dumps(
            [
                {
                    "id": "assistant-1",
                    "threadId": "thread-1",
                    "input": "Hỏi gì?",
                    "output": "Trả lời sai",
                }
            ]
        ),
        encoding="utf-8",
    )

    exit_code = main(
        [
            "--feedbacks",
            str(feedbacks_path),
            "--steps",
            str(steps_path),
            "--out",
            str(out_path),
        ]
    )

    assert exit_code == 0
    rows = [json.loads(line) for line in out_path.read_text().splitlines()]
    assert rows[0]["question"] == "Hỏi gì?"
