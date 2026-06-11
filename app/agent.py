import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_classic.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from app.tools import get_current_time, search_dummy

# Load environment variables
load_dotenv()

def get_llm(temperature: float = 0.0):
    """Initialize the Google Gemini LLM with a configurable temperature."""
    return ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        temperature=temperature,
        google_api_key=os.getenv("GOOGLE_API_KEY")
    )

def create_conversational_agent(temperature: float = 0.0):
    """Create a conversational agent with tool calling capabilities."""
    llm = get_llm(temperature=temperature)
    tools = [get_current_time, search_dummy]
    
    # Define the prompt template
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a helpful and intelligent AI assistant. You can use tools to answer questions more accurately."),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])
    
    # Create the agent
    agent = create_tool_calling_agent(llm, tools, prompt)
    
    # Create the executor
    agent_executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,
        handle_parsing_errors=True
    )
    
    return agent_executor
