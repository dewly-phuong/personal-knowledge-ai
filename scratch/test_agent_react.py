from dotenv import load_dotenv
from app.agent import create_conversational_agent

load_dotenv()

agent = create_conversational_agent(temperature=0.0)

query = "Hoàng Văn Tuấn đã nghỉ đúng theo chính sách nghỉ phép hay sai"
print(f"Running agent with query: {query}")

try:
    res = agent.invoke({"input": query, "chat_history": []})
    print("Agent execution succeeded:")
    print(res.get("output"))
except Exception as e:
    print("Agent execution failed with exception:")
    print(e)
