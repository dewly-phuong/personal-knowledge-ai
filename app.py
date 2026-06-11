# app.py
import chainlit as cl
import logging
from typing import Optional
from app.agent import create_conversational_agent
from fastapi import Request, Response

logger = logging.getLogger(__name__)

@cl.password_auth_callback
def auth_callback(username: str, password: str) -> Optional[cl.User]:
    """Password auth handler for login"""
    
    if (username, password) == ("admin", "admin"): #For development
        return cl.User(identifier="admin", metadata={"role": "ADMIN"})
    else: 
        return None
    
@cl.on_logout
def on_logout(request: Request, response: Response):
    ### Handler to tidy up resources
    for cookie_name in request.cookies.keys():
        response.delete_cookie(cookie_name)

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
    # Now we can see who's starting the conversation!
    user = cl.user_session.get("user")
    logger.info(f"{user.identifier} has started the conversation")
    # Initialize the agent for this session
    agent_executor = create_conversational_agent(temperature=0.0)
    cl.user_session.set("agent", agent_executor)
    cl.user_session.set("chat_history", [])

    # await cl.Message(content="Chào bạn! Tôi là trợ lý AI. Bạn muốn hỏi gì hôm nay?").send()

@cl.on_chat_end
def on_chat_end():
    user = cl.user_session.get("user")
    logger.info(f"{user.identifier} has ended the chat")

    
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
