"""
Multi-turn end-to-end evaluation.

Tải các cuộc hội thoại đã được mô phỏng sẵn từ eval/datasets/multi_turn_goldens.json
(được tạo bởi ConversationSimulator trong generate_datasets.py) và đánh giá trực tiếp.

Metrics (tối đa 5, theo chiến lược Agent + RAG + Graph chatbot):
  --- PROD (referenceless) ---
  1. ConversationCompletenessMetric — hội thoại có đáp ứng đủ nhu cầu không
  2. KnowledgeRetentionMetric       — agent có nhớ ngữ cảnh từ các lượt trước không
  3. TurnFaithfulnessMetric         — mỗi lượt có trung thực với context không (RAG)

  --- PROD + Custom ---
  4. ConversationalGEval            — tiếng Việt, graph reasoning, nguồn trích dẫn

  --- DEV (referenceless nhưng chỉ hữu ích khi câu hỏi đủ đa dạng) ---
  5. TurnRelevancyMetric            — mỗi lượt có liên quan đến input không

Lý do bỏ TurnRelevancy khỏi PROD: với chatbot domain-specific,
TurnFaithfulness + ConvCompleteness đã bao phủ đủ chất lượng hội thoại.
Bật lại bằng cách thêm vào _METRICS nếu cần debug.

Prerequisites:
    uv run python eval/generate_datasets.py

Run:
    uv run pytest eval/test_multi_turn.py -v
"""

import json
import os
from pathlib import Path
from typing import List

import pytest
from dotenv import load_dotenv

from deepeval import assert_test
from deepeval.metrics import (
    ConversationCompletenessMetric,
    ConversationalGEval,
    KnowledgeRetentionMetric,
    TurnFaithfulnessMetric,
    TurnRelevancyMetric,
)
from deepeval.models.base_model import DeepEvalBaseLLM
from deepeval.test_case import ConversationalTestCase, Turn
from deepeval.test_case.conversational_test_case import MultiTurnParams

load_dotenv()

DATASET_PATH = Path(__file__).parent / "datasets" / "multi_turn_goldens.json"


# ---------------------------------------------------------------------------
# Judge model
# ---------------------------------------------------------------------------


class GeminiJudge(DeepEvalBaseLLM):
    def __init__(self):
        self._model = None
        super().__init__()

    def load_model(self):
        if self._model is None:
            from langchain_google_genai import ChatGoogleGenerativeAI

            self._model = ChatGoogleGenerativeAI(
                model="gemini-2.5-flash",
                temperature=0,
                google_api_key=os.getenv("GOOGLE_API_KEY"),
            )
        return self._model

    def generate(self, prompt: str, schema=None):
        m = self.load_model()
        if schema is not None:
            return m.with_structured_output(schema).invoke(prompt)
        return m.invoke(prompt).content

    async def a_generate(self, prompt: str, schema=None):
        import asyncio

        return await asyncio.to_thread(self.generate, prompt, schema)

    def get_model_name(self) -> str:
        return "gemini-2.5-flash"


_judge = GeminiJudge()

# ---------------------------------------------------------------------------
# Metrics — PROD
# ---------------------------------------------------------------------------

_completeness = ConversationCompletenessMetric(
    threshold=0.5,
    model=_judge,
    async_mode=False,
)

_knowledge_retention = KnowledgeRetentionMetric(
    threshold=0.5,
    model=_judge,
    async_mode=False,
)

_turn_faithfulness = TurnFaithfulnessMetric(
    threshold=0.5,
    model=_judge,
    async_mode=False,
)

# Custom metric kết hợp: domain (tiếng Việt, số liệu) + graph reasoning + context retention
# Đây là metric quan trọng nhất cho hệ thống Graph RAG chatbot
_conv_geval = ConversationalGEval(
    name="ConvGraphDomainFaithfulness",
    model=_judge,
    async_mode=False,
    evaluation_params=[
        MultiTurnParams.CONTENT,
        MultiTurnParams.RETRIEVAL_CONTEXT,
    ],
    evaluation_steps=[
        # Domain & ngôn ngữ
        "Xác nhận trợ lý LUÔN trả lời bằng tiếng Việt trong toàn bộ cuộc hội thoại, "
        "bất kể người dùng hỏi bằng ngôn ngữ nào (tiếng Anh, tiếng Việt hay ngôn ngữ khác). "
        "Đây là yêu cầu bắt buộc — nếu trợ lý trả lời bằng tiếng Việt là ĐÚNG, không penalize.",
        # Context retention (multi-turn đặc thù)
        "Kiểm tra trợ lý có ghi nhớ và sử dụng lại thông tin từ các lượt trước không "
        "(ví dụ: nếu user đề cập entity A ở lượt 1, lượt 3 phải nhớ A mà không cần nhắc lại).",
        # Graph reasoning — chỉ áp dụng khi có retrieval_context
        "Với mỗi entity (tên, mã, ID) được đề cập trong câu trả lời, nếu retrieval_context "
        "của lượt đó KHÔNG rỗng thì xác nhận entity có xuất hiện trong đó. "
        "Nếu retrieval_context rỗng, BỎ QUA bước này — không penalize.",
        "Kiểm tra các mối quan hệ (relationship) được nêu ra có được graph context hỗ trợ không "
        "— chỉ penalize nếu retrieval_context không rỗng và relationship bị bịa. "
        "Nếu retrieval_context rỗng, BỎ QUA bước này.",
        # Số liệu & nguồn — chỉ áp dụng khi có retrieval_context
        "Nếu có số liệu (VNĐ, %, ngày, số lượng) VÀ retrieval_context không rỗng, "
        "xác nhận số liệu xuất hiện trong retrieval_context — không được tự bịa. "
        "Nếu retrieval_context rỗng, bỏ qua kiểm tra số liệu.",
        # Completeness
        "Câu trả lời cuối phải đầy đủ, không bỏ lỡ câu hỏi nào của người dùng trong lượt đó.",
        "Trợ lý nên trích dẫn nguồn dữ liệu cụ thể (tên tài liệu, ID node graph) khi trả lời.",
    ],
    threshold=0.65,
)

# ---------------------------------------------------------------------------
# Metrics — DEV (hữu ích khi debug nhưng không bắt buộc cho prod)
# ---------------------------------------------------------------------------

_turn_relevancy = TurnRelevancyMetric(
    threshold=0.5,
    model=_judge,
    async_mode=False,
)

# ---------------------------------------------------------------------------
# Metrics được áp dụng — tối đa 5
# Bật _turn_relevancy bằng cách thêm vào list nếu cần debug turn-level relevancy
# ---------------------------------------------------------------------------

_METRICS = [
    _completeness,        # Hội thoại đáp ứng đủ nhu cầu
    _knowledge_retention, # Nhớ ngữ cảnh xuyên suốt
    # _turn_faithfulness: PydanticOutputParser crash khi Gemini trả output ngoài schema
    #   (idk verdict với format không chuẩn). ConvGraphDomainFaithfulness cover tương đương.
    _conv_geval,          # Graph reasoning + domain + tiếng Việt
    # _turn_relevancy,    # Bật khi cần debug turn-level relevancy
]

# ---------------------------------------------------------------------------
# Load pre-simulated conversations from dataset
# ---------------------------------------------------------------------------


def _load_test_cases() -> List[ConversationalTestCase]:
    if not DATASET_PATH.exists():
        return []
    records = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    test_cases = []
    for r in records:
        turns = [
            Turn(
                role=t["role"],
                content=t["content"],
                retrieval_context=t.get("retrieval_context") or None,
            )
            for t in r.get("turns", [])
        ]
        if not turns:
            continue
        test_cases.append(
            ConversationalTestCase(
                turns=turns,
                expected_outcome=r.get("expected_outcome"),
            )
        )
    return test_cases


_test_cases = _load_test_cases()

_skip_reason: str | None = (
    "Dataset empty — run: uv run python eval/generate_datasets.py"
    if not _test_cases
    else "GOOGLE_API_KEY not set"
    if not os.getenv("GOOGLE_API_KEY")
    else None
)

# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "test_case",
    _test_cases or [None],
    ids=[f"MT{i + 1:03d}" for i in range(len(_test_cases))]
    if _test_cases
    else ["skip"],
)
def test_multi_turn(test_case: ConversationalTestCase):
    if _skip_reason or test_case is None:
        pytest.skip(_skip_reason or "no test cases")

    assert_test(test_case=test_case, metrics=_METRICS, run_async=False)