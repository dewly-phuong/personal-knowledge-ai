# Fix for engineio packet limit error ("Too many packets in payload")
try:
    from engineio.payload import Payload
    Payload.max_decode_packets = 2048
except ImportError:
    pass

import asyncio
import json
import os
import re
import datetime
from contextlib import asynccontextmanager
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.responses import StreamingResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict
from langchain_core.messages import HumanMessage
from chainlit.utils import mount_chainlit
from apscheduler.schedulers.background import BackgroundScheduler

from app.services.graph_store import GraphStore
from app.core.redis import get_redis_client
from app.agent import create_conversational_agent
from app.memory.session_store import SessionStore
from app.memory.history_manager import HistoryManager



def scheduled_sync_and_lint():
    """Daily job that runs pipeline sync and audits wiki health."""
    print(f"\n--- [Scheduled Job] Starting daily Sync & Lint ({datetime.datetime.now()}) ---")
    try:
        from ingest import run_ingest_pipeline
        from app.tools import lint_wiki
        
        # 1. Run local files ingestion
        run_ingest_pipeline(source="local", dir_path="raw/local")
        
        # 2. Run wiki audit
        report = lint_wiki.invoke({})
        
        # 3. Save health report
        os.makedirs("wiki", exist_ok=True)
        with open("wiki/health_report.md", "w", encoding="utf-8") as f:
            f.write(report)
            
        print("[Scheduled Job] Sync & Lint completed successfully. Health report saved to wiki/health_report.md.")
    except Exception as e:
        print(f"[Scheduled Job] Error running daily sync: {e}")


def accumulate_costs(input_tokens: int, output_tokens: int) -> float:
    """Computes Gemini 2.5 Pro costs and records statistics in Redis."""
    # Pricing: $0.075 / 1M input, $0.30 / 1M output
    input_rate = 0.075 / 1_000_000
    output_rate = 0.30 / 1_000_000
    cost = (input_tokens * input_rate) + (output_tokens * output_rate)
    
    try:
        r = get_redis_client()
        today_str = datetime.date.today().isoformat()
        month_str = today_str[:7]
        
        # 1. Daily Stats
        daily_key = f"cost:daily:{today_str}"
        r.hincrby(daily_key, "input", input_tokens)
        r.hincrby(daily_key, "output", output_tokens)
        r.hincrbyfloat(daily_key, "cost", cost)
        r.expire(daily_key, 30 * 86400)  # TTL 30 days
        
        # 2. Monthly Stats
        monthly_key = f"cost:monthly:{month_str}"
        r.hincrby(monthly_key, "input", input_tokens)
        r.hincrby(monthly_key, "output", output_tokens)
        r.hincrbyfloat(monthly_key, "cost", cost)
        r.expire(monthly_key, 365 * 86400)  # TTL 365 days
    except Exception as e:
        print(f"Error saving cost metrics to Redis: {e}")
        
    return cost


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("\n--- FastAPI Lifespan Startup ---")
    
    # 1. Load GraphStore
    app.state.graph_store = GraphStore()
    print(f"Knowledge Graph pre-loaded. Nodes: {len(app.state.graph_store.graph.nodes)}, Edges: {len(app.state.graph_store.graph.edges)}")
    
    # 2. Connect to Redis
    try:
        r = get_redis_client()
        r.ping()
        print("Connected to Redis successfully.")
    except Exception as e:
        print(f"Warning: Failed to connect to Redis: {e}")

    # Initialize SessionStore and HistoryManager
    app.state.session_store = SessionStore()
    app.state.history_manager = HistoryManager(store=app.state.session_store)
    print("SessionStore and HistoryManager initialized.")
        
    # 3. Start Daily Scheduler
    scheduler = BackgroundScheduler()
    # Execute scheduled job once every 24 hours (daily)
    scheduler.add_job(scheduled_sync_and_lint, 'interval', hours=24)
    scheduler.start()
    app.state.scheduler = scheduler
    print("Daily Scheduler started successfully.")
    
    print("--------------------------------\n")
    yield
    print("\n--- FastAPI Lifespan Shutdown ---")
    if hasattr(app.state, "scheduler"):
        app.state.scheduler.shutdown()
        print("Scheduler shut down successfully.")
    if hasattr(app.state, "session_store"):
        await app.state.session_store.flush()
        app.state.session_store.close()
        print("Session store background tasks flushed and closed.")


app = FastAPI(lifespan=lifespan)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    query: str
    session_id: str

async def chat_generator(query: str, session_id: str, history_manager: HistoryManager):
    chat_history = await history_manager.get_context(session_id)
    agent = create_conversational_agent(temperature=1.0)

    # create_agent expects {"messages": [*history, HumanMessage(query)]}
    input_messages = list(chat_history) + [HumanMessage(content=query)]

    total_input = 0
    total_output = 0
    output = ""
    new_messages = []

    try:
        async for event in agent.astream_events(
            {"messages": input_messages},
            version="v2",
        ):
            kind = event.get("event")

            if kind == "on_chat_model_stream":
                chunk = event.get("data", {}).get("chunk")
                if chunk and hasattr(chunk, "content"):
                    content = chunk.content
                    if isinstance(content, list):
                        for part in content:
                            if not isinstance(part, dict):
                                continue
                            ptype = part.get("type", "")
                            if ptype == "text" and part.get("text"):
                                yield f"data: {json.dumps({'type': 'token', 'token': part['text']})}\n\n"
                            elif ptype == "thinking" and part.get("thinking"):
                                yield f"data: {json.dumps({'type': 'thinking', 'token': part['thinking']})}\n\n"
                    elif isinstance(content, str) and content:
                        yield f"data: {json.dumps({'type': 'token', 'token': content})}\n\n"
                # langchain-google-genai exposes thinking in additional_kwargs too
                if chunk and hasattr(chunk, "additional_kwargs"):
                    thinking_text = chunk.additional_kwargs.get("thinking", "")
                    if thinking_text:
                        yield f"data: {json.dumps({'type': 'thinking', 'token': thinking_text})}\n\n"

            elif kind == "on_tool_start":
                tool_name = event.get("name", "tool")
                tool_input = event.get("data", {}).get("input", "")
                if not isinstance(tool_input, str):
                    tool_input = json.dumps(tool_input, ensure_ascii=False)
                yield f"data: {json.dumps({'type': 'step_start', 'name': tool_name, 'input': tool_input})}\n\n"

            elif kind == "on_tool_end":
                raw_output = event.get("data", {}).get("output", "")
                # LangGraph wraps tool returns in a ToolMessage object — extract .content
                if hasattr(raw_output, "content"):
                    tool_output = str(raw_output.content)
                else:
                    tool_output = str(raw_output)

                if tool_output.startswith("CHART_JSON:"):
                    chart_json = tool_output[len("CHART_JSON:"):]
                    yield f"data: {json.dumps({'type': 'chart', 'chart_json': chart_json})}\n\n"
                    # Store full JSON in step output so data layer persists it for page reload
                    yield f"data: {json.dumps({'type': 'step_end', 'output': tool_output})}\n\n"
                else:
                    yield f"data: {json.dumps({'type': 'step_end', 'output': tool_output})}\n\n"

            elif kind == "on_chat_model_end":
                response = event.get("data", {}).get("output")
                if response and hasattr(response, "usage_metadata") and response.usage_metadata:
                    usage = response.usage_metadata
                    total_input += usage.get("input_tokens", 0)
                    total_output += usage.get("output_tokens", 0)

            elif kind == "on_chain_end" and event.get("name") == "LangGraph":
                # Final graph output — extract last AIMessage as the answer
                result = event.get("data", {}).get("output", {})
                msgs = result.get("messages", [])
                if msgs:
                    last = msgs[-1]
                    content = getattr(last, "content", "")
                    if isinstance(content, list):
                        output = "".join(
                            p["text"] if isinstance(p, dict) and "text" in p else str(p)
                            for p in content
                        )
                    else:
                        output = str(content)
                    new_messages = msgs

        estimated_cost = accumulate_costs(total_input, total_output)
        await history_manager.append_turn(session_id, query, output, new_messages)

        yield f"data: {json.dumps({'type': 'done', 'output': output, 'usage': {'input': total_input, 'output': total_output}, 'cost': estimated_cost})}\n\n"

    except Exception as e:
        yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"

@app.post("/api/chat")
async def chat_stream(request: ChatRequest):
    """Streams chat tokens and intermediate tool execution steps from the agent."""
    return StreamingResponse(
        chat_generator(request.query, request.session_id, app.state.history_manager),
        media_type="text/event-stream"
    )

@app.get("/api/chat/{session_id}")
async def get_chat_history(session_id: str):
    """Retrieves the raw conversation history messages for a given session."""
    store = app.state.session_store
    from langchain_core.messages import messages_to_dict
    messages = await store.load(session_id)
    return {"messages": messages_to_dict(messages)}

@app.delete("/api/chat/{session_id}")
async def clear_chat_history(session_id: str):
    """Clears history for a given session."""
    await app.state.history_manager.clear(session_id)
    return {"status": "ok", "message": f"Chat history for session {session_id} has been cleared"}

class SyncHistoryRequest(BaseModel):
    messages: List[Dict[str, str]]

@app.post("/api/chat/{session_id}/sync")
async def sync_chat_history(session_id: str, payload: SyncHistoryRequest):
    """Syncs/overwrites the conversation history for a given session."""
    from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
    
    langchain_messages = []
    for msg in payload.messages:
        role = msg.get("role")
        content = msg.get("content", "")
        if role == "user":
            langchain_messages.append(HumanMessage(content=content))
        elif role == "assistant":
            langchain_messages.append(AIMessage(content=content))
        elif role == "system":
            langchain_messages.append(SystemMessage(content=content))
            
    store = app.state.session_store
    await store.save(session_id, langchain_messages)
    await store.flush()
    return {"status": "ok", "message": f"Chat history for session {session_id} synced successfully."}

class IngestRequest(BaseModel):
    source: str
    path_or_repo: str

@app.post("/api/ingest")
async def trigger_ingest(request: IngestRequest):
    """Triggers background document ingestion."""
    from app.tools import ingest_source
    res = ingest_source.invoke({"source": request.source, "path_or_repo": request.path_or_repo})
    match = re.search(r'Task ID: ([a-f0-9\-]+)', res)
    task_id = match.group(1) if match else "unknown"
    return {"status": "scheduled", "task_id": task_id}

@app.get("/api/ingest/{task_id}")
async def get_ingest_status(task_id: str):
    """Retrieves status of a background ingestion task from Redis."""
    r = get_redis_client()
    task_data = r.get(f"ingest:task:{task_id}")
    if not task_data:
        raise HTTPException(status_code=404, detail=f"Ingestion task {task_id} not found.")
    return json.loads(task_data)

@app.get("/api/graph/{entity}")
async def get_entity_graph(entity: str):
    """Returns the 2-hop neighborhood of a given entity in JSON format."""
    store = GraphStore()
    return store.get_subgraph(entity, hops=2)

@app.get("/api/cost")
async def get_cost_stats():
    """Retrieves accumulated LLM API costs for today and the current month."""
    try:
        r = get_redis_client()
        today_str = datetime.date.today().isoformat()
        month_str = today_str[:7]
        
        today_data = r.hgetall(f"cost:daily:{today_str}") or {}
        month_data = r.hgetall(f"cost:monthly:{month_str}") or {}
        
        return {
            "today": {
                "date": today_str,
                "input_tokens": int(today_data.get("input", 0)),
                "output_tokens": int(today_data.get("output", 0)),
                "cost_usd": round(float(today_data.get("cost", 0.0)), 6)
            },
            "month": {
                "month": month_str,
                "input_tokens": int(month_data.get("input", 0)),
                "output_tokens": int(month_data.get("output", 0)),
                "cost_usd": round(float(month_data.get("cost", 0.0)), 6)
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error accessing cost stats from Redis: {e}")

@app.get("/api/elements/{element_id}/plotly")
async def serve_plotly_element(element_id: str):
    """Serves persisted Plotly figure JSON for a given element ID."""
    from motor.motor_asyncio import AsyncIOMotorClient
    client = AsyncIOMotorClient(os.getenv("MONGO_URI", "mongodb://localhost:27017/"))
    db = client["personal_knowledge_ai"]
    doc = await db["cl_elements"].find_one({"id": element_id})
    if not doc or not doc.get("_plotly_content"):
        raise HTTPException(status_code=404, detail="Plotly element content not found")
    return Response(content=doc["_plotly_content"], media_type="application/json")

@app.get("/api/health")
async def health_check():
    store = app.state.session_store
    mongo_ok = await store.ping_mongo()
    redis_ok = await store.ping_redis()
    
    overall = "ok" if (mongo_ok and redis_ok) else "degraded"
    
    return {
        "status": overall,
        "fastapi": "ok",
        "redis": "connected" if redis_ok else "disconnected",
        "mongodb": "connected" if mongo_ok else "disconnected",
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
    }

# Mount Chainlit chat UI on /chat
mount_chainlit(app=app, target="app.py", path="/chat")
