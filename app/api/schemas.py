from typing import List, Dict
from pydantic import BaseModel


class ChatRequest(BaseModel):
    query: str
    session_id: str


class SyncHistoryRequest(BaseModel):
    messages: List[Dict[str, str]]


class IngestRequest(BaseModel):
    source: str
    path_or_repo: str
