import os
import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI
from apscheduler.schedulers.background import BackgroundScheduler

from app.services.graph_store import GraphStore
from app.core.redis import get_redis_client
from app.memory.session_store import SessionStore
from app.memory.history_manager import HistoryManager


def scheduled_sync_and_lint() -> None:
    """Daily background job: re-ingests raw/local and saves a wiki health report."""
    print(
        f"\n--- [Scheduled Job] Starting daily Sync & Lint ({datetime.datetime.now()}) ---"
    )
    try:
        from ingest import run_ingest_pipeline
        from app.tools.admin import lint_wiki

        run_ingest_pipeline(source="local", dir_path="raw/local")
        report = lint_wiki.invoke({})

        os.makedirs("wiki", exist_ok=True)
        with open("wiki/health_report.md", "w", encoding="utf-8") as f:
            f.write(report)

        print(
            "[Scheduled Job] Sync & Lint completed. Health report saved to wiki/health_report.md."
        )
    except Exception as e:
        print(f"[Scheduled Job] Error: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan — runs startup tasks before yield, teardown after."""
    print("\n--- FastAPI Lifespan Startup ---")

    app.state.graph_store = GraphStore()
    print(
        f"Knowledge Graph loaded. "
        f"Nodes: {len(app.state.graph_store.graph.nodes)}, "
        f"Edges: {len(app.state.graph_store.graph.edges)}"
    )

    try:
        get_redis_client().ping()
        print("Connected to Redis successfully.")
    except Exception as e:
        print(f"Warning: Failed to connect to Redis: {e}")

    app.state.session_store = SessionStore()
    app.state.history_manager = HistoryManager(store=app.state.session_store)
    print("SessionStore and HistoryManager initialized.")

    scheduler = BackgroundScheduler()
    scheduler.add_job(scheduled_sync_and_lint, "interval", hours=24)
    scheduler.start()
    app.state.scheduler = scheduler
    print("Daily Scheduler started.")

    print("--------------------------------\n")
    yield

    print("\n--- FastAPI Lifespan Shutdown ---")
    if hasattr(app.state, "scheduler"):
        app.state.scheduler.shutdown()
        print("Scheduler shut down.")
    if hasattr(app.state, "session_store"):
        await app.state.session_store.flush()
        app.state.session_store.close()
        print("Session store flushed and closed.")
