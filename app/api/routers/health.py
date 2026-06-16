import datetime

from fastapi import APIRouter, Request

router = APIRouter(prefix="/api/health", tags=["health"])


@router.get("")
async def health_check(req: Request):
    """Returns Redis and MongoDB connectivity status."""
    store = req.app.state.session_store
    mongo_ok = await store.ping_mongo()
    redis_ok = await store.ping_redis()
    return {
        "status": "ok" if (mongo_ok and redis_ok) else "degraded",
        "fastapi": "ok",
        "redis": "connected" if redis_ok else "disconnected",
        "mongodb": "connected" if mongo_ok else "disconnected",
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
