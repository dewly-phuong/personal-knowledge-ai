from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from app.services.upload_artifacts import (
    get_artifact,
    list_artifacts,
)

router = APIRouter(prefix="/api/uploads", tags=["uploads"])


@router.get("")
async def list_uploaded_artifacts(
    limit: int = Query(default=50, ge=1, le=200),
    status: str | None = None,
):
    """List uploaded files retained as chat-session context."""
    return {"artifacts": list_artifacts(limit=limit, status=status)}


@router.get("/{upload_id}/file")
async def serve_uploaded_artifact_file(upload_id: str):
    """Serve a processed uploaded file retained as chat-session context."""
    artifact = get_artifact(upload_id)
    if not artifact or artifact.get("status") != "processed":
        raise HTTPException(status_code=404, detail="Uploaded artifact not found.")
    processed_path = artifact.get("processed_path")
    if not processed_path:
        raise HTTPException(status_code=404, detail="Processed file not found.")
    try:
        with open(processed_path, "rb") as f:
            content = f.read()
    except OSError:
        raise HTTPException(status_code=404, detail="Processed file not found.")
    return Response(
        content=content,
        media_type="text/markdown",
        headers={
            "Content-Disposition": (
                f'inline; filename="{artifact.get("original_filename", upload_id)}.processed.md"'
            )
        },
    )


@router.get("/{upload_id}")
async def get_uploaded_artifact(upload_id: str):
    """Return detailed metadata for one uploaded artifact."""
    artifact = get_artifact(upload_id)
    if not artifact:
        raise HTTPException(status_code=404, detail="Uploaded artifact not found.")
    return artifact
