from fastapi import APIRouter, HTTPException

from app.services.cost_tracker import CostTracker

router = APIRouter(prefix="/api/cost", tags=["cost"])

_cost_tracker = CostTracker()


@router.get("")
async def get_cost_stats():
    """Retrieves accumulated LLM API costs for today and the current month."""
    try:
        return _cost_tracker.get_stats()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error accessing cost stats: {e}")
