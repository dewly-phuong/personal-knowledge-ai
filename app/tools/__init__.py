"""
app.tools package — re-exports every public tool and helper so existing
import paths continue to work unchanged.
"""

from app.tools.retrieval_context import (
    start_retrieval_capture,
    pop_retrieval_capture,
    set_current_upload_session,
    get_current_upload_session,
    register_retrieval,
)
from app.tools.search import (
    wiki_search,
    entity_search,
    graph_traverse,
    uploaded_file_context,
)
from app.tools.mongodb import mongodb_query
from app.tools.ingest import ingest_source, sync_knowledge_base, _schedule_ingest
from app.tools.admin import lint_wiki
from app.tools.chart import generate_chart

__all__ = [
    # retrieval context
    "start_retrieval_capture",
    "pop_retrieval_capture",
    "set_current_upload_session",
    "get_current_upload_session",
    "register_retrieval",
    # search
    "wiki_search",
    "entity_search",
    "graph_traverse",
    "uploaded_file_context",
    # mongodb
    "mongodb_query",
    # ingest
    "ingest_source",
    "sync_knowledge_base",
    "_schedule_ingest",
    # admin
    "lint_wiki",
    # chart
    "generate_chart",
]
