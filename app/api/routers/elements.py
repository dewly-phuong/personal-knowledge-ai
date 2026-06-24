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


@router.get("/{element_id}/file")
async def serve_file_element(element_id: str):
    """Serves persisted Chainlit file content for a given element ID."""
    client = AsyncIOMotorClient(os.getenv("MONGO_URI", "mongodb://localhost:27017/"))
    doc = await client["personal_knowledge_ai"]["cl_elements"].find_one(
        {"id": element_id}
    )
    content = doc.get("_file_content") if doc else None
    if content is None:
        raise HTTPException(status_code=404, detail="File element content not found")
    return Response(
        content=bytes(content),
        media_type=doc.get("_file_mime")
        or doc.get("mime")
        or "application/octet-stream",
        headers={
            "Content-Disposition": f'inline; filename="{doc.get("name", "file")}"'
        },
    )
