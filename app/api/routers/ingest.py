import asyncio
import json
import re

from fastapi import APIRouter, HTTPException

from app.api.schemas import IngestRequest
from app.core.redis import get_redis_client

router = APIRouter(prefix="/api/ingest", tags=["ingest"])


@router.post("")
async def trigger_ingest(body: IngestRequest):
    """Triggers background document ingestion and returns a task ID."""
    from app.tools.ingest import ingest_source

    loop = asyncio.get_running_loop()
    res = await loop.run_in_executor(
        None,
        ingest_source.invoke,
        {"source": body.source, "path_or_repo": body.path_or_repo},
    )
    match = re.search(r"Task ID: ([a-f0-9\-]+)", res)
    task_id = match.group(1) if match else "unknown"
    return {"status": "scheduled", "task_id": task_id}


@router.get("/{task_id}")
async def get_ingest_status(task_id: str):
    """Retrieves the status of a background ingestion task from Redis."""
    task_data = get_redis_client().get(f"ingest:task:{task_id}")
    if not task_data:
        raise HTTPException(
            status_code=404, detail=f"Ingestion task {task_id} not found."
        )
    return json.loads(task_data)
