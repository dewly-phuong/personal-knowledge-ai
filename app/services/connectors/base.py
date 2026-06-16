from abc import ABC, abstractmethod
from typing import Literal
from pydantic import BaseModel


class Document(BaseModel):
    content: str
    source_url: str
    path: str
    source_type: Literal["github", "confluence", "local"]
    last_modified: str


class BaseConnector(ABC):
    @abstractmethod
    def fetch_documents(self) -> list[Document]:
        """Fetch all documents from the source."""
        pass
