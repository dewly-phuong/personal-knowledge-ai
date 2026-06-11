import asyncio
import json
import os
import re
import datetime
from contextlib import asynccontextmanager
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Tuple, Optional, Dict, Any
from langchain_core.callbacks import BaseCallbackHandler
from chainlit.utils import mount_chainlit
from apscheduler.schedulers.background import BackgroundScheduler

from app.services.graph_store import GraphStore
from app.core.redis import get_redis_client
from app.agent import create_conversational_agent

class QueueCallbackHandler(BaseCallbackHandler):
    """Callback handler to stream LLM tokens, token usage, and tool executions into an asyncio.Queue."""
    def __init__(self, queue: asyncio.Queue):
        self.queue = queue
        
    def on_llm_new_token(self, token: str, **kwargs) -> None:
        self.queue.put_nowait({"type": "token", "value": token})
        
    def on_llm_end(self, response, **kwargs) -> None:
        try:
            for generations in response.generations:
                for gen in generations:
                    if hasattr(gen, "message") and gen.message.usage_metadata:
                        usage = gen.message.usage_metadata
                        input_tokens = usage.get("input_tokens", 0)
                        output_tokens = usage.get("output_tokens", 0)
                        self.queue.put_nowait({
                            "type": "usage", 
                            "input": input_tokens, 
                            "output": output_tokens
                        })
        except Exception as e:
            print(f"Error extracting token usage: {e}")
        
    def on_llm_error(self, error: BaseException, **kwargs) -> None:
        pass

    def on_tool_start(self, serialized: Dict[str, Any], input_str: str, **kwargs) -> None:
        tool_name = serialized.get("name", "Unknown Tool")
        self.queue.put_nowait({
            "type": "step_start",
            "name": tool_name,
            "input": input_str
        })

    def on_tool_end(self, output: Any, **kwargs) -> None:
        self.queue.put_nowait({
            "type": "step_end",
            "output": str(output)
        })

    def on_tool_error(self, error: BaseException, **kwargs) -> None:
        self.queue.put_nowait({
            "type": "step_end",
            "output": f"Tool execution error: {error}"
        })


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
    chat_history: List[Tuple[str, str]] = []

async def chat_generator(query: str, chat_history: List[Tuple[str, str]]):
    queue = asyncio.Queue()
    cb = QueueCallbackHandler(queue)
    
    formatted_history = []
    for role, text in chat_history:
        formatted_history.append((role, text))
        
    agent = create_conversational_agent(temperature=0.0)
    
    # Run agent in background task
    task = asyncio.create_task(
        agent.ainvoke(
            {"input": query, "chat_history": formatted_history},
            config={"callbacks": [cb]}
        )
    )
    task.add_done_callback(lambda _: queue.put_nowait(None))
    
    total_input = 0
    total_output = 0
    
    while True:
        try:
            item = await asyncio.wait_for(queue.get(), timeout=20.0)
            if item is None:
                break
                
            if isinstance(item, dict):
                itype = item.get("type")
                if itype == "token":
                    yield f"data: {json.dumps({'type': 'token', 'token': item['value']})}\n\n"
                elif itype == "step_start":
                    yield f"data: {json.dumps({'type': 'step_start', 'name': item['name'], 'input': item['input']})}\n\n"
                elif itype == "step_end":
                    yield f"data: {json.dumps({'type': 'step_end', 'output': item['output']})}\n\n"
                elif itype == "usage":
                    total_input += item.get("input", 0)
                    total_output += item.get("output", 0)
                    
            queue.task_done()
        except asyncio.TimeoutError:
            if task.done():
                break

    try:
        res = await task
        output = res.get('output', '')
        if isinstance(output, list):
            output_str = ""
            for part in output:
                if isinstance(part, dict) and "text" in part:
                    output_str += part["text"]
                elif isinstance(part, str):
                    output_str += part
            output = output_str
            
        # Record costs in Redis
        estimated_cost = accumulate_costs(total_input, total_output)
        
        done_payload = {
            'type': 'done',
            'output': output,
            'usage': {'input': total_input, 'output': total_output},
            'cost': estimated_cost
        }
        yield f"data: {json.dumps(done_payload)}\n\n"
    except Exception as e:
        yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"

@app.post("/api/chat")
async def chat_stream(request: ChatRequest):
    """Streams chat tokens and intermediate tool execution steps from the agent."""
    return StreamingResponse(
        chat_generator(request.query, request.chat_history),
        media_type="text/event-stream"
    )

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

@app.get("/api/health")
def health_check():
    return {"status": "ok", "message": "Server FastAPI đang hoạt động"}

# Mount Chainlit chat UI on /chat
mount_chainlit(app=app, target="app.py", path="/chat")
