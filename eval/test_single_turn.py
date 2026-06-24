"""
Single-turn end-to-end evaluation.

Agent được gọi trực tiếp qua LangGraph; deepeval đánh giá test case được tạo
từ output và retrieval_context thu thập từ ToolMessage trong luồng agent.

Metrics (tối đa 5, theo chiến lược Agent + RAG + Graph):
  --- PROD (referenceless — chạy cả dev lẫn production) ---
  1. AnswerRelevancyMetric   — output có trả lời đúng câu hỏi không
  2. FaithfulnessMetric      — output có trung thực với context không (khi có context)
  3. GraphReasoningGEval     — suy luận từ graph có đúng entity/relationship không
  4. DomainFaithfulnessGEval — không tự bịa số liệu, trả lời bằng tiếng Việt

  --- DEV ONLY (cần ground truth — chỉ chạy khi có expected_tools) ---
  5. ToolCorrectnessMetric   — tool được gọi có đúng không

Prerequisites:
    uv run python eval/generate_datasets.py

Run:
    uv run pytest eval/test_single_turn.py -v
"""

import os
from pathlib import Path

import pytest
from dotenv import load_dotenv

from deepeval import assert_test
from deepeval.dataset import EvaluationDataset, Golden
from deepeval.metrics import (
    AnswerRelevancyMetric,
    FaithfulnessMetric,
    GEval,
    ToolCorrectnessMetric,
)
from deepeval.test_case import LLMTestCase, SingleTurnParams

from eval.judge import GeminiJudge

load_dotenv()

DATASET_PATH = Path(__file__).parent / "datasets" / "single_turn_goldens.json"

_judge = GeminiJudge()

# ---------------------------------------------------------------------------
# Metrics — PROD (referenceless, luôn chạy)
# ---------------------------------------------------------------------------

_answer_relevancy = AnswerRelevancyMetric(threshold=0.5, model=_judge, async_mode=False)

_faithfulness = FaithfulnessMetric(threshold=0.5, model=_judge, async_mode=False)

_graph_reasoning = GEval(
    name="GraphReasoningAccuracy",
    model=_judge,
    async_mode=False,
    evaluation_steps=[
        "Kiểm tra các entity (tên, mã, ID) được đề cập trong câu trả lời có xuất hiện "
        "trong retrieval_context không — không được tự bịa entity.",
        "Xác nhận các mối quan hệ (relationship) giữa các entity trong câu trả lời "
        "có được hỗ trợ bởi dữ liệu trong retrieval_context không.",
        "Kiểm tra kết luận cuối cùng có logic nhất quán với chuỗi quan hệ "
        "được tìm thấy trong graph không (ví dụ: A → B → C phải có đủ bằng chứng từng bước).",
        "Nếu retrieval_context rỗng, câu trả lời phải thừa nhận không tìm thấy dữ liệu "
        "thay vì đưa ra kết luận.",
    ],
    evaluation_params=[
        SingleTurnParams.INPUT,
        SingleTurnParams.ACTUAL_OUTPUT,
        SingleTurnParams.RETRIEVAL_CONTEXT,
    ],
    threshold=0.65,
)

_domain_faithfulness = GEval(
    name="DomainFaithfulness",
    model=_judge,
    async_mode=False,
    evaluation_steps=[
        "Câu trả lời phải hoàn toàn bằng tiếng Việt.",
        "Nếu retrieval_context rỗng, câu trả lời phải thừa nhận không có dữ liệu, "
        "không được tự suy diễn hay bịa thông tin.",
        "Nếu có số liệu (VNĐ, %, ngày, số lượng), xác nhận số liệu đó xuất hiện "
        "trong retrieval_context — không được tự bịa.",
        "Trợ lý nên trích dẫn nguồn dữ liệu cụ thể khi có thể.",
    ],
    evaluation_params=[
        SingleTurnParams.INPUT,
        SingleTurnParams.ACTUAL_OUTPUT,
        SingleTurnParams.RETRIEVAL_CONTEXT,
    ],
    threshold=0.7,
)

# ---------------------------------------------------------------------------
# Metrics — DEV ONLY
# ---------------------------------------------------------------------------

_tool_correctness = ToolCorrectnessMetric(threshold=0.5, model=_judge)

_PROD_METRICS = [_answer_relevancy, _graph_reasoning, _domain_faithfulness]

# ---------------------------------------------------------------------------
# Dataset — loaded once at module import
# ---------------------------------------------------------------------------


def _load_dataset() -> EvaluationDataset:
    if not DATASET_PATH.exists():
        return EvaluationDataset()
    dataset = EvaluationDataset()
    dataset.add_goldens_from_json_file(
        file_path=str(DATASET_PATH),
        input_key_name="input",
        expected_output_key_name="expected_output",
    )
    return dataset


_dataset = _load_dataset()

# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "golden",
    _dataset.goldens,
    ids=[f"ST{i + 1:03d}" for i in range(len(_dataset.goldens))],
)
def test_single_turn(golden: Golden):
    if not os.getenv("GOOGLE_API_KEY"):
        pytest.skip("GOOGLE_API_KEY not set")
    if not _dataset.goldens:
        pytest.skip("Dataset empty — run: uv run python eval/generate_datasets.py")

    from app.agent import create_conversational_agent

    agent = create_conversational_agent()

    result = agent.invoke(
        {"messages": [{"role": "user", "content": golden.input}]},
    )
    messages = result.get("messages", [])

    actual_output = ""
    retrieval_context = []

    for msg in messages:
        mtype = type(msg).__name__
        if mtype == "ToolMessage":
            content = getattr(msg, "content", "")
            if isinstance(content, list):
                content = " ".join(str(p) for p in content)
            retrieval_context.append(str(content))
        elif mtype == "AIMessage":
            content = getattr(msg, "content", "")
            if isinstance(content, list):
                content = " ".join(
                    b.get("text", "") if isinstance(b, dict) else str(b)
                    for b in content
                )
            if content:
                actual_output = content

    test_case = LLMTestCase(
        input=golden.input,
        actual_output=actual_output,
        expected_output=golden.expected_output,
        retrieval_context=retrieval_context if retrieval_context else [],
    )

    metrics = list(_PROD_METRICS)
    if retrieval_context:
        metrics.append(_faithfulness)
    if getattr(golden, "expected_tools", None) is not None:
        metrics.append(_tool_correctness)

    assert_test(test_case=test_case, metrics=metrics, run_async=False)
