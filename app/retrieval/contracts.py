from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal, Protocol


@dataclass(slots=True)
class SearchContext:
    session_id: str | None = None
    upload_ids: list[str] | None = None
    limit: int = 100
    timeout_seconds: float = 8.0


@dataclass(slots=True)
class SourceResult:
    source: str
    status: Literal["ok", "empty", "error"]
    data: Any | None
    summary: str
    metadata: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    @classmethod
    def ok(
        cls,
        source: str,
        data: Any,
        summary: str,
        metadata: dict[str, Any] | None = None,
    ) -> "SourceResult":
        return cls(
            source=source,
            status="ok",
            data=data,
            summary=summary,
            metadata=metadata or {},
        )

    @classmethod
    def empty(
        cls,
        source: str,
        summary: str,
        metadata: dict[str, Any] | None = None,
    ) -> "SourceResult":
        return cls(
            source=source,
            status="empty",
            data=None,
            summary=summary,
            metadata=metadata or {},
        )

    @classmethod
    def error_result(
        cls,
        source: str,
        summary: str,
        error: str,
        metadata: dict[str, Any] | None = None,
    ) -> "SourceResult":
        return cls(
            source=source,
            status="error",
            data=None,
            summary=summary,
            metadata=metadata or {},
            error=error,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class SearchBundle:
    query: str
    results: list[SourceResult]

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "results": [result.to_dict() for result in self.results],
        }


class KnowledgeSource(Protocol):
    name: str

    async def search(self, query: str, context: SearchContext) -> SourceResult:
        ...
