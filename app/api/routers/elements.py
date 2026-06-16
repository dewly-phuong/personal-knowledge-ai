import os

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from motor.motor_asyncio import AsyncIOMotorClient

router = APIRouter(prefix="/api/elements", tags=["elements"])


@router.get("/{element_id}/plotly")
async def serve_plotly_element(element_id: str):
    """Serves persisted Plotly figure JSON for a given element ID."""
    client = AsyncIOMotorClient(os.getenv("MONGO_URI", "mongodb://localhost:27017/"))
    doc = await client["personal_knowledge_ai"]["cl_elements"].find_one(
        {"id": element_id}
    )
    if not doc or not doc.get("_plotly_content"):
        raise HTTPException(status_code=404, detail="Plotly element content not found")
    return Response(content=doc["_plotly_content"], media_type="application/json")
