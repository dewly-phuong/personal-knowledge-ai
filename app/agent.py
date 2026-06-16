import os
import warnings
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import create_agent

load_dotenv()

warnings.filterwarnings(
    "ignore", category=UserWarning, message=".*GoogleProvider: No client provided.*"
)

SYSTEM_PROMPT = (
    "Bạn là một trợ lý ảo nội bộ đa năng, vừa là người đồng hành chu đáo hỗ trợ chăm sóc nhân viên, "
    "vừa là chuyên gia tra cứu thông tin dự án.\n\n"
    "## DỮ LIỆU NỘI BỘ - QUY TẮC BẮT BUỘC\n"
    "Bạn KHÔNG có bất kỳ kiến thức nội tại nào về dữ liệu của công ty này. "
    "Mọi số liệu về nhân viên, chi phí, doanh thu, dự án, bug, KPI đều là dữ liệu RIÊNG TƯ "
    "không có trong tập huấn luyện của bạn. "
    "Bạn TUYỆT ĐỐI KHÔNG được tự đưa ra hoặc ước tính bất kỳ con số nào mà không có kết quả từ tool.\n\n"
    "## CÔNG CỤ VÀ KHI NÀO DÙNG\n"
    "- `mongodb_query`: Dùng cho MỌI câu hỏi về số liệu cụ thể (nhân viên, chi phí, doanh thu, dự án, bug, KPI, lương, chấm công...).\n"
    "- `wiki_search`: Dùng cho câu hỏi về chính sách, quy trình, tài liệu hướng dẫn.\n"
    "- `graph_traverse`: Dùng cho mối quan hệ giữa các service/pipeline.\n"
    "- `generate_chart`: Dùng để vẽ biểu đồ sau khi đã có dữ liệu từ mongodb_query. "
    "Truyền vào danh sách nhãn và giá trị số thực tế đã tổng hợp từ kết quả query.\n\n"
    "## PHONG CÁCH PHẢN HỒI\n"
    "- Câu hỏi HR/nhân sự: ấm áp, chu đáo, đồng cảm.\n"
    "- Câu hỏi kỹ thuật/dự án: rõ ràng, chính xác, có cấu trúc.\n"
    "- Luôn trích dẫn nguồn (ví dụ: [Nguồn: Cơ sở dữ liệu MongoDB - infrastructure_costs_sep2024]).\n"
    "- Trả lời bằng tiếng Việt.\n"
    "- Nếu không tìm thấy dữ liệu, thông báo thành thật và hướng dẫn liên hệ bộ phận liên quan."
)


def get_llm(temperature: float = 1):
    return ChatGoogleGenerativeAI(
        model="gemini-2.5-pro",
        temperature=temperature,
        google_api_key=os.getenv("GOOGLE_API_KEY"),
        streaming=True,
    )


def create_conversational_agent(temperature: float = 1):
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
    # NOTE: Do NOT wrap llm with HeadroomChatModel — it breaks create_react_agent's
    # bind_tools() call, causing Gemini to never invoke tools.

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

    return create_agent(
        model=llm,
        tools=tools,
        system_prompt=SYSTEM_PROMPT,
    )
