import os
import pickle
from typing import Dict, Any, List
import networkx as nx
from app.models.graph import Entity, Relation


class GraphStore:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(GraphStore, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, file_path: str = "graph/graph.pkl"):
        if getattr(self, "_initialized", False):
            return
        self.file_path = file_path
        self.graph = self._load_graph()
        self._initialized = True

    def _load_graph(self) -> nx.MultiDiGraph:
        """Loads NetworkX graph from pickle, or creates a new MultiDiGraph if none exists."""
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, "rb") as f:
                    g = pickle.load(f)
                    if isinstance(g, nx.MultiDiGraph):
                        return g
            except Exception as e:
                print(
                    f"Error loading graph from {self.file_path}: {e}. Initializing new graph."
                )

        # Ensure parent folder exists
        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
        return nx.MultiDiGraph()

    def save(self):
        """Serializes the graph back to disk."""
        # Ensure parent folder exists
        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
        try:
            with open(self.file_path, "wb") as f:
                pickle.dump(self.graph, f)
        except Exception as e:
            print(f"Error saving graph to {self.file_path}: {e}")

    def add_entities_and_relations(
        self,
        entities: List[Entity],
        relations: List[Relation],
        alias_map: Dict[str, str],
        source_doc_url: str,
    ):
        """
        Merges new entities and relations into the MultiDiGraph.
        Resolves entity names to canonical names using alias_map.
        """
        # 1. Add/Update Nodes
        for entity in entities:
            canonical_name = alias_map.get(entity.name, entity.name)

            # Retrieve existing node attributes if any
            if self.graph.has_node(canonical_name):
                node_attrs = self.graph.nodes[canonical_name]

                # Update descriptions (append/merge if different)
                desc = node_attrs.get("description", "")
                if entity.description and entity.description not in desc:
                    # Keep description clean, merge if helpful
                    node_attrs["description"] = f"{desc} / {entity.description}".lstrip(
                        " / "
                    )

                # Add aliases
                aliases = set(node_attrs.get("aliases", []))
                aliases.add(entity.name)
                node_attrs["aliases"] = list(aliases)

                # Add source doc URL
                source_docs = set(node_attrs.get("source_docs", []))
                source_docs.add(source_doc_url)
                node_attrs["source_docs"] = list(source_docs)
            else:
                self.graph.add_node(
                    canonical_name,
                    type=entity.type,
                    description=entity.description,
                    aliases=[entity.name],
                    source_docs=[source_doc_url],
                )

        # 2. Add/Update Edges
        for rel in relations:
            canonical_source = alias_map.get(rel.source, rel.source)
            canonical_target = alias_map.get(rel.target, rel.target)

            # Check if this edge already exists
            edge_exists = False
            if self.graph.has_edge(canonical_source, canonical_target):
                # Check if edge with exact predicate and source doc exists
                for key, edge_data in self.graph[canonical_source][
                    canonical_target
                ].items():
                    if (
                        edge_data.get("predicate") == rel.predicate
                        and edge_data.get("source_doc") == source_doc_url
                    ):
                        edge_exists = True
                        break

            if not edge_exists:
                self.graph.add_edge(
                    canonical_source,
                    canonical_target,
                    predicate=rel.predicate.lower().strip(),
                    source_doc=source_doc_url,
                )

    def get_subgraph(self, entity_name: str, hops: int = 2) -> Dict[str, Any]:
        """
        Retrieves a subgraph centered around the target entity name up to N hops.
        Format is ready for frontend serialization.
        """
        if not self.graph.has_node(entity_name):
            return {"nodes": [], "edges": []}

        # Use networkx ego_graph or single_source_shortest_path_length to get neighborhood
        undirected = self.graph.to_undirected()
        try:
            lengths = nx.single_source_shortest_path_length(
                undirected, entity_name, cutoff=hops
            )
            nodes_in_subgraph = list(lengths.keys())
        except Exception:
            nodes_in_subgraph = [entity_name]

        sub_g = self.graph.subgraph(nodes_in_subgraph)

        nodes_list = []
        for n, data in sub_g.nodes(data=True):
            nodes_list.append(
                {
                    "id": n,
                    "type": data.get("type", "CONCEPT"),
                    "label": n,
                    "description": data.get("description", ""),
                }
            )

        edges_list = []
        for u, v, key, data in sub_g.edges(keys=True, data=True):
            edges_list.append(
                {
                    "source": u,
                    "target": v,
                    "predicate": data.get("predicate", ""),
                    "source_doc": data.get("source_doc", ""),
                }
            )

        return {"nodes": nodes_list, "edges": edges_list}
