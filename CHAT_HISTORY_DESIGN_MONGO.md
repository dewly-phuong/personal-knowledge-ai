# Chat History Memory System Design (MongoDB + Redis)

This document describes the design and implementation plan for the persistent chat memory system for the LangChain Knowledge Graph Agent.

## 📋 Understanding Summary
*   **What is being built:** A persistent chat history memory system for the LangChain agent. It uses a dual-layer storage architecture: **Redis** as a hot cache (TTL 24 hours) and **MongoDB** as a cold backup.
*   **Why it exists:** To allow the assistant to remember context over multi-turn conversations in Chainlit, ensuring efficient token usage (via a Summary Buffer) and session persistence across backend restarts.
*   **Who it is for:** Engineering team members querying the Internal Doc Q&A system.
*   **Key constraints:**
    *   **Decoupled Architecture:** Chainlit remains decoupled from FastAPI. Chainlit tracks the session using the connection/session ID and queries the `/api/chat` FastAPI endpoint.
    *   **Graceful Degradation:** If Redis or MongoDB is offline, the system must log a warning but degrade gracefully (using in-memory list or stateless memory) without crashing.
    *   **Non-blocking I/O:** MongoDB operations must use `motor` (the async driver) so as not to block FastAPI's asyncio event loop.
    *   **Summary Buffer Strategy:** Retain the full text of the last 3 turns, and summarize older turns into a single system block.

## 🔍 Assumptions
1.  **Database Configuration:** MongoDB connection details are retrieved from `MONGO_URI` in `.env` (already pointing to `mongodb://localhost:27017/`).
2.  **Schema Names:** We will use database `personal_knowledge_ai` and collection `chat_history`.
3.  **Serialization:** Messages are stored using standard LangChain message serialization format (`messages_to_dict` / `messages_from_dict`) to easily preserve roles, tool calls, and metadata.
4.  **Redis Connection:** The existing Redis helper in `app/core/redis.py` will be reused/extended to support caching.

## 📝 Decision Log
*   **Backup Database: MongoDB** — Decided over PostgreSQL (`langchain-postgres`) because the user already has a running MongoDB container configured via `MONGO_URI` in `.env`.
*   **MongoDB Client: Motor** — Decided over synchronous `pymongo` to prevent blocking FastAPI's single-threaded async event loop.
*   **Session Identification: Chainlit ID** — Decided over persistent user-level IDs or custom UUIDs because it integrates cleanly with the standard Chainlit session lifecycle.
*   **Serialization: `messages_to_dict`** — Decided over custom role/content schema to natively preserve system messages, agent tool calls, and metadata without custom parser code.
*   **Architecture: Decoupled Service** — Decided over extending `BaseChatMessageHistory` subclass to give clean control over async flow and graceful degradation if DBs fail.

---

## 🛠️ Architecture & Component Design

```
Chainlit UI (browser tab)
    │
    │  session_id = cl.context.session.id (per tab)
    ▼
FastAPI POST /api/chat
    │
    ├─► [READ]  Redis → session:{session_id} (< 1ms)
    │           (fallback if cache miss: MongoDB → personal_knowledge_ai.chat_history)
    │
    ├─► [COMPRESS] SummaryBuffer → Summarizes turns > 3 using gemini-2.0-flash
    │
    ├─► [RUN]   AgentExecutor with history injected into "chat_history"
    │
    └─► [WRITE] Redis (awaited) + MongoDB (asynchronous task) after turn completes
```

### 1. File Structure

```
app/
├── core/
│   └── redis.py              # (Existing) Redis singleton
├── memory/
│   ├── __init__.py
│   ├── session_store.py      # Dual-layer store (Redis + Motor)
│   ├── summary_buffer.py     # Custom summary buffer context compressor
│   └── history_manager.py    # Orchestrator wrapping store + summarizer
main.py                       # Update lifespan and POST /api/chat
app.py                        # Update Chainlit session start, on_message, and clear
pyproject.toml                # Add motor dependency
```

### 2. File Specifications

#### `app/memory/session_store.py`
Manages read/write caching and storage operations.
*   Uses `motor.motor_asyncio.AsyncIOMotorClient` for MongoDB.
*   Uses `messages_to_dict` and `messages_from_dict` for serialization.
*   Enforces a 24-hour cache TTL in Redis.
*   Catches all DB exceptions and degrades gracefully.

#### `app/memory/summary_buffer.py`
Truncates history and summarizes older conversations:
*   Counts human/AI dialogue turns.
*   Extracts anything older than the last 3 turns and formats it as text.
*   Calls `gemini-2.0-flash` to summarize the old text in Vietnamese.
*   Assembles `[SystemMessage(summary)] + recent_turns` messages.

#### `app/memory/history_manager.py`
Orchestrates the interaction between `SessionStore` and `summary_buffer`:
*   `get_context(session_id: str) -> List[BaseMessage]`: retrieves and compresses history.
*   `append_turn(session_id: str, query: str, answer: str)`: saves raw turn to store.
*   `clear(session_id: str)`: purges history from Redis and MongoDB.
