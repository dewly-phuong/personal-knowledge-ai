import os
import warnings
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_classic.agents import AgentExecutor, create_react_agent
from langchain_core.tools import Tool
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
import json
from app.tools import get_current_time, wiki_search, graph_traverse, ingest_source, lint_wiki, sync_knowledge_base, mongodb_query

def _mongodb_query_func(query_input: str) -> str:
    try:
        args = json.loads(query_input)
        return mongodb_query.invoke(args)
    except Exception as e:
        return f"Error parsing JSON input: {e}"

mongodb_query_wrapper = Tool(
    name="mongodb_query",
    description="Query structured company data from MongoDB. Use this when you need exact facts about employees, projects, bug tracking, KPIs, or organizational charts. Input must be a valid JSON string with keys: 'collection' (required), 'filter_json' (required), 'projection_json' (optional), and 'limit' (optional, default 100, max 1000). Example: '{\"collection\": \"employees\", \"filter_json\": \"{\\\"status\\\": \\\"active\\\"}\"}'",
    func=_mongodb_query_func
)

def _ingest_source_func(input_args: str) -> str:
    try:
        args = json.loads(input_args)
        return ingest_source.invoke(args)
    except Exception as e:
        return f"Error parsing JSON input: {e}"

ingest_source_wrapper = Tool(
    name="ingest_source",
    description="Triggers an asynchronous ingestion run for a source. Input must be a valid JSON string with keys 'source' ('local' or 'github') and 'path_or_repo'.",
    func=_ingest_source_func
)

# Suppress Headroom warning about Google client estimation
warnings.filterwarnings("ignore", category=UserWarning, message=".*GoogleProvider: No client provided.*")

try:
    from headroom.integrations import HeadroomChatModel, wrap_tools_with_headroom
    HAS_HEADROOM = True
except ImportError:
    HAS_HEADROOM = False

# Load environment variables
load_dotenv()

def get_llm(temperature: float = 0.3):
    """Initialize the Google Gemini LLM with a configurable temperature."""
    # Using gemini-2.5-pro as selected for multi-hop reasoning
    return ChatGoogleGenerativeAI(
        model="gemini-2.5-pro",
        temperature=temperature,
        google_api_key=os.getenv("GOOGLE_API_KEY"),
        streaming=True,
    )

def create_conversational_agent(temperature: float = 0.3):
    """Create a conversational agent with tool-calling capabilities."""
    llm = get_llm(temperature)
    
    if HAS_HEADROOM:
        try:
            llm = HeadroomChatModel(llm)
        except Exception:
            pass
    
    # Define system prompt focused on architecture, dependencies, and wiki search
    system_prompt_template = (
        "Bạn là một trợ lý ảo nội bộ đa năng, vừa là người đồng hành chu đáo hỗ trợ chăm sóc nhân viên, "
        "vừa là chuyên gia tra cứu thông tin dự án.\n"
        "Nhiệm vụ của bạn là sử dụng các công cụ được cung cấp để giải đáp các thắc mắc về chính sách nhân sự, "
        "phúc lợi, quy trình làm việc, cũng như thông tin kỹ thuật, mối quan hệ giữa các dịch vụ (services/pipelines) "
        "trong công ty.\n\n"
        "Hướng dẫn phong cách phản hồi:\n"
        "1. Đối với câu hỏi về chính sách, phúc lợi, đời sống nhân viên (HR/benefits/onboarding): Hãy trả lời với thái "
        "độ ấm áp, chu đáo, đồng cảm và sẵn sàng hỗ trợ. Đặt sự an tâm và trải nghiệm của nhân viên lên hàng đầu.\n"
        "2. Đối với câu hỏi về dự án, kỹ thuật, sơ đồ hệ thống: Hãy trả lời một cách rõ ràng, chính xác, có cấu trúc tốt "
        "và mang tính chuyên môn kỹ thuật cao.\n\n"
        "Quy tắc phản hồi nghiêm ngặt:\n"
        "1. Luôn ưu tiên tra cứu thông tin từ các nguồn thích hợp:\n"
        "   - Sử dụng `mongodb_query` cho các thông tin dạng bảng/có cấu trúc (như danh sách nhân viên, sơ đồ tổ chức, chi tiết dự án, ngân sách, kpi, hay danh sách lỗi/bug).\n"
        "   - Sử dụng `wiki_search` cho các tài liệu hướng dẫn, chính sách chung và `graph_traverse` cho mối quan hệ giữa các dịch vụ.\n"
        "2. Trích dẫn rõ nguồn tài liệu hoặc nguồn dữ liệu khi bạn sử dụng thông tin từ đó (ví dụ: `[Nguồn: wiki/...]` hoặc `[Nguồn: Cơ sở dữ liệu MongoDB - employees]`).\n"
        "3. Trả lời bằng tiếng Việt lịch sự, rõ ràng và mạch lạc.\n"
        "4. Nếu thông tin không có trong wiki, đồ thị hoặc cơ sở dữ liệu MongoDB, hãy chân thành báo cho nhân viên biết và hướng dẫn họ liên hệ bộ phận liên quan thay vì tự bịa ra câu trả lời.\n\n"
        "You have access to the following tools:\n\n"
        "{tools}\n\n"
        "Use the following format strictly without any deviation:\n\n"
        "Question: the input question you must answer\n"
        "Thought: you should always think about what to do\n"
        "Action: the action to take, should be one of [{tool_names}]\n"
        "Action Input: the input to the action (must be a raw string or raw JSON string, do NOT wrap in markdown code blocks like ```json)\n"
        "Observation: the result of the action\n"
        "... (this Thought/Action/Action Input/Observation can repeat N times)\n"
        "Thought: I now know the final answer\n"
        "Final Answer: the final answer to the original input question\n\n"
        "CRITICAL FORMATTING RULES:\n"
        "- Never use `Action: json\\n{{...}}`. You MUST use `Action: <tool_name>` followed immediately by `Action Input: <input>` on the next line.\n"
        "- Do not include conversational text before 'Thought:'. Always start your response with 'Thought:' or 'Final Answer:'."
    )

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt_template),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}\n\n{agent_scratchpad}"),
        ]
    )
    
    # Define tools using the wrappers for multi-input tools to satisfy ReAct's single string input requirement
    tools = [get_current_time, wiki_search, graph_traverse, ingest_source_wrapper, lint_wiki, sync_knowledge_base, mongodb_query_wrapper]
    
    # Only let headroom wrap the tools it is safe to wrap (not our custom single-string wrappers,
    # since headroom converts Tool → StructuredTool and breaks the single-string input contract)
    if HAS_HEADROOM:
        try:
            safe_tools = [t for t in tools if t not in (mongodb_query_wrapper, ingest_source_wrapper)]
            custom_tools = [mongodb_query_wrapper, ingest_source_wrapper]
            safe_tools = wrap_tools_with_headroom(safe_tools)
            tools = safe_tools + custom_tools
        except Exception:
            pass
            
    # Construct the agent
    agent = create_react_agent(llm, tools, prompt)
    
    # Create the agent executor
    agent_executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,
        return_intermediate_steps=True,
        handle_parsing_errors=True,
    )
    
    return agent_executor
