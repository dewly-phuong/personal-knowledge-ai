"""
Contextvars-based retrieval accumulator.

Lets callers (e.g. eval model_callback) collect retrieval chunks for a
single agent.invoke() call without deepeval tracing.
"""

import contextvars
from typing import List

# Per-invocation accumulators
_retrieval_accumulator: contextvars.ContextVar[list | None] = contextvars.ContextVar(
    "retrieval_accumulator", default=None
)
_current_upload_session: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "current_upload_session", default=None
)
_current_upload_ids: contextvars.ContextVar[list[str] | None] = contextvars.ContextVar(
    "current_upload_ids", default=None
)


def start_retrieval_capture() -> None:
    """Reset and activate the per-invocation retrieval accumulator."""
    _retrieval_accumulator.set([])


def pop_retrieval_capture() -> List[str]:
    """Return accumulated retrieval chunks and deactivate the accumulator."""
    chunks = _retrieval_accumulator.get() or []
    _retrieval_accumulator.set(None)
    return chunks


def set_current_upload_session(session_id: str | None, token=None):
    """Set/reset the session used by uploaded_file_context during one agent run."""
    if token is not None:
        _current_upload_session.reset(token)
        return None
    return _current_upload_session.set(session_id)


def get_current_upload_session() -> str | None:
    return _current_upload_session.get()


def set_current_upload_ids(upload_ids: list[str] | None, token=None):
    """Set/reset upload ids used by retrieval sources during one agent run."""
    if token is not None:
        _current_upload_ids.reset(token)
        return None
    return _current_upload_ids.set(upload_ids)


def get_current_upload_ids() -> list[str] | None:
    return _current_upload_ids.get()


def register_retrieval(chunks: List[str]) -> None:
    """Append retrieval chunks to the active deepeval trace and/or local accumulator."""
    acc = _retrieval_accumulator.get()
    if acc is not None:
        acc.extend(chunks)
    try:
        from deepeval.tracing.tracing import current_trace_context
        from deepeval.tracing import update_current_trace

        trace = current_trace_context.get()
        if trace is not None:
            existing = getattr(trace, "retrieval_context", None) or []
            update_current_trace(retrieval_context=existing + chunks)
    except Exception:
        pass
