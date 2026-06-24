import json
import os
import pickle

from app.visualizer_html import render_graph_html


def _graph_payload(graph) -> dict:
    nodes = [
        {
            "id": node,
            "type": data.get("type", "CONCEPT"),
            "description": data.get("description", ""),
            "aliases": data.get("aliases", []),
            "source_docs": data.get("source_docs", []),
        }
        for node, data in graph.nodes(data=True)
    ]
    links = [
        {
            "source": source,
            "target": target,
            "predicate": data.get("predicate", ""),
            "source_doc": data.get("source_doc", ""),
        }
        for source, target, _, data in graph.edges(keys=True, data=True)
    ]
    return {"nodes": nodes, "links": links}


def main():
    graph_path = "graph/graph.pkl"
    output_path = "graph/visualizer.html"
    if not os.path.exists(graph_path):
        print(f"Error: {graph_path} not found. Please run ingestion first.")
        return

    print(f"Loading knowledge graph from {graph_path}...")
    with open(graph_path, "rb") as f:
        graph = pickle.load(f)
    print(
        f"Graph loaded: {graph.number_of_nodes()} nodes, "
        f"{graph.number_of_edges()} edges."
    )

    graph_json = json.dumps(_graph_payload(graph), indent=2)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(render_graph_html(graph_json))

    print(
        "\nSuccess! Open this file in your browser to view the interactive graph:\n"
        f"file://{os.path.abspath(output_path)}"
    )


if __name__ == "__main__":
    main()
