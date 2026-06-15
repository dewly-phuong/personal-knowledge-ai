import os
from dotenv import load_dotenv
load_dotenv()

from langchain_google_genai import ChatGoogleGenerativeAI
from headroom.integrations import HeadroomChatModel, wrap_tools_with_headroom
from app.tools import wiki_search

def test():
    print("Testing headroom-ai imports...")
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=os.getenv("GOOGLE_API_KEY")
    )
    print("Base LLM initialized.")
    
    # Try wrapping LLM
    try:
        wrapped_llm = HeadroomChatModel(llm)
        print("Wrapped LLM with HeadroomChatModel successfully.")
    except Exception as e:
        print("Failed to wrap LLM:", e)
        return

    # Try wrapping tools
    try:
        tools = [wiki_search]
        wrapped_tools = wrap_tools_with_headroom(tools)
        print("Wrapped tools successfully:", wrapped_tools)
    except Exception as e:
        print("Failed to wrap tools:", e)

if __name__ == "__main__":
    test()
