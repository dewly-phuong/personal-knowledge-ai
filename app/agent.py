import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_classic.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from app.tools import get_current_time, wiki_search, graph_traverse, ingest_source, lint_wiki, sync_knowledge_base

# Load environment variables
load_dotenv()

def get_llm(temperature: float = 0.0):
    """Initialize the Google Gemini LLM with a configurable temperature."""
    # Using gemini-2.5-pro as selected for multi-hop reasoning
    return ChatGoogleGenerativeAI(
        model="gemini-2.5-pro",
        temperature=temperature,
        google_api_key=os.getenv("GOOGLE_API_KEY"),
        streaming=True,
    )

def create_conversational_agent(temperature: float = 0.0):
    """Create a conversational agent with tool-calling capabilities."""
    llm = get_llm(temperature)
    
    # Define system prompt focused on architecture, dependencies, and wiki search
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "Bạn là trợ lý ảo chuyên gia về kiến trúc hệ thống và quy trình kỹ thuật phần mềm.\n"
                "Nhiệm vụ của bạn là sử dụng các công cụ được cung cấp để trả lời các câu hỏi về sơ đồ kiến trúc, "
                "mối quan hệ giữa các dịch vụ (services/pipelines), và nội dung tài liệu wiki.\n\n"
                "Quy tắc phản hồi:\n"
                "1. Luôn ưu tiên tra cứu thông tin từ wiki bằng công cụ `wiki_search` và mối quan hệ từ đồ thị bằng `graph_traverse`.\n"
                "2. Trích dẫn rõ nguồn tài liệu (ví dụ: `[Nguồn: wiki/concepts/auth-service.md]`) khi bạn sử dụng thông tin từ đó.\n"
                "3. Trả lời bằng tiếng Việt lịch sự, rõ ràng, và mang tính chuyên môn kỹ thuật cao.\n"
                "4. Nếu thông tin không có trong wiki hoặc đồ thị, hãy báo cho người dùng biết thay vì tự bịa ra câu trả lời."
            ),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ]
    )
    
    # Define tools
    tools = [get_current_time, wiki_search, graph_traverse, ingest_source, lint_wiki, sync_knowledge_base]
    
    # Construct the agent
    agent = create_tool_calling_agent(llm, tools, prompt)
    
    # Create the agent executor
    agent_executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,
    )
    
    return agent_executor
