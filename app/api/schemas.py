from typing import List, Dict
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    query: str
    session_id: str
    upload_ids: List[str] = Field(default_factory=list)


class SyncHistoryRequest(BaseModel):
    messages: List[Dict[str, str]]


class IngestRequest(BaseModel):
    source: str
    path_or_repo: str
