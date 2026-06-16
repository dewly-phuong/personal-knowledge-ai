"""
Chart pipeline diagnostic tests.
Run with: uv run python test_chart_pipeline.py

Tests each layer independently:
  [1] generate_chart tool returns correct CHART_JSON: prefix
  [2] ToolMessage content extraction (the on_tool_end fix in main.py)
  [3] plotly JSON round-trip (to_json -> from_json)
  [4] cl.Plotly element can be constructed from the chart JSON
  [5] Live SSE endpoint emits a 'chart' event when asked for a chart
"""

import asyncio
import json
import sys

PASS = "\033[92m[PASS]\033[0m"
FAIL = "\033[91m[FAIL]\033[0m"
INFO = "\033[94m[INFO]\033[0m"


# ---------------------------------------------------------------------------
# Test 1: generate_chart tool direct invocation
# ---------------------------------------------------------------------------
def test_generate_chart_tool():
    print("\n=== Test 1: generate_chart tool direct output ===")
    from app.tools import generate_chart

    result = generate_chart.invoke({
        "chart_type": "pie",
        "title": "Test Chart",
        "labels": ["A", "B", "C"],
        "values": [10.0, 20.0, 30.0],
    })

    print(f"  Raw output (first 120 chars): {str(result)[:120]}")

    if isinstance(result, str) and result.startswith("CHART_JSON:"):
        print(f"{PASS} Tool returned CHART_JSON: prefix")
        return result
    else:
        print(f"{FAIL} Expected 'CHART_JSON:' prefix, got: {type(result)} → {str(result)[:200]}")
        return None


# ---------------------------------------------------------------------------
# Test 2: ToolMessage content extraction (simulate on_tool_end)
# ---------------------------------------------------------------------------
def test_tool_message_extraction(raw_tool_output: str):
    print("\n=== Test 2: ToolMessage content extraction ===")
    from langchain_core.messages import ToolMessage

    # Simulate what LangGraph puts in event["data"]["output"]
    wrapped = ToolMessage(content=raw_tool_output, name="generate_chart", tool_call_id="test-id")
    print(f"  str(ToolMessage) starts with CHART_JSON: {str(wrapped).startswith('CHART_JSON:')}")

    # Apply the extraction logic from main.py
    if hasattr(wrapped, "content"):
        extracted = str(wrapped.content)
    else:
        extracted = str(wrapped)

    if extracted.startswith("CHART_JSON:"):
        print(f"{PASS} Content extraction works — starts with CHART_JSON:")
        return extracted
    else:
        print(f"{FAIL} Extraction failed. Got: {extracted[:200]}")
        return None


# ---------------------------------------------------------------------------
# Test 3: Plotly JSON round-trip
# ---------------------------------------------------------------------------
def test_plotly_roundtrip(chart_output: str):
    print("\n=== Test 3: Plotly JSON round-trip (to_json → from_json) ===")
    import plotly.io as pio

    chart_json = chart_output[len("CHART_JSON:"):]
    try:
        fig = pio.from_json(chart_json)
        title = fig.layout.title.text if fig.layout.title.text else "(no title)"
        traces = len(fig.data)
        print(f"  Reconstructed figure: title='{title}', traces={traces}")
        print(f"{PASS} plotly round-trip works")
        return fig
    except Exception as e:
        print(f"{FAIL} pio.from_json failed: {e}")
        return None


# ---------------------------------------------------------------------------
# Test 4: cl.Plotly element construction
# ---------------------------------------------------------------------------
def test_chainlit_element(fig):
    print("\n=== Test 4: cl.Plotly element construction ===")
    try:
        import chainlit as cl
        element = cl.Plotly(name="chart", figure=fig, display="inline", size="large")
        print(f"  Element type: {type(element).__name__}, name={element.name}")
        print(f"{PASS} cl.Plotly element constructed successfully")
        return True
    except Exception as e:
        print(f"{FAIL} cl.Plotly construction failed: {e}")
        return False


# ---------------------------------------------------------------------------
# Test 5: Live SSE endpoint emits chart event
# ---------------------------------------------------------------------------
async def test_live_sse_endpoint():
    print("\n=== Test 5: Live /api/chat SSE endpoint ===")
    print(f"  {INFO} Sending chart request to http://localhost:8000/api/chat ...")
    try:
        import httpx
        payload = {
            "query": "vẽ biểu đồ tròn chi phí hạ tầng tháng 9/2024 theo service_category",
            "session_id": "test-chart-debug",
        }
        events_received = []
        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream("POST", "http://localhost:8000/api/chat", json=payload) as resp:
                if resp.status_code != 200:
                    print(f"{FAIL} HTTP {resp.status_code}")
                    return

                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        try:
                            data = json.loads(line[6:])
                            dtype = data.get("type")
                            events_received.append(dtype)
                            if dtype == "step_start":
                                print(f"  → tool_start: {data.get('name')}")
                            elif dtype == "step_end":
                                out = data.get("output", "")[:80]
                                print(f"  → tool_end output: {out}")
                            elif dtype == "chart":
                                cj = data.get("chart_json", "")
                                print(f"  → chart event received! JSON length: {len(cj)} chars")
                                print(f"{PASS} Chart SSE event emitted by backend")
                            elif dtype == "done":
                                break
                            elif dtype == "error":
                                print(f"{FAIL} Agent error: {data.get('error')}")
                        except Exception:
                            pass

        if "chart" not in events_received:
            print(f"{FAIL} No 'chart' SSE event received. Events seen: {events_received}")
        else:
            print(f"{PASS} End-to-end SSE pipeline works")

    except httpx.ConnectError:
        print(f"  {INFO} Server not running — skipping live test (start with: uv run uvicorn main:app)")
    except Exception as e:
        print(f"{FAIL} Unexpected error: {e}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("=" * 60)
    print("  Chart Pipeline Diagnostic")
    print("=" * 60)

    # Tests 1-4 are unit tests (no server needed)
    tool_output = test_generate_chart_tool()
    if tool_output is None:
        print("\n[STOP] Tool is broken — fix generate_chart first")
        sys.exit(1)

    extracted = test_tool_message_extraction(tool_output)
    if extracted is None:
        print("\n[STOP] ToolMessage extraction is broken — fix main.py on_tool_end handler")
        sys.exit(1)

    fig = test_plotly_roundtrip(extracted)
    if fig is None:
        print("\n[STOP] Plotly round-trip broken — check plotly installation")
        sys.exit(1)

    test_chainlit_element(fig)

    # Test 5 requires the server to be running
    asyncio.run(test_live_sse_endpoint())

    print("\n" + "=" * 60)
    print("  Diagnostic complete")
    print("=" * 60)
