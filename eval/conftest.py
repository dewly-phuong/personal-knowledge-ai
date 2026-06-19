"""
pytest conftest for eval/ — adds project root to sys.path and saves a
pass/fail summary to eval/result/ after each session.
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest
from deepeval.tracing.tracing import Observer, TraceManager, trace_manager
from deepeval.tracing.types import EvalMode, EvalSession
from deepeval.constants import PYTEST_TRACE_TEST_WRAPPER_SPAN_NAME

# ---------------------------------------------------------------------------
# Monkey-patch: Gemini streaming returns content blocks (list) per token
# interval, but BaseApiSpan.token_intervals expects Dict[str, str].
# Coerce list → str by joining text fields before pydantic validation hits.
# ---------------------------------------------------------------------------
_orig_convert = TraceManager._convert_span_to_api_span


def _patched_convert(self, span):
    if getattr(span, "token_intervals", None):
        fixed = {}
        for k, v in span.token_intervals.items():
            if isinstance(v, list):
                fixed[k] = "".join(
                    b.get("text", "") if isinstance(b, dict) else str(b)
                    for b in v
                )
            else:
                fixed[k] = v
        span.token_intervals = fixed
    return _orig_convert(self, span)


TraceManager._convert_span_to_api_span = _patched_convert

# Increase per-attempt timeout — 5 metrics × async_mode=False can exceed 180s
os.environ.setdefault("DEEPEVAL_PER_ATTEMPT_TIMEOUT_SECONDS_OVERRIDE", "600")

_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

RESULT_DIR = Path(__file__).parent / "result"


@pytest.fixture(autouse=True)
def _deepeval_trace_scope(request):
    """Replicate the deepeval pytest plugin's Observer wrapper.

    Only active for single-turn tests (assert_test(golden=...)).
    Multi-turn uses ConversationalTestCase and doesn't need the trace scope.
    """
    if "test_single_turn" not in request.node.nodeid:
        yield
        return

    prev_session = trace_manager.eval_session
    trace_manager.eval_session = EvalSession(mode=EvalMode.EVALUATE)
    observer = Observer("custom", func_name=PYTEST_TRACE_TEST_WRAPPER_SPAN_NAME)
    observer.__enter__()
    try:
        yield
    finally:
        try:
            observer.__exit__(None, None, None)
        finally:
            trace_manager.eval_session = prev_session


def serialize_deepeval_object(obj):
    """Safely serialize Pydantic models to a dict structure."""
    if hasattr(obj, "model_dump"):
        try:
            return obj.model_dump()
        except Exception:
            pass
    if hasattr(obj, "dict"):
        try:
            return obj.dict()
        except Exception:
            pass
    try:
        return str(obj)
    except Exception:
        return None


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    from deepeval.test_run.test_run import global_test_run_manager
    if call.when == "setup":
        try:
            tr = global_test_run_manager.get_test_run()
            item._initial_tc_count = len(tr.test_cases)
            item._initial_ctc_count = len(tr.conversational_test_cases)
        except Exception:
            item._initial_tc_count = 0
            item._initial_ctc_count = 0

    outcome = yield
    rep = outcome.get_result()
    if rep.when == "call":
        item._report = rep
        try:
            tr = global_test_run_manager.get_test_run()
            initial_tc_count = getattr(item, "_initial_tc_count", 0)
            initial_ctc_count = getattr(item, "_initial_ctc_count", 0)
            new_tcs = tr.test_cases[initial_tc_count:]
            new_ctcs = tr.conversational_test_cases[initial_ctc_count:]
            if new_tcs:
                item._deepeval_test_cases = getattr(item, "_deepeval_test_cases", []) + new_tcs
            if new_ctcs:
                item._deepeval_conversational_test_cases = getattr(item, "_deepeval_conversational_test_cases", []) + new_ctcs
        except Exception:
            pass


def pytest_sessionfinish(session, exitstatus):
    RESULT_DIR.mkdir(parents=True, exist_ok=True)

    results: dict[str, list] = {"single_turn": [], "multi_turn": []}

    for item in session.items:
        rep = getattr(item, "_report", None)
        if rep is None:
            continue
        bucket = "multi_turn" if "MT" in item.nodeid else "single_turn"
        
        deepeval_cases = []
        tcs = getattr(item, "_deepeval_test_cases", [])
        ctcs = getattr(item, "_deepeval_conversational_test_cases", [])
        
        for tc in tcs:
            serialized = serialize_deepeval_object(tc)
            if serialized:
                deepeval_cases.append(serialized)
        for ctc in ctcs:
            serialized = serialize_deepeval_object(ctc)
            if serialized:
                deepeval_cases.append(serialized)

        record = {
            "id": item.nodeid.split("::")[-1],
            "outcome": rep.outcome,
            "duration_s": round(rep.duration, 2),
            "error": str(rep.longrepr)[:500] if rep.failed else None,
        }
        if deepeval_cases:
            record["deepeval_test_cases"] = deepeval_cases

        results[bucket].append(record)

    ts = datetime.now(timezone.utc).isoformat()
    for key, records in results.items():
        if not records:
            continue
        path = RESULT_DIR / f"{key}_results.json"
        path.write_text(
            json.dumps(
                {"generated_at": ts, "count": len(records), "results": records},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"\n[eval] Saved {len(records)} results → {path}")

