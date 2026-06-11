# app.py
import chainlit as cl
import logging
from app.agent import create_conversational_agent

logger = logging.getLogger(__name__)

@cl.set_starters
async def set_chat_starters():
    return [
        cl.Starter(
            label="Hỏi giờ",
            message="Bây giờ là mấy giờ?",
        ),
        cl.Starter(
            label="Tìm kiếm",
            message="Tìm kiếm thông tin về Gemini CLI",
        ),
    ]


@cl.on_chat_start
async def start():
    # Initialize the agent for this session
    agent_executor = create_conversational_agent(temperature=0.0)
    cl.user_session.set("agent", agent_executor)
    cl.user_session.set("chat_history", [])

    await cl.Message(content="Chào bạn! Tôi là trợ lý AI. Bạn muốn hỏi gì hôm nay?").send()

@cl.on_settings_update
async def setup_agent(settings):
    # Re-initialize agent with new temperature
    agent_executor = create_conversational_agent(temperature=settings["Temperature"])
    cl.user_session.set("agent", agent_executor)
    await cl.Message(content=f"Đã cập nhật nhiệt độ sang {settings['Temperature']}").send()

@cl.on_message
async def on_message(message: cl.Message):
    # Retrieve the agent and chat history from the session
    agent = cl.user_session.get("agent")
    chat_history = cl.user_session.get("chat_history")
    
    # Initialize the Chainlit LangChain callback handler
    # This automatically shows tool usage and thought process in the UI
    cb = cl.LangchainCallbackHandler(stream_final_answer=True)
    
    # Run the agent
    res = await agent.ainvoke(
        {"input": message.content, "chat_history": chat_history},
        config={"callbacks": [cb]}
    )
    
    output = res["output"]
    
    # Update chat history
    chat_history.append(("human", message.content))
    chat_history.append(("ai", output))
    cl.user_session.set("chat_history", chat_history)
    
    # If the final answer wasn't streamed, send it manually
    if not cb.final_stream:
        await cl.Message(content=output).send()
