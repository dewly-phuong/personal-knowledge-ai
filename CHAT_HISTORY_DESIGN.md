# Conversation History — Implementation Plan

> **Mục tiêu:** Thêm conversation memory vào agent chatbot hiện tại (FastAPI + Chainlit + LangChain).
> Lưu trữ: Redis (RAM, TTL 24h) + Postgres (persistent backup).
> Interface: Chainlit web UI.
> Pattern: `RunnableWithMessageHistory` + Summary Buffer Memory.

---

## Tổng quan kiến trúc

```
Chainlit UI (browser tab)
    │
    │  session_id = cl.context.session.id (per tab)
    ▼
FastAPI POST /chat
    │
    ├─► [READ]  Redis → lấy history gần nhất (hot, < 1ms)
    │           key: "session:{session_id}"
    │           value: list of LangChain messages (JSON)
    │           TTL: 86400s (24h)
    │
    ├─► [READ]  Postgres → fallback nếu Redis miss (cold start / restart)
    │           table: chat_history
    │
    ├─► [RUN]   LangChain Agent với history inject vào prompt
    │           strategy: Summary Buffer (tóm tắt cũ, giữ 3 turns gần)
    │
    └─► [WRITE] Redis + Postgres đồng thời sau mỗi turn
```

---

## Cấu trúc file thêm mới

```
app/
├── memory/
│   ├── __init__.py
│   ├── session_store.py      # Redis + Postgres read/write
│   ├── history_manager.py    # RunnableWithMessageHistory wrapper
│   └── summary_buffer.py     # Summary Buffer Memory logic
├── db/
│   ├── vector_store.py       # (đã có)
│   ├── graph_store.py        # (đã có)
│   └── chat_history.py       # Postgres schema + CRUD  ← NEW
chainlit_app.py               # cập nhật on_chat_start, on_message, on_chat_resume
.env                          # thêm REDIS_URL
requirements.txt              # thêm redis, langchain-postgres
```

---

## Dependencies

```bash
pip install redis langchain-community langchain-postgres hiredis
```

Thêm vào `pyproject.toml` hoặc `requirements.txt`:
```
redis>=5.0.0
hiredis>=2.3.0          # C parser, tăng tốc Redis serialization
langchain-community>=0.2.0
langchain-postgres>=0.0.9
```

---

## Biến môi trường

Thêm vào `.env`:
```bash
REDIS_URL=redis://localhost:6379/0
# Postgres đã có DATABASE_URL từ trước — dùng lại
```

---

## Bước 1 — Postgres schema

**File:** `app/db/chat_history.py`

```python
"""
Postgres table để backup conversation history.
Dùng langchain_postgres.PostgresChatMessageHistory.
"""

import psycopg
from langchain_postgres import PostgresChatMessageHistory


def create_chat_history_table(conn_string: str) -> None:
    """
    Tạo bảng chat_history nếu chưa tồn tại.
    Gọi một lần khi khởi động app (trong lifespan FastAPI).
    
    Schema tự động tạo bởi langchain_postgres:
        CREATE TABLE IF NOT EXISTS chat_history (
            id          SERIAL PRIMARY KEY,
            session_id  TEXT NOT NULL,
            message     JSONB NOT NULL,
            created_at  TIMESTAMPTZ DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_chat_history_session 
            ON chat_history (session_id);
    """
    sync_conn = psycopg.connect(conn_string)
    PostgresChatMessageHistory.create_tables(sync_conn, "chat_history")
    sync_conn.close()


def get_postgres_history(session_id: str, conn_string: str) -> PostgresChatMessageHistory:
    """
    Trả về PostgresChatMessageHistory cho một session.
    Dùng làm fallback khi Redis miss.
    """
    return PostgresChatMessageHistory(
        table_name="chat_history",
        session_id=session_id,
        connection=conn_string,
    )
```

---

## Bước 2 — Session Store (Redis + Postgres)

**File:** `app/memory/session_store.py`

```python
"""
Đọc/ghi conversation history.
Redis = hot cache (nhanh, TTL 24h).
Postgres = cold backup (persistent qua restart).

Quy tắc:
- Read:  Redis trước → miss → Postgres → seed Redis
- Write: Redis + Postgres đồng thời (fire-and-forget Postgres)
"""

import json
import asyncio
import logging
from typing import Optional

import redis.asyncio as aioredis
from langchain_core.messages import BaseMessage, messages_from_dict, messages_to_dict
from langchain_postgres import PostgresChatMessageHistory

logger = logging.getLogger(__name__)

REDIS_TTL = 86400        # 24 giờ
REDIS_KEY  = "session:{session_id}"


class SessionStore:
    def __init__(self, redis_url: str, pg_conn_string: str):
        self.redis = aioredis.from_url(redis_url, decode_responses=True)
        self.pg_conn = pg_conn_string

    # ── READ ──────────────────────────────────────────────────────────────

    async def load(self, session_id: str) -> list[BaseMessage]:
        """
        Load history cho session.
        1. Thử Redis trước.
        2. Nếu miss → load Postgres → seed Redis.
        """
        key = REDIS_KEY.format(session_id=session_id)

        # 1. Redis
        raw = await self.redis.get(key)
        if raw:
            try:
                return messages_from_dict(json.loads(raw))
            except Exception:
                logger.warning("Redis parse error for %s, falling back to Postgres", session_id)

        # 2. Postgres fallback
        messages = self._load_postgres(session_id)
        if messages:
            await self._seed_redis(key, messages)
        return messages

    def _load_postgres(self, session_id: str) -> list[BaseMessage]:
        """Đọc từ Postgres (sync — chạy trong thread pool)."""
        try:
            pg = PostgresChatMessageHistory(
                table_name="chat_history",
                session_id=session_id,
                connection=self.pg_conn,
            )
            return pg.messages
        except Exception as e:
            logger.error("Postgres load error: %s", e)
            return []

    async def _seed_redis(self, key: str, messages: list[BaseMessage]) -> None:
        """Ghi messages vào Redis với TTL (sau khi Postgres hit)."""
        try:
            await self.redis.set(
                key,
                json.dumps(messages_to_dict(messages)),
                ex=REDIS_TTL,
            )
        except Exception as e:
            logger.warning("Redis seed error: %s", e)

    # ── WRITE ─────────────────────────────────────────────────────────────

    async def save(self, session_id: str, messages: list[BaseMessage]) -> None:
        """
        Ghi history sau mỗi turn.
        Redis: await (cần ngay cho turn tiếp theo).
        Postgres: fire-and-forget (không block response).
        """
        key = REDIS_KEY.format(session_id=session_id)

        # Redis — await
        await self.redis.set(
            key,
            json.dumps(messages_to_dict(messages)),
            ex=REDIS_TTL,
        )

        # Postgres — fire and forget
        asyncio.create_task(self._save_postgres(session_id, messages))

    async def _save_postgres(self, session_id: str, messages: list[BaseMessage]) -> None:
        """Ghi vào Postgres trong background task."""
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._sync_save_postgres, session_id, messages)
        except Exception as e:
            logger.error("Postgres save error for %s: %s", session_id, e)

    def _sync_save_postgres(self, session_id: str, messages: list[BaseMessage]) -> None:
        pg = PostgresChatMessageHistory(
            table_name="chat_history",
            session_id=session_id,
            connection=self.pg_conn,
        )
        pg.clear()
        pg.add_messages(messages)

    # ── UTILS ─────────────────────────────────────────────────────────────

    async def clear(self, session_id: str) -> None:
        """Xóa history của session (user bấm New Chat)."""
        key = REDIS_KEY.format(session_id=session_id)
        await self.redis.delete(key)
        asyncio.create_task(self._clear_postgres(session_id))

    async def _clear_postgres(self, session_id: str) -> None:
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, lambda: PostgresChatMessageHistory(
                table_name="chat_history",
                session_id=session_id,
                connection=self.pg_conn,
            ).clear())
        except Exception as e:
            logger.error("Postgres clear error: %s", e)
```

---

## Bước 3 — Summary Buffer Memory

**File:** `app/memory/summary_buffer.py`

```python
"""
Quản lý context window cho agent.
Strategy: Summary Buffer
  - Giữ full content của N turns gần nhất (default: 3)
  - Tóm tắt tất cả turns cũ hơn thành 1 đoạn summary
  - Inject vào prompt: [summary] + [3 turns gần]
  
Tại sao không dùng ConversationSummaryBufferMemory của LangChain trực tiếp?
Vì ta cần full control để kết hợp với Redis/Postgres store.
"""

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

SUMMARY_PROMPT = """Tóm tắt ngắn gọn cuộc hội thoại dưới đây thành 2-3 câu.
Giữ lại: các entities quan trọng được hỏi (service, pipeline, người), 
các quyết định hoặc thông tin đã xác nhận, context cần thiết cho câu hỏi tiếp theo.
Bỏ qua: các câu hỏi không liên quan, small talk.

Hội thoại:
{conversation}

Tóm tắt:"""

MAX_RECENT_TURNS = 3          # số turns giữ full
MAX_TOKENS_BEFORE_SUMMARY = 800  # token threshold để trigger tóm tắt


async def compress_history(
    messages: list[BaseMessage],
    llm: ChatGoogleGenerativeAI,
    max_recent: int = MAX_RECENT_TURNS,
) -> list[BaseMessage]:
    """
    Nhận toàn bộ history, trả về compressed version:
    [SystemMessage(summary)] + [3 turns gần nhất]
    
    Nếu history ngắn (≤ max_recent turns), trả về nguyên.
    """
    # Tách human/ai pairs thành turns
    turns = _to_turns(messages)

    if len(turns) <= max_recent:
        # Chưa đủ dài để cần tóm tắt
        return messages

    old_turns  = turns[:-max_recent]
    recent_turns = turns[-max_recent:]

    # Tóm tắt phần cũ
    conversation_text = "\n".join(
        f"User: {t['human']}\nAssistant: {t['ai']}"
        for t in old_turns
    )
    summary_response = await llm.ainvoke(
        SUMMARY_PROMPT.format(conversation=conversation_text)
    )
    summary_text = summary_response.content

    # Assemble: SystemMessage(summary) + recent messages
    compressed = [SystemMessage(content=f"[Tóm tắt hội thoại trước]: {summary_text}")]
    for turn in recent_turns:
        compressed.append(HumanMessage(content=turn["human"]))
        compressed.append(AIMessage(content=turn["ai"]))

    return compressed


def _to_turns(messages: list[BaseMessage]) -> list[dict]:
    """Convert flat message list thành list of {human, ai} pairs."""
    turns = []
    i = 0
    while i < len(messages):
        if isinstance(messages[i], HumanMessage):
            human_text = messages[i].content
            ai_text = messages[i + 1].content if i + 1 < len(messages) and isinstance(messages[i + 1], AIMessage) else ""
            turns.append({"human": human_text, "ai": ai_text})
            i += 2
        else:
            i += 1
    return turns
```

---

## Bước 4 — History Manager (kết nối tất cả)

**File:** `app/memory/history_manager.py`

```python
"""
Orchestrate toàn bộ memory flow:
  load → compress → inject vào agent → save

Đây là interface duy nhất mà FastAPI và Chainlit gọi vào.
"""

from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from app.memory.session_store import SessionStore
from app.memory.summary_buffer import compress_history


class HistoryManager:
    def __init__(self, store: SessionStore, llm: ChatGoogleGenerativeAI):
        self.store = store
        self.llm   = llm

    async def get_context(self, session_id: str) -> list[BaseMessage]:
        """
        Load + compress history cho session.
        Trả về list messages để inject vào agent prompt.
        """
        raw_history = await self.store.load(session_id)
        if not raw_history:
            return []
        return await compress_history(raw_history, self.llm)

    async def append_turn(
        self,
        session_id: str,
        user_message: str,
        assistant_message: str,
    ) -> None:
        """
        Append một turn (user + assistant) vào history rồi save.
        Gọi sau khi agent đã trả lời xong.
        """
        raw_history = await self.store.load(session_id)
        raw_history.append(HumanMessage(content=user_message))
        raw_history.append(AIMessage(content=assistant_message))
        await self.store.save(session_id, raw_history)

    async def clear(self, session_id: str) -> None:
        """Xóa history (user bấm New Chat)."""
        await self.store.clear(session_id)
```

---

## Bước 5 — Cập nhật FastAPI `/chat`

**File:** `app/main.py` — phần liên quan

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import StreamingResponse

from app.memory.session_store import SessionStore
from app.memory.history_manager import HistoryManager
from app.db.chat_history import create_chat_history_table
from app.agent import build_agent
import os

# ── Khởi tạo shared instances ──────────────────────────────────────────

store: SessionStore = None
history_manager: HistoryManager = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Chạy một lần khi app start."""
    global store, history_manager

    # Tạo Postgres table nếu chưa có
    create_chat_history_table(os.environ["DATABASE_URL"])

    # Khởi tạo store và manager
    store = SessionStore(
        redis_url=os.environ["REDIS_URL"],
        pg_conn_string=os.environ["DATABASE_URL"],
    )
    llm = build_llm()  # ChatGoogleGenerativeAI instance
    history_manager = HistoryManager(store=store, llm=llm)

    yield  # app chạy ở đây

    # Cleanup (nếu cần)
    await store.redis.aclose()


app = FastAPI(lifespan=lifespan)


# ── POST /chat ─────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    query: str
    session_id: str   # Chainlit truyền cl.context.session.id
    stream: bool = True

@app.post("/chat")
async def chat(req: ChatRequest):
    # 1. Load compressed history
    chat_history = await history_manager.get_context(req.session_id)

    # 2. Gọi agent với history
    agent = build_agent(chat_history=chat_history)

    if req.stream:
        return StreamingResponse(
            _stream_agent(agent, req.query, req.session_id),
            media_type="text/event-stream",
        )
    else:
        result = await agent.ainvoke({"input": req.query})
        answer = result["output"]
        await history_manager.append_turn(req.session_id, req.query, answer)
        return {"answer": answer}


async def _stream_agent(agent, query: str, session_id: str):
    """Stream tokens, collect full response, sau đó save history."""
    full_response = []
    async for event in agent.astream_events({"input": query}, version="v1"):
        if event["event"] == "on_chat_model_stream":
            chunk = event["data"]["chunk"].content
            if chunk:
                full_response.append(chunk)
                yield f"data: {chunk}\n\n"

    # Save sau khi stream xong
    answer = "".join(full_response)
    await history_manager.append_turn(session_id, query, answer)
    yield "data: [DONE]\n\n"


# ── DELETE /chat/{session_id} — clear history ──────────────────────────

@app.delete("/chat/{session_id}")
async def clear_history(session_id: str):
    await history_manager.clear(session_id)
    return {"status": "cleared"}
```

---

## Bước 6 — Cập nhật Agent

**File:** `app/agent.py` — phần liên quan

```python
from langchain_core.messages import BaseMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

def build_agent(chat_history: list[BaseMessage] = None):
    """
    Build LangChain agent với history inject vào prompt.
    chat_history: compressed history từ HistoryManager.
    """
    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),          # system prompt tiếng Việt (từ plan.md)
        MessagesPlaceholder("chat_history"), # ← inject history vào đây
        ("human", "{input}"),
        MessagesPlaceholder("agent_scratchpad"),
    ])

    agent = create_tool_calling_agent(llm, tools, prompt)
    executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

    # Bind history vào executor
    return executor.with_config(
        configurable={"chat_history": chat_history or []}
    )

    # Hoặc đơn giản hơn: truyền trực tiếp khi invoke
    # executor.ainvoke({"input": query, "chat_history": chat_history or []})
```

---

## Bước 7 — Cập nhật Chainlit

**File:** `chainlit_app.py`

```python
import chainlit as cl
import httpx
import os

API_BASE = os.environ.get("API_BASE_URL", "http://localhost:8000")


@cl.on_chat_start
async def on_start():
    """
    Mỗi lần mở tab mới → session mới.
    Lưu session_id vào cl.user_session để dùng xuyên suốt conversation.
    """
    session_id = cl.context.session.id
    cl.user_session.set("session_id", session_id)

    # Optional: load lại history cũ nếu muốn resume
    # (cần Chainlit data persistence được bật)
    await cl.Message(
        content="Xin chào! Tôi là trợ lý nội bộ. Hỏi tôi bất cứ điều gì về docs của team nhé."
    ).send()


@cl.on_message
async def on_message(message: cl.Message):
    session_id = cl.user_session.get("session_id")

    # Streaming response từ FastAPI
    response_msg = cl.Message(content="")
    await response_msg.send()

    async with httpx.AsyncClient(timeout=60.0) as client:
        async with client.stream(
            "POST",
            f"{API_BASE}/chat",
            json={
                "query": message.content,
                "session_id": session_id,
                "stream": True,
            },
        ) as resp:
            async for line in resp.aiter_lines():
                if line.startswith("data: ") and line != "data: [DONE]":
                    token = line[6:]  # bỏ "data: " prefix
                    await response_msg.stream_token(token)

    await response_msg.update()


@cl.on_chat_end
async def on_end():
    """
    Khi user đóng tab — history vẫn còn trong Redis (TTL 24h) và Postgres.
    Không cần làm gì thêm.
    """
    pass


@cl.action_callback("new_chat")
async def on_new_chat(action: cl.Action):
    """
    Nút 'New Chat' trong UI — xóa history session hiện tại.
    """
    session_id = cl.user_session.get("session_id")
    async with httpx.AsyncClient() as client:
        await client.delete(f"{API_BASE}/chat/{session_id}")

    await cl.Message(content="Đã xóa lịch sử. Bắt đầu cuộc hội thoại mới!").send()


# ── Optional: Resume session cũ ───────────────────────────────────────

@cl.on_chat_resume
async def on_resume(thread: cl.ThreadDict):
    """
    Khi user quay lại session cũ (cần Chainlit data persistence).
    Chainlit tự render lại messages trong thread.
    Chỉ cần restore session_id vào user_session.
    """
    session_id = thread.get("id", cl.context.session.id)
    cl.user_session.set("session_id", session_id)
```

---

## Thứ tự implement

| Ngày | Task | Verify bằng cách nào |
|---|---|---|
| 1 sáng | Cài deps, setup Redis local (`docker run -p 6379:6379 redis`), viết `chat_history.py`, chạy `create_chat_history_table` | Kiểm tra table tồn tại trong Postgres |
| 1 chiều | Viết `session_store.py`, viết unit test load/save/clear | `pytest tests/test_session_store.py` |
| 2 sáng | Viết `summary_buffer.py`, test với mock conversation 10 turns | In ra compressed history, kiểm tra summary hợp lý |
| 2 chiều | Viết `history_manager.py`, integrate vào FastAPI `/chat` | `curl POST /chat` 3 lần liên tiếp, message sau refer được message trước |
| 3 sáng | Cập nhật `agent.py` với `MessagesPlaceholder` | Agent trả lời "bạn vừa hỏi về X" đúng |
| 3 chiều | Cập nhật `chainlit_app.py`, test streaming + session | Mở 2 tab, verify 2 sessions độc lập |
| 4 | Test edge cases + regression | Xem checklist bên dưới |

---

## Test cases

### Unit tests

```python
# tests/test_session_store.py

import pytest
from app.memory.session_store import SessionStore

@pytest.mark.asyncio
async def test_load_empty_session(store: SessionStore):
    """Session mới phải trả về list rỗng."""
    result = await store.load("new-session-xyz")
    assert result == []

@pytest.mark.asyncio
async def test_save_and_load(store: SessionStore):
    """Save rồi load lại phải khớp."""
    from langchain_core.messages import HumanMessage, AIMessage
    messages = [HumanMessage(content="hello"), AIMessage(content="hi")]
    await store.save("test-session", messages)
    loaded = await store.load("test-session")
    assert len(loaded) == 2
    assert loaded[0].content == "hello"

@pytest.mark.asyncio
async def test_redis_miss_falls_back_to_postgres(store: SessionStore, redis):
    """Xóa Redis key → load phải fallback về Postgres."""
    await store.save("fallback-session", [HumanMessage(content="test")])
    await redis.delete("session:fallback-session")  # Simulate Redis miss
    loaded = await store.load("fallback-session")
    assert len(loaded) == 1

@pytest.mark.asyncio
async def test_clear(store: SessionStore):
    """Clear phải xóa cả Redis lẫn Postgres."""
    await store.save("clear-session", [HumanMessage(content="x")])
    await store.clear("clear-session")
    loaded = await store.load("clear-session")
    assert loaded == []
```

### Integration tests (manual)

```
1. Multi-turn follow-up
   Turn 1: "service TrainingPipeline làm gì?"
   Turn 2: "nó depend vào gì?"          ← "nó" phải resolve được là TrainingPipeline
   Turn 3: "ai own cái đó?"             ← "cái đó" = dependency từ turn 2
   Expected: agent trả lời đúng xuyên suốt

2. Session isolation
   Mở 2 tab Chainlit cùng lúc
   Tab A hỏi về ServiceX
   Tab B hỏi về ServiceY
   Kiểm tra: Tab A không bị nhiễm context từ Tab B

3. Redis restart recovery
   Chat 3 turns
   Restart Redis (docker restart)
   Chat turn 4
   Expected: history vẫn còn (load từ Postgres)

4. Summary trigger
   Chat hơn 3 turns liên tiếp
   Kiểm tra log: summary được generate khi turns > MAX_RECENT_TURNS
   Turn tiếp theo vẫn coherent với context cũ

5. New Chat button
   Chat 5 turns
   Bấm New Chat
   Hỏi "bạn vừa hỏi gì?"
   Expected: agent không biết — history đã clear
```

---

## Edge cases cần xử lý

| Edge case | Hành vi mong muốn |
|---|---|
| Redis down | Fallback Postgres, log warning, không crash |
| Postgres down | Chỉ dùng Redis, log error, tiếp tục hoạt động |
| Cả hai down | Trả về history rỗng, agent vẫn trả lời được (stateless) |
| Session không tồn tại | Trả về `[]`, bắt đầu fresh |
| Message rất dài (> 4000 chars) | Summary buffer tóm tắt trước khi save |
| Concurrent requests cùng session | Redis atomic SET — last write wins, chấp nhận được |
| Tab reload | Session ID mới → fresh start (expected behavior) |

---

## Checklist trước khi ship

- [ ] Unit tests `test_session_store.py` pass 100%
- [ ] Manual test multi-turn follow-up: "nó", "cái đó" resolve đúng
- [ ] Manual test 2 tabs: sessions hoàn toàn độc lập
- [ ] Manual test Redis restart: history không mất
- [ ] Summary được trigger đúng khi > 3 turns
- [ ] New Chat button xóa history thành công
- [ ] Không có session_id nào bị hardcode
- [ ] Redis TTL = 86400s đã set đúng (verify bằng `TTL session:{id}`)
- [ ] Postgres table `chat_history` có index trên `session_id`
- [ ] Streaming vẫn hoạt động sau khi thêm history
- [ ] Regression test 10 câu từ Sprint 3 vẫn pass