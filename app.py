import os
import re
import chainlit as cl
import logging
import httpx
import json
from typing import Optional
from fastapi import Request, Response

logger = logging.getLogger(__name__)

@cl.password_auth_callback
def auth_callback(username: str, password: str) -> Optional[cl.User]:
    """Password auth handler for login"""
    if (username, password) == ("admin", "admin"):
        return cl.User(identifier="admin", metadata={"role": "ADMIN"})
    return None

@cl.on_logout
def on_logout(request: Request, response: Response):
    for cookie_name in request.cookies.keys():
        response.delete_cookie(cookie_name)

@cl.set_starters
async def set_chat_starters():
    return [
        cl.Starter(
            label="Tra cứu wiki",
            message="Tìm kiếm thông tin về qmd và các tính năng chính của nó",
        ),
        cl.Starter(
            label="Xem kết nối dịch vụ",
            message="Giải thích các mối quan hệ và dependencies xung quanh auth-service",
        ),
        cl.Starter(
            label="Kiểm tra chất lượng Wiki",
            message="Hãy chạy kiểm tra sức khỏe (lint) của wiki hiện tại",
        ),
    ]

@cl.on_chat_start
async def start():
    user = cl.user_session.get("user")
    logger.info(f"{user.identifier if user else 'Guest'} has started the conversation")
    cl.user_session.set("chat_history", [])

@cl.on_chat_end
def on_chat_end():
    user = cl.user_session.get("user")
    logger.info(f"{user.identifier if user else 'Guest'} has ended the chat")

def resolve_citations(text: str) -> str:
    """
    Parses references like [Nguồn: wiki/services/auth-service.md] in the text,
    reads the front matter of the cited file, and replaces it with its original
    clickable source URL (e.g. Confluence/GitHub link).
    """
    # Pattern to match [Nguồn: wiki/...] or [Nguồn: wiki\...]
    pattern = r'\[Nguồn:\s*(wiki/[^\]]+)\]'
    matches = re.findall(pattern, text)
    
    for rel_path in matches:
        # Resolve path to local workspace file
        abs_path = os.path.abspath(rel_path)
        if os.path.exists(abs_path):
            try:
                with open(abs_path, "r", encoding="utf-8") as f:
                    content = f.read()
                
                # Parse front matter for source_docs: [...]
                source_url = None
                if content.startswith("---"):
                    parts = content.split("---", 2)
                    if len(parts) >= 3:
                        yaml_text = parts[1]
                        doc_match = re.search(r'source_docs:\s*\[(.*?)\]', yaml_text)
                        if doc_match:
                            urls = [u.strip().strip("'").strip('"') for u in doc_match.group(1).split(",") if u.strip()]
                            if urls:
                                source_url = urls[0]
                
                if source_url:
                    basename = os.path.basename(rel_path)
                    replacement = f"[Nguồn: {basename}]({source_url})"
                    text = text.replace(f"[Nguồn: {rel_path}]", replacement)
            except Exception as e:
                print(f"Error parsing front matter for {rel_path}: {e}")
                
    return text

@cl.on_message
async def on_message(message: cl.Message):
    chat_history = cl.user_session.get("chat_history", [])
    url = "http://localhost:8000/api/chat"
    
    # Initialize main message
    streamed_msg = cl.Message(content="")
    await streamed_msg.send()
    
    payload = {
        "query": message.content,
        "chat_history": chat_history
    }
    
    # Keep track of active Chainlit steps (tool calls)
    active_steps = {}
    
    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            async with client.stream("POST", url, json=payload) as response:
                if response.status_code != 200:
                    await streamed_msg.update(content=f"Error from server: HTTP {response.status_code}")
                    return
                    
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]
                        try:
                            data = json.loads(data_str)
                            dtype = data.get("type")
                            
                            if dtype == "step_start":
                                # 1. Render active tool thinking block
                                step_name = data.get("name")
                                step_input = data.get("input")
                                
                                step = cl.Step(name=step_name)
                                step.input = step_input
                                await step.send()
                                active_steps[step_name] = step
                                
                            elif dtype == "step_end":
                                # 2. Update and close active thinking block
                                step_name = list(active_steps.keys())[-1] if active_steps else None
                                if step_name:
                                    step = active_steps.pop(step_name)
                                    step.output = data.get("output", "")
                                    await step.update()
                                    
                            elif dtype == "token":
                                # 3. Stream text tokens to main message
                                await streamed_msg.stream_token(data["token"])
                                
                            elif dtype == "done":
                                # 4. Resolve wiki links/citations to clickable remote URLs
                                final_output = data.get("output", "")
                                resolved_output = resolve_citations(final_output)
                                await streamed_msg.update(content=resolved_output)
                                
                            elif dtype == "error":
                                await streamed_msg.stream_token(f"\n[Error: {data['error']}]")
                                
                        except Exception as json_err:
                            print(f"Error parsing chunk: {json_err} for line: {line}")
                            
        # Save chat history
        chat_history.append(("human", message.content))
        chat_history.append(("ai", streamed_msg.content))
        cl.user_session.set("chat_history", chat_history)
        await streamed_msg.update()
        
    except Exception as e:
        await cl.Message(content=f"Error connecting to chat API: {e}. Hãy đảm bảo server FastAPI đang chạy tại localhost:8000.").send()
