from fastapi import APIRouter

from app.services.graph_store import GraphStore

router = APIRouter(prefix="/api/graph", tags=["graph"])


@router.get("/{entity}")
async def get_entity_graph(entity: str):
    """Returns the 2-hop neighborhood of a given entity as a JSON node/edge graph."""
    return GraphStore().get_subgraph(entity, hops=2)
