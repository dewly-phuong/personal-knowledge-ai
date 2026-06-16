"""
Chart pipeline diagnostic tests.
Run with: uv run python test_chart_pipeline.py

Tests each layer independently:
  [1] generate_chart tool returns correct CHART_JSON: prefix
  [2] ToolMessage content extraction (the on_tool_end fix in main.py)
  [3] plotly JSON round-trip (to_json -> from_json)
  [4] cl.Plotly element can be constructed (needs Chainlit context, expected to fail in script)
  [5] Live SSE endpoint emits a 'chart' event
  [6] LLM bind_tools — does the model actually call a tool?   <-- ROOT CAUSE CHECK
  [7] Full agent astream_events — what event types does it emit?
"""

import asyncio
import json
import os
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

    wrapped = ToolMessage(content=raw_tool_output, name="generate_chart", tool_call_id="test-id")
    print(f"  str(ToolMessage) starts with CHART_JSON: {str(wrapped).startswith('CHART_JSON:')}")

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
# Test 4: cl.Plotly element construction (needs Chainlit context)
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
        if "context" in str(e).lower():
            print(f"  {INFO} Skipped — Chainlit context only exists inside the running app (expected)")
        else:
            print(f"{FAIL} cl.Plotly construction failed: {e}")
        return False


# ---------------------------------------------------------------------------
# Test 6: bind_tools — does the LLM actually produce a tool call?
# ---------------------------------------------------------------------------
def test_bind_tools():
    print("\n=== Test 6: LLM bind_tools + single invocation (streaming=False) ===")
    from dotenv import load_dotenv
    from langchain_google_genai import ChatGoogleGenerativeAI
    from app.tools import mongodb_query, generate_chart

    load_dotenv()
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-pro",
        temperature=1,
        google_api_key=os.getenv("GOOGLE_API_KEY"),
        streaming=False,
    )

    tools = [mongodb_query, generate_chart]
    llm_with_tools = llm.bind_tools(tools)

    prompt = (
        "Truy vấn collection 'infrastructure_costs_sep2024' với filter {} "
        "và giới hạn 3 bản ghi. Dùng tool mongodb_query."
    )
    print(f"  Prompt: {prompt}")
    try:
        response = llm_with_tools.invoke(prompt)
        print(f"  Response type     : {type(response).__name__}")
        print(f"  tool_calls        : {response.tool_calls}")
        print(f"  content (first 200): {str(response.content)[:200]}")

        if response.tool_calls:
            print(f"{PASS} Model produced tool_calls: {[t['name'] for t in response.tool_calls]}")
            return True
        else:
            print(f"{FAIL} Model answered with plain text — tools are NOT being called")
            print(f"  {INFO} Root cause: check system prompt, Headroom wrapping, or model config")
            return False
    except Exception as e:
        print(f"{FAIL} bind_tools invocation failed: {e}")
        return False


# ---------------------------------------------------------------------------
# Test 7: Full agent astream_events — raw event types
# ---------------------------------------------------------------------------
async def test_agent_events():
    print("\n=== Test 7: Full agent astream_events (raw event types) ===")
    from langchain_core.messages import HumanMessage
    from app.agent import create_conversational_agent

    agent = create_conversational_agent(temperature=1)
    query = "chi phí hạ tầng tháng 9/2024 là bao nhiêu? hãy dùng tool mongodb_query để trả lời"

    event_kinds = []
    tool_calls_seen = []
    print(f"  Query: {query}")
    try:
        async for event in agent.astream_events(
            {"messages": [HumanMessage(content=query)]},
            version="v2",
        ):
            kind = event.get("event")
            event_kinds.append(kind)

            if kind == "on_tool_start":
                name = event.get("name", "?")
                tool_calls_seen.append(name)
                print(f"  → on_tool_start : {name}")
            elif kind == "on_tool_end":
                print(f"  → on_tool_end   : {event.get('name', '?')}")
            elif kind == "on_chat_model_end":
                resp = event.get("data", {}).get("output")
                if resp:
                    tc = getattr(resp, "tool_calls", [])
                    if tc:
                        print(f"  → model tool_calls in response: {[t['name'] for t in tc]}")

    except Exception as e:
        print(f"{FAIL} Agent stream error: {e}")
        return

    unique = sorted(set(event_kinds))
    print(f"  Unique event kinds seen: {unique}")
    if tool_calls_seen:
        print(f"{PASS} Agent called tools: {tool_calls_seen}")
    else:
        print(f"{FAIL} Agent called NO tools — only text generated")
        print(f"  {INFO} Event counts: { {k: event_kinds.count(k) for k in unique} }")


# ---------------------------------------------------------------------------
# Test 8: Agent WITHOUT HeadroomChatModel — isolate Headroom as root cause
# ---------------------------------------------------------------------------
async def test_agent_without_headroom():
    print("\n=== Test 8: Agent astream_events WITHOUT HeadroomChatModel ===")
    import os
    from dotenv import load_dotenv
    from langchain_google_genai import ChatGoogleGenerativeAI
    from langchain.agents import create_agent
    from langchain_core.messages import HumanMessage
    from app.tools import mongodb_query, generate_chart
    from app.agent import SYSTEM_PROMPT

    load_dotenv()
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-pro",
        temperature=1,
        google_api_key=os.getenv("GOOGLE_API_KEY"),
        streaming=False,
    )
    tools = [mongodb_query, generate_chart]
    agent = create_agent(model=llm, tools=tools, system_prompt=SYSTEM_PROMPT)

    query = "chi phí hạ tầng tháng 9/2024 là bao nhiêu? hãy dùng tool mongodb_query"
    event_kinds = []
    tool_calls_seen = []
    print(f"  Query: {query}")
    try:
        async for event in agent.astream_events(
            {"messages": [HumanMessage(content=query)]},
            version="v2",
        ):
            kind = event.get("event")
            event_kinds.append(kind)
            if kind == "on_tool_start":
                name = event.get("name", "?")
                tool_calls_seen.append(name)
                print(f"  → on_tool_start : {name}")
            elif kind == "on_tool_end":
                print(f"  → on_tool_end   : {event.get('name', '?')}")
    except Exception as e:
        print(f"{FAIL} Agent stream error: {e}")
        return

    unique = sorted(set(event_kinds))
    print(f"  Unique event kinds seen: {unique}")
    if tool_calls_seen:
        print(f"{PASS} Without Headroom, agent called tools: {tool_calls_seen}")
        print(f"  {INFO} CONFIRMED: HeadroomChatModel is the root cause — it breaks bind_tools")
    else:
        print(f"{FAIL} Still no tool calls even without Headroom")
        print(f"  {INFO} Root cause is elsewhere (system prompt or create_agent config)")


# ---------------------------------------------------------------------------
# Test 5: Live SSE endpoint
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
                                print(f"  → tool_end output: {data.get('output', '')[:80]}")
                            elif dtype == "chart":
                                cj = data.get("chart_json", "")
                                print(f"  → chart event! JSON length: {len(cj)} chars")
                                print(f"{PASS} Chart SSE event emitted")
                            elif dtype == "done":
                                break
                            elif dtype == "error":
                                print(f"{FAIL} Agent error: {data.get('error')}")
                        except Exception:
                            pass

        unique = sorted(set(events_received))
        print(f"  Event types seen: {unique}")
        if "chart" not in events_received:
            print(f"{FAIL} No 'chart' SSE event received")
        else:
            print(f"{PASS} End-to-end SSE pipeline works")

    except httpx.ConnectError:
        print(f"  {INFO} Server not running — skipping (start with: uv run uvicorn main:app)")
    except Exception as e:
        print(f"{FAIL} Unexpected error: {e}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("=" * 60)
    print("  Chart Pipeline Diagnostic")
    print("=" * 60)

    tool_output = test_generate_chart_tool()
    if tool_output is None:
        sys.exit(1)

    extracted = test_tool_message_extraction(tool_output)
    if extracted is None:
        sys.exit(1)

    fig = test_plotly_roundtrip(extracted)
    if fig is None:
        sys.exit(1)

    test_chainlit_element(fig)

    # These call the Google API — need GOOGLE_API_KEY in .env
    test_bind_tools()
    asyncio.run(test_agent_events())
    asyncio.run(test_agent_without_headroom())

    # Requires running server
    asyncio.run(test_live_sse_endpoint())

    print("\n" + "=" * 60)
    print("  Diagnostic complete")
    print("=" * 60)
