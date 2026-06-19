"""
Generate synthetic golden datasets.

Single-turn  — DeepEval Synthesizer from wiki doc contexts.
Multi-turn   — ConversationSimulator against the REAL agent; saves actual
               conversations so test_multi_turn.py can evaluate without
               re-simulating (faster test runs, real agent behavior captured).

Run once before eval tests:
    uv run python eval/generate_datasets.py

Outputs:
    eval/datasets/single_turn_goldens.json   — 20 single-turn Q&A goldens
    eval/datasets/multi_turn_goldens.json    — 20 simulated conversations
"""

import json
import os
import sys
from pathlib import Path
from typing import List

from dotenv import load_dotenv

load_dotenv()

# Ensure project root is on sys.path when script is run directly from eval/
_root = Path(__file__).parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

ROOT = Path(__file__).parent.parent
DATASETS_DIR = Path(__file__).parent / "datasets"

# ---------------------------------------------------------------------------
# Wiki docs for single-turn synthesis
# ---------------------------------------------------------------------------

WIKI_DOCS = [
    # services — sản phẩm cốt lõi, có số liệu cụ thể (accuracy, MRR, latency, budget)
    str(ROOT / "wiki/services/visionchat.md"),        # 92.3% accuracy, MRR 0.53B, 10 clients
    str(ROOT / "wiki/services/datapulse.md"),          # 32% progress, budget 1800M, spent 620M
    str(ROOT / "wiki/services/auth-service.md"),       # Go/Gin, port 8002, JWT/OAuth, 2 replicas
    # pipelines — quy trình có SLA/rule cụ thể, dễ test exact recall
    str(ROOT / "wiki/pipelines/incident-handling-process.md"),  # P1→5min, postmortem 48h
    str(ROOT / "wiki/pipelines/release-process.md"),            # 2 approvals, PR inactive 3 days
    # decisions — fact-dense: date, duration, specific numbers
    str(ROOT / "wiki/decisions/hotfix-v121.md"),       # 02/09/2024, 2h31m resolution, 420 sessions
    str(ROOT / "wiki/decisions/q32024-okr-review.md"), # 7.2B/8B VNĐ, 4/5 contracts, OKR %
    # person/department — headcount, salary range, policy table
    str(ROOT / "wiki/person/human-resources-department.md"),  # leave days by level table
    str(ROOT / "wiki/person/engineering-department.md"),      # 6 employees, avg 25.2M VNĐ
    # concepts — clear permitted/prohibited rules, easy true/false assertion
    str(ROOT / "wiki/concepts/ai-tools-usage-guidelines.md"),
]
WIKI_DOCS = [p for p in WIKI_DOCS if Path(p).exists()]

# ---------------------------------------------------------------------------
# Predefined multi-turn scenarios — diverse coverage across all agent tools
# ---------------------------------------------------------------------------

MT_SCENARIOS = [
    # wiki_search scenarios
    {
        "scenario": "Nhân viên mới muốn tìm hiểu về auth-service: ngôn ngữ lập trình, framework, port, số replicas, và cơ chế xác thực.",
        "expected_outcome": "Nhân viên nắm được đầy đủ thông tin kỹ thuật của auth-service bao gồm Go/Gin, port 8002, 2 replicas và JWT/OAuth.",
        "user_description": "Nhân viên kỹ thuật mới tại TechVision AI đang tìm hiểu kiến trúc hệ thống.",
    },
    {
        "scenario": "Developer hỏi về API Gateway: công nghệ sử dụng, các chức năng chính, và cách nó kết nối với các service khác.",
        "expected_outcome": "Developer hiểu rõ API Gateway dùng Kong/Nginx, xử lý rate limiting, auth, routing đến các internal services.",
        "user_description": "Senior developer đang thiết kế tích hợp client mới.",
    },
    {
        "scenario": "Product manager muốn hiểu quy trình CI/CD của TechVision: các bước từ commit đến production, công cụ sử dụng.",
        "expected_outcome": "PM nắm được pipeline CI/CD với GitHub Actions, Docker, Kubernetes và quy trình review/deploy.",
        "user_description": "Product manager cần nắm quy trình kỹ thuật để lên kế hoạch release.",
    },
    {
        "scenario": "Nhân viên hỏi về chính sách nghỉ phép: số ngày phép năm, quy trình xin phép, và chính sách WFH.",
        "expected_outcome": "Nhân viên biết rõ chính sách nghỉ phép và WFH của công ty.",
        "user_description": "Nhân viên mới cần tìm hiểu chính sách HR của công ty.",
    },
    # graph_traverse scenarios
    {
        "scenario": "Tech lead muốn khám phá mối quan hệ giữa bot-engine và các service liên quan: NLU service, RAG engine, response generator.",
        "expected_outcome": "Tech lead hiểu rõ luồng xử lý của bot-engine và các dependency service của nó.",
        "user_description": "Tech lead đang thiết kế kiến trúc cho tính năng mới.",
    },
    {
        "scenario": "Architect hỏi về knowledge-base-indexer: pipeline xử lý, các component liên quan, và luồng dữ liệu đến vector database.",
        "expected_outcome": "Architect nắm được toàn bộ knowledge base indexing pipeline và dependency graph.",
        "user_description": "Solution architect đang đánh giá khả năng mở rộng hệ thống.",
    },
    # mongodb_query scenarios
    {
        "scenario": "HR muốn biết danh sách nhân viên đi muộn trong tháng 10/2024 và số lần đi muộn của từng người.",
        "expected_outcome": "HR có danh sách đầy đủ nhân viên đi muộn với thông tin chi tiết từ attendance_october_2024.",
        "user_description": "Nhân viên HR đang làm báo cáo chấm công tháng.",
    },
    {
        "scenario": "Finance muốn xem tổng chi phí infrastructure tháng 9/2024 theo từng provider và category dịch vụ.",
        "expected_outcome": "Finance có breakdown chi phí cloud infrastructure theo AWS/GCP, chia theo Compute/Database/Network v.v.",
        "user_description": "Finance analyst đang lập báo cáo chi phí vận hành.",
    },
    {
        "scenario": "COO hỏi về tình hình revenue tháng 6-9/2024: tổng MRR, số khách hàng mới, churn rate và gross margin.",
        "expected_outcome": "COO có cái nhìn tổng quan về business metrics 4 tháng gần nhất từ revenue_2024.",
        "user_description": "COO cần dữ liệu cho báo cáo board meeting.",
    },
    {
        "scenario": "Trưởng phòng kỹ thuật muốn xem danh sách bug priority Critical đang còn mở và assignee của từng bug.",
        "expected_outcome": "Trưởng phòng có danh sách bug Critical chưa resolved với assignee để theo dõi.",
        "user_description": "Engineering manager đang review tình trạng quality của sprint hiện tại.",
    },
    # mixed tool scenarios
    {
        "scenario": "New hire hỏi: NLU service là gì, nó liên kết với những service nào, và hiện có bao nhiêu sprint ticket liên quan đến NLU.",
        "expected_outcome": "New hire hiểu NLU service (wiki), các service liên quan (graph), và tình trạng sprint tickets (mongodb).",
        "user_description": "Kỹ sư mới vừa join team AI/ML muốn nắm codebase.",
    },
    {
        "scenario": "Manager muốn tuyển thêm Python developer: hiện pipeline tuyển dụng có bao nhiêu ứng viên đang active, vị trí nào đang tuyển nhiều nhất.",
        "expected_outcome": "Manager nắm được số ứng viên active, top positions đang tuyển từ recruitment_pipeline.",
        "user_description": "Engineering manager đang lên kế hoạch headcount Q4.",
    },
    # additional wiki_search scenarios
    {
        "scenario": "Product manager hỏi về DataPulse: tiến độ hiện tại bao nhiêu phần trăm, ngân sách tổng và đã chi bao nhiêu, deadline dự kiến.",
        "expected_outcome": "PM biết DataPulse đạt 32% progress, budget 1800M VNĐ, đã chi 620M, và deadline kế hoạch.",
        "user_description": "Product manager cần cập nhật tình trạng dự án cho stakeholder.",
    },
    {
        "scenario": "Business analyst hỏi về VisionChat: accuracy hiện tại, MRR, số khách hàng đang dùng, và các tính năng nổi bật.",
        "expected_outcome": "Analyst nắm VisionChat đạt 92.3% accuracy, MRR 0.53B, 10 clients và các tính năng chính.",
        "user_description": "Business analyst chuẩn bị tài liệu pitching cho khách hàng tiềm năng.",
    },
    {
        "scenario": "Scrum master hỏi chi tiết về hotfix v1.2.1: thời điểm xảy ra sự cố, thời gian khắc phục, số phiên bị ảnh hưởng, và nguyên nhân gốc rễ.",
        "expected_outcome": "Scrum master biết hotfix v1.2.1 xảy ra 02/09/2024, giải quyết trong 2h31m, ảnh hưởng 420 sessions và root cause.",
        "user_description": "Scrum master cần viết báo cáo retrospective về incident.",
    },
    {
        "scenario": "Giám đốc hỏi về kết quả OKR Q3/2024: doanh thu thực tế so với mục tiêu, số hợp đồng ký được, và OKR nào đạt/không đạt.",
        "expected_outcome": "Giám đốc nắm Q3 2024 đạt 7.2B/8B VNĐ, 4/5 hợp đồng, và chi tiết từng OKR.",
        "user_description": "CEO đang chuẩn bị board presentation Q3.",
    },
    # additional mongodb_query scenarios
    {
        "scenario": "Scrum master muốn xem sprint velocity 3 sprint gần nhất: story points committed vs completed, và sprint nào có completion rate thấp nhất.",
        "expected_outcome": "Scrum master có dữ liệu velocity trend và sprint có completion rate thấp nhất để cải thiện.",
        "user_description": "Scrum master đang chuẩn bị retrospective và capacity planning.",
    },
    {
        "scenario": "Customer success muốn xem điểm NPS và CSAT của các khách hàng Enterprise trong Q3/2024, sắp xếp theo score thấp nhất.",
        "expected_outcome": "CS team có danh sách khách hàng Enterprise với NPS/CSAT thấp để ưu tiên follow-up.",
        "user_description": "Customer success manager đang lên kế hoạch retention cho khách hàng Enterprise.",
    },
    # additional graph_traverse scenarios
    {
        "scenario": "Developer muốn biết VisionChat phụ thuộc vào những service nào, service nào phụ thuộc ngược lại vào VisionChat.",
        "expected_outcome": "Developer hiểu full dependency graph của VisionChat: upstream dependencies và downstream consumers.",
        "user_description": "Developer cần assess impact trước khi deploy breaking change cho VisionChat.",
    },
    # additional mixed tool scenarios
    {
        "scenario": "DevOps muốn hiểu quy trình xử lý incident P1: các bước theo pipeline, SLA cụ thể, và hiện đang có bao nhiêu incident P1 open trong tháng này.",
        "expected_outcome": "DevOps nắm quy trình P1 (wiki/pipeline), SLA 5 phút, và số lượng P1 đang open (mongodb).",
        "user_description": "DevOps engineer vừa được phân công on-call duty.",
    },
]


# ---------------------------------------------------------------------------
# Shared judge / embedder model
# ---------------------------------------------------------------------------


def build_judge():
    from deepeval.models.base_model import DeepEvalBaseLLM
    from langchain_google_genai import ChatGoogleGenerativeAI

    class GeminiJudge(DeepEvalBaseLLM):
        def __init__(self):
            self._model = None
            super().__init__()

        def load_model(self):
            if self._model is None:
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

    return GeminiJudge()


# ---------------------------------------------------------------------------
# Single-turn generation (Synthesizer from wiki doc contexts)
# ---------------------------------------------------------------------------


def _chunk_docs(chunk_size: int = 1200) -> tuple[list[list[str]], list[str]]:
    contexts, sources = [], []
    for path in WIKI_DOCS:
        text = Path(path).read_text(encoding="utf-8")
        if text.startswith("---"):
            end = text.find("---", 3)
            if end != -1:
                text = text[end + 3 :].strip()
        chunks = [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)]
        contexts.append(chunks)
        sources.append(path)
    return contexts, sources


def generate_single_turn(synthesizer, n: int = 5) -> list[dict]:
    """Synthesize exactly n single-turn Q&A goldens from wiki doc contexts."""
    contexts, sources = _chunk_docs()
    per_ctx = max(2, -(-n // len(contexts)))
    print(
        f"Generating ~{per_ctx} goldens per context from {len(contexts)} docs ..."
    )

    goldens = synthesizer.generate_goldens_from_contexts(
        contexts=contexts,
        source_files=sources,
        include_expected_output=True,
        max_goldens_per_context=per_ctx,
    )
    goldens = goldens  # trim to exactly n
    print(f"Generated {len(goldens)} single-turn goldens")

    return [
        {
            "id": f"ST{i:03d}",
            "input": g.input,
            "expected_output": g.expected_output,
            "context": g.context or [],
            "additional_metadata": g.additional_metadata or {},
        }
        for i, g in enumerate(goldens, 1)
    ]


# ---------------------------------------------------------------------------
# Multi-turn generation (ConversationSimulator against the real agent)
# ---------------------------------------------------------------------------


def _make_agent_callback():
    """Wrap the real LangGraph agent as a ConversationSimulator model_callback."""
    from app.agent import create_conversational_agent
    from app.tools import start_retrieval_capture, pop_retrieval_capture
    from deepeval.test_case import Turn

    agent = create_conversational_agent()

    def model_callback(input: str, turns: List[Turn]) -> Turn:
        # Pass full turn history as messages; agent has no checkpointer.
        messages = [{"role": t.role, "content": t.content} for t in turns]
        start_retrieval_capture()
        result = agent.invoke({"messages": messages})
        retrieval_ctx = pop_retrieval_capture()
        for msg in reversed(result.get("messages", [])):
            if type(msg).__name__ == "AIMessage":
                content = getattr(msg, "content", "")
                if isinstance(content, list):
                    content = " ".join(
                        p.get("text", "") if isinstance(p, dict) else str(p)
                        for p in content
                    )
                if content:
                    return Turn(
                        role="assistant",
                        content=content,
                        retrieval_context=retrieval_ctx or None,
                    )
        return Turn(role="assistant", content="", retrieval_context=retrieval_ctx or None)

    return model_callback


def generate_multi_turn(
    judge, n: int = 5, max_turns_per_scenario: int = 5
) -> list[dict]:
    """Simulate multi-turn conversations using ConversationSimulator + real agent.

    Saves the resulting ConversationalTestCase turns as golden data so that
    test_multi_turn.py can evaluate without re-simulating.
    """
    from deepeval.dataset import ConversationalGolden
    from deepeval.simulator import ConversationSimulator

    scenarios = MT_SCENARIOS[:n]
    if len(scenarios) < n:
        print(
            f"Warning: only {len(MT_SCENARIOS)} scenarios defined, generating {len(scenarios)}."
        )

    goldens = [
        ConversationalGolden(
            scenario=s["scenario"],
            expected_outcome=s["expected_outcome"],
            user_description=s["user_description"],
        )
        for s in scenarios
    ]

    print(
        f"Simulating {len(goldens)} multi-turn conversations (max {max_turns_per_scenario} turns each) ..."
    )

    simulator = ConversationSimulator(
        model_callback=_make_agent_callback(),
        simulator_model=judge,
        async_mode=False,
    )
    test_cases = simulator.simulate(
        conversational_goldens=goldens,
        max_user_simulations=max_turns_per_scenario,
    )
    print(f"Simulated {len(test_cases)} conversations")

    records = []
    for i, (tc, spec) in enumerate(zip(test_cases, scenarios), 1):
        turns = []
        for t in tc.turns or []:
            turns.append(
                {
                    "role": t.role,
                    "content": t.content,
                    "retrieval_context": t.retrieval_context or [],
                }
            )
        records.append(
            {
                "id": f"MT{i:03d}",
                "scenario": spec["scenario"],
                "expected_outcome": spec["expected_outcome"],
                "user_description": spec["user_description"],
                "turns": turns,
            }
        )
    return records


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Generate eval golden datasets.")
    parser.add_argument(
        "--single",
        type=int,
        default=20,
        help="Number of single-turn goldens (default: 20)",
    )
    parser.add_argument(
        "--multi",
        type=int,
        default=20,
        help="Number of multi-turn conversations (default: 20)",
    )
    args = parser.parse_args()

    if not os.getenv("GOOGLE_API_KEY"):
        print("ERROR: GOOGLE_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    DATASETS_DIR.mkdir(parents=True, exist_ok=True)

    from deepeval.synthesizer import Synthesizer
    from deepeval.synthesizer.config import StylingConfig

    judge = build_judge()

    # --- single-turn ---
    synthesizer = Synthesizer(
        model=judge,
        async_mode=False,
        styling_config=StylingConfig(
            scenario=(
                "Nhân viên hoặc developer tại TechVision AI đang hỏi trợ lý AI nội bộ "
                "về hệ thống, kiến trúc kỹ thuật, chính sách HR, hoặc quy trình công ty."
            ),
            task=(
                "Trả lời các câu hỏi thực tế cụ thể về dịch vụ, hạ tầng, chính sách "
                "và pipeline của TechVision AI."
            ),
            input_format=(
                "Một câu hỏi ngắn gọn bằng tiếng Việt về một sự kiện cụ thể, "
                "chi tiết kỹ thuật, hoặc quy định tại TechVision AI."
            ),
            expected_output_format=(
                "Câu trả lời chính xác, thực tế bằng tiếng Việt, có trích dẫn nguồn tài liệu, "
                "hệ thống, hoặc mục chính sách liên quan."
            ),
        ),
    )
    single_records = generate_single_turn(synthesizer, n=args.single)
    st_path = DATASETS_DIR / "single_turn_goldens.json"
    st_path.write_text(json.dumps(single_records, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved {len(single_records)} single-turn goldens → {st_path}")

    # --- multi-turn ---
    multi_records = generate_multi_turn(judge, n=args.multi)
    mt_path = DATASETS_DIR / "multi_turn_goldens.json"
    mt_path.write_text(
        json.dumps(multi_records, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Saved {len(multi_records)} multi-turn goldens → {mt_path}")


if __name__ == "__main__":
    main()
