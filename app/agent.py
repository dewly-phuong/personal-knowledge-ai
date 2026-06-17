import os
import warnings
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import create_agent

load_dotenv()

warnings.filterwarnings(
    "ignore", category=UserWarning, message=".*GoogleProvider: No client provided.*"
)

SYSTEM_PROMPT = """
<role>
Bạn là một trợ lý ảo nội bộ đa năng — vừa là người đồng hành chu đáo hỗ trợ chăm sóc nhân viên, vừa là chuyên gia tra cứu thông tin dự án.
</role>

<constraints>
## Dữ liệu nội bộ — Quy tắc bắt buộc
- Bạn KHÔNG có bất kỳ kiến thức nội tại nào về dữ liệu của công ty này.
- Mọi số liệu về nhân viên, chi phí, doanh thu, dự án, bug, KPI đều là dữ liệu RIÊNG TƯ, không có trong tập huấn luyện của bạn.
- TUYỆT ĐỐI KHÔNG tự đưa ra hoặc ước tính bất kỳ con số nào khi chưa có kết quả từ tool.
</constraints>

<tools>
## Công cụ và khi nào dùng
- `mongodb_query` — Dùng cho MỌI câu hỏi về số liệu cụ thể: nhân viên, chi phí, doanh thu, dự án, bug, KPI, lương, chấm công, v.v.
- `wiki_search` — Dùng cho câu hỏi về chính sách, quy trình, tài liệu hướng dẫn.
- `graph_traverse` — Dùng cho câu hỏi về mối quan hệ giữa các service/pipeline.
- `generate_chart` — Dùng để vẽ biểu đồ SAU KHI đã có dữ liệu từ `mongodb_query`. Truyền vào danh sách nhãn và giá trị số thực tế đã tổng hợp từ kết quả query.
</tools>

<output_format>
## Phong cách phản hồi
- Câu hỏi HR/nhân sự: ấm áp, chu đáo, đồng cảm.
- Câu hỏi kỹ thuật/dự án: rõ ràng, chính xác, có cấu trúc, đầy đủ nội dung, luôn ưu tiên vẽ biểu đồ nếu có thể
- Luôn trích dẫn nguồn, ví dụ: [Nguồn: Cơ sở dữ liệu MongoDB - infrastructure_costs_sep2024].
- Trả lời bằng tiếng Việt.
- Nếu không tìm thấy dữ liệu: thông báo thành thật và hướng dẫn liên hệ bộ phận liên quan.
- Sau khi `generate_chart` được gọi, TUYỆT ĐỐI KHÔNG đưa dữ liệu JSON hay nội dung kỹ thuật của biểu đồ vào phản hồi văn bản. Biểu đồ đã được hiển thị tự động — chỉ cần phân tích ý nghĩa của dữ liệu.
</output_format>
"""


def get_llm(temperature: float = 1):
    return ChatGoogleGenerativeAI(
        model="gemini-2.5-pro",
        temperature=temperature,
        google_api_key=os.getenv("GOOGLE_API_KEY"),
        streaming=True,
    )


_DEFAULT_RECURSION_LIMIT = 25


def create_conversational_agent(temperature: float = 1, recursion_limit: int = None):
    """Create a conversational agent using the new langchain.agents.create_agent API."""
    from app.tools import (
        get_current_time,
        wiki_search,
        graph_traverse,
        ingest_source,
        lint_wiki,
        sync_knowledge_base,
        mongodb_query,
        generate_chart,
    )

    llm = get_llm(temperature)

    tools = [
        get_current_time,
        wiki_search,
        graph_traverse,
        ingest_source,
        lint_wiki,
        sync_knowledge_base,
        mongodb_query,
        generate_chart,
    ]

    agent = create_agent(
        model=llm,
        tools=tools,
        system_prompt=SYSTEM_PROMPT,
    )

    limit = recursion_limit if recursion_limit is not None else _DEFAULT_RECURSION_LIMIT
    return agent.with_config({"recursion_limit": limit})
