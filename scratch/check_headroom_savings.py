import os
from dotenv import load_dotenv
load_dotenv()

from langchain_google_genai import ChatGoogleGenerativeAI
from headroom.integrations import HeadroomChatModel, wrap_tools_with_headroom
from app.tools import wiki_search

def run_test():
    print("Initializing LLM...")
    raw_llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=os.getenv("GOOGLE_API_KEY")
    )
    
    # Wrap model with Headroom
    llm = HeadroomChatModel(raw_llm)
    print("Wrapped LLM with HeadroomChatModel.")

    # Wrap tools
    tools = [wiki_search]
    wrapped_tools = wrap_tools_with_headroom(tools)
    print("Wrapped tools with Headroom.")

    # Invoke wrapped model with a multi-turn message history containing a large ToolMessage
    print("\nSending a conversation history with a large ToolMessage to trigger Headroom compression...")
    from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
    
    messages = [
        HumanMessage(content="Hello"),
        AIMessage(content="Hi! I am the assistant."),
        HumanMessage(content="Please search the wiki for auth service configurations."),
        ToolMessage(
            content="Configuration details:\n" + "\n".join([f"service-auth-port={i}, host=auth-server-{i}.local, security=tls, max_connections=1000" for i in range(150)]),
            name="wiki_search",
            tool_call_id="call_123"
        ),
        HumanMessage(content="Great, summarize the host connections from the search results.")
    ]
    
    response = llm.invoke(messages)
    print(f"\nResponse:\n{response.content}\n")

    # Get headroom savings summary
    try:
        summary = llm.get_savings_summary()
        print("=== Headroom Savings Summary ===")
        print(summary)
        print(f"Total Tokens Saved: {llm.total_tokens_saved}")
    except Exception as e:
        print("Failed to get savings summary:", e)

if __name__ == "__main__":
    run_test()
