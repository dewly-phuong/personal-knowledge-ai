"""
Ingestion tools: ingest_source, sync_knowledge_base.
Background-thread runner + Redis task store.
"""

import datetime
import json
import threading
import uuid

from langchain_core.tools import tool

from app.core.redis import get_redis_client


def _run_ingest_async(task_id: str, source: str, path_or_repo: str) -> None:
    r = get_redis_client()
    task_key = f"ingest:task:{task_id}"
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    try:
        from ingest import run_ingest_pipeline

        if source == "local":
            result = run_ingest_pipeline(source=source, dir_path=path_or_repo)
        elif source == "github":
            result = run_ingest_pipeline(source=source, repo_name=path_or_repo)
        else:
            raise ValueError(f"Unsupported source: {source}")
        task_data = {
            "status": "SUCCESS",
            "started_at": now,
            "finished_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "error": None,
            "summary": result.get("summary", "Ingestion run finished."),
        }
    except Exception as e:
        task_data = {
            "status": "FAILED",
            "started_at": now,
            "finished_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "error": str(e),
            "summary": "Ingestion failed with error.",
        }
    r.set(task_key, json.dumps(task_data), ex=7 * 86400)


def _schedule_ingest(source: str, path_or_repo: str, summary: str) -> str:
    """Creates a PENDING task in Redis and starts a daemon background thread. Returns task_id."""
    task_id = str(uuid.uuid4())
    r = get_redis_client()
    r.set(
        f"ingest:task:{task_id}",
        json.dumps(
            {
                "status": "PENDING",
                "started_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "finished_at": None,
                "error": None,
                "summary": summary,
            }
        ),
        ex=7 * 86400,
    )
    threading.Thread(
        target=_run_ingest_async, args=(task_id, source, path_or_repo), daemon=True
    ).start()
    return task_id


@tool
def ingest_source(source: str, path_or_repo: str) -> str:
    """
    Triggers an asynchronous ingestion run for a source.
    source: 'local' (requires directory path) or 'github' (requires 'owner/repo').
    path_or_repo: The directory path or github repo identifier.
    Returns a task ID that can be polled for status.
    """
    task_id = _schedule_ingest(
        source, path_or_repo, "Task scheduled in background thread."
    )
    return (
        f"Ingestion task scheduled successfully. Task ID: {task_id}. "
        "You can check status with the `/ingest/{task_id}` endpoint or let the user know."
    )


@tool
def sync_knowledge_base() -> str:
    """
    Manually triggers a full synchronization of the local knowledge base (raw/local directory).
    Use this when the user asks to sync, update, or refresh the knowledge base manually.
    Returns a task ID that can be polled for status.
    """
    task_id = _schedule_ingest(
        "local",
        "raw/local",
        "Manual knowledge base sync scheduled in background thread.",
    )
    return f"Manual knowledge base synchronization started. Task ID: {task_id}. You can track status with this ID."
