from __future__ import annotations

import asyncio
from collections.abc import Iterable

from app.retrieval.contracts import (
    KnowledgeSource,
    SearchBundle,
    SearchContext,
    SourceResult,
)


class KnowledgeSourceRegistry:
    def __init__(self, sources: Iterable[KnowledgeSource]):
        self._sources = list(sources)

    @property
    def sources(self) -> list[KnowledgeSource]:
        return list(self._sources)

    async def search_all(self, query: str, context: SearchContext) -> SearchBundle:
        results = await asyncio.gather(
            *(self._search_one(source, query, context) for source in self._sources)
        )
        return SearchBundle(query=query, results=list(results))

    async def _search_one(
        self, source: KnowledgeSource, query: str, context: SearchContext
    ) -> SourceResult:
        try:
            return await asyncio.wait_for(
                source.search(query, context), timeout=context.timeout_seconds
            )
        except TimeoutError:
            return SourceResult.error_result(
                source=source.name,
                summary="Source timed out.",
                error="timeout",
                metadata={"timeout_seconds": context.timeout_seconds},
            )
        except Exception as exc:
            return SourceResult.error_result(
                source=source.name,
                summary="Source failed.",
                error=str(exc),
            )
