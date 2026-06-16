# Fix for engineio packet limit error ("Too many packets in payload")
try:
    from engineio.payload import Payload

    Payload.max_decode_packets = 2048
except ImportError:
    pass

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from chainlit.utils import mount_chainlit

from app.api.lifespan import lifespan
from app.api.routers import chat, ingest, graph, cost, health, elements

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router)
app.include_router(ingest.router)
app.include_router(graph.router)
app.include_router(cost.router)
app.include_router(health.router)
app.include_router(elements.router)

mount_chainlit(app=app, target="app.py", path="/chat")
