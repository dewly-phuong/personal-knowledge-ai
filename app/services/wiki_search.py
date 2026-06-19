import os
import re
import json
import logging
from typing import Dict, List, Optional, Tuple

from rank_bm25 import BM25Okapi
from qdrant_client import QdrantClient

from app.core.redis import get_redis_client
from app.services.embedding import get_embedding_service

logger = logging.getLogger(__name__)

_CACHE_KEY = "wiki:cache"
_CACHE_TTL = 3600  # 1 hour

# Module-level singletons — built once, reused across all queries
_qdrant_client: Optional[QdrantClient] = None
_bm25_index: Optional[BM25Okapi] = None
_bm25_paths: List[str] = []
_bm25_docs_key: Optional[str] = None  # tracks which docs the index was built from


def _tokenize(text: str) -> List[str]:
    return re.findall(r"\w+", text.lower())


def _get_qdrant_client() -> Optional[QdrantClient]:
    global _qdrant_client
    if _qdrant_client is None:
        url = os.getenv("QDRANT_URL")
        key = os.getenv("QDRANT_API_KEY")
        if url and key:
            _qdrant_client = QdrantClient(url=url, api_key=key)
    return _qdrant_client


class WikiSearchService:
    """Hybrid BM25 + Qdrant vector search over compiled wiki pages."""

    def __init__(self, wiki_dir: str = "wiki"):
        self.wiki_dir = wiki_dir

    # ── Data loading ──────────────────────────────────────────────────────

    def _load_docs(self) -> Dict[str, str]:
        """Returns all wiki pages as {path: content}, cached in Redis for 1 hour."""
        r = get_redis_client()
        try:
            cached = r.get(_CACHE_KEY)
            if cached:
                return json.loads(cached)
        except Exception as e:
            logger.warning("WikiSearchService: Redis read failed: %s", e)

        docs: Dict[str, str] = {}
        if os.path.exists(self.wiki_dir):
            for root, _, files in os.walk(self.wiki_dir):
                for fname in files:
                    if fname.endswith(".md") and fname not in ("log.md", "index.md"):
                        fpath = os.path.join(root, fname)
                        try:
                            with open(fpath, "r", encoding="utf-8") as f:
                                docs[fpath] = f.read()
                        except Exception:
                            pass
        try:
            r.setex(_CACHE_KEY, _CACHE_TTL, json.dumps(docs))
        except Exception as e:
            logger.warning("WikiSearchService: Redis write failed: %s", e)
        return docs

    # ── Ranking strategies ────────────────────────────────────────────────

    def _bm25_rank(self, docs: Dict[str, str], query: str) -> List[str]:
        global _bm25_index, _bm25_paths, _bm25_docs_key
        # Cache key = frozenset of paths; rebuild only when docs change
        current_key = str(sorted(docs.keys()))
        if _bm25_index is None or _bm25_docs_key != current_key:
            _bm25_paths = list(docs.keys())
            corpus = [_tokenize(text) for text in docs.values()]
            _bm25_index = BM25Okapi(corpus)
            _bm25_docs_key = current_key
        scores = _bm25_index.get_scores(_tokenize(query))
        ranked = sorted(zip(_bm25_paths, scores), key=lambda x: x[1], reverse=True)
        return [p for p, s in ranked if s > 0]

    def _qdrant_rank(self, query: str) -> List[str]:
        client = _get_qdrant_client()
        if not client:
            return []
        try:
            vec = get_embedding_service().embed_text(query)
            res = client.query_points(collection_name="wiki_pages", query=vec, limit=10)
            return [
                hit.payload["path"]
                for hit in res.points
                if hit.payload and "path" in hit.payload
            ]
        except Exception as e:
            logger.warning("WikiSearchService: Qdrant search failed: %s", e)
            return []

    def _rrf(self, *rankings: List[str], k: int = 60) -> List[Tuple[str, float]]:
        """Reciprocal Rank Fusion — merges multiple ranked lists into one."""
        scores: Dict[str, float] = {}
        for ranking in rankings:
            for rank, path in enumerate(ranking):
                norm = os.path.normpath(path)
                scores[norm] = scores.get(norm, 0.0) + 1.0 / (k + rank + 1)
        return sorted(scores.items(), key=lambda x: x[1], reverse=True)

    # ── Snippet extraction ────────────────────────────────────────────────

    def _snippet(self, content: str, query: str) -> str:
        matches = list(re.finditer(re.escape(query), content, re.IGNORECASE))
        if matches:
            start = max(0, matches[0].start() - 100)
            end = min(len(content), matches[0].end() + 150)
            snippet = content[start:end].strip()
            if start > 0:
                snippet = "..." + snippet
            if end < len(content):
                snippet += "..."
            return snippet

        body = content
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                body = parts[2].strip()
        return body[:2000].strip() + ("..." if len(body) > 2000 else "")

    # ── Public API ────────────────────────────────────────────────────────

    def search(self, query: str, top_k: int = 5) -> str:
        """Returns the top-k wiki snippets as a formatted string for the agent."""
        docs = self._load_docs()
        if not docs:
            return "No wiki pages found."

        fused = self._rrf(self._bm25_rank(docs, query), self._qdrant_rank(query))[
            :top_k
        ]
        if not fused:
            fused = [(os.path.normpath(p), 0.0) for p in list(docs.keys())[:top_k]]

        norm_to_orig = {os.path.normpath(p): p for p in docs}
        results = []
        for rank, (norm_path, score) in enumerate(fused):
            orig = norm_to_orig.get(norm_path)
            if not orig:
                continue
            results.append(
                f"[{rank + 1}] {os.path.basename(orig)}\n"
                f"{self._snippet(docs[orig], query)}"
            )
        return "\n\n".join(results) if results else "No matches found."


def invalidate_wiki_cache() -> None:
    """Call after ingestion to force BM25 index rebuild on next query."""
    global _bm25_index, _bm25_docs_key
    _bm25_index = None
    _bm25_docs_key = None
    try:
        get_redis_client().delete(_CACHE_KEY)
    except Exception:
        pass
