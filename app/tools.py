import datetime
from langchain.tools import tool

@tool
def get_current_time():
    """Get the current time in the system. Use this whenever you are asked about the current time."""
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

@tool
def search_dummy(query: str):
    """A dummy search tool to simulate external knowledge retrieval. Use this for general questions that might require searching."""
    return f"Simulated search results for: {query}. The answer is likely related to this query but this is a placeholder."
