import os
import pickle
import json


def main():
    graph_path = "graph/graph.pkl"
    output_path = "graph/visualizer.html"

    if not os.path.exists(graph_path):
        print(f"Error: {graph_path} not found. Please run ingestion first.")
        return

    print(f"Loading knowledge graph from {graph_path}...")
    with open(graph_path, "rb") as f:
        g = pickle.load(f)

    print(f"Graph loaded: {g.number_of_nodes()} nodes, {g.number_of_edges()} edges.")

    # 1. Convert to D3-friendly structure
    nodes = []
    for n, data in g.nodes(data=True):
        nodes.append(
            {
                "id": n,
                "type": data.get("type", "CONCEPT"),
                "description": data.get("description", ""),
                "aliases": data.get("aliases", []),
                "source_docs": data.get("source_docs", []),
            }
        )

    links = []
    for u, v, key, data in g.edges(keys=True, data=True):
        links.append(
            {
                "source": u,
                "target": v,
                "predicate": data.get("predicate", ""),
                "source_doc": data.get("source_doc", ""),
            }
        )

    graph_json = json.dumps({"nodes": nodes, "links": links}, indent=2)

    # 2. Standalone HTML template with D3.js
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Personal Knowledge AI - Graph Visualizer</title>
    <script src="https://d3js.org/d3.v7.min.js"></script>
    <style>
        body {{
            margin: 0;
            padding: 0;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: #0d1117;
            color: #c9d1d9;
            overflow: hidden;
        }}
        
        #header {{
            position: absolute;
            top: 20px;
            left: 20px;
            z-index: 10;
            background: rgba(22, 27, 34, 0.85);
            padding: 15px 25px;
            border-radius: 12px;
            border: 1px solid #30363d;
            box-shadow: 0 4px 12px rgba(0,0,0,0.5);
            backdrop-filter: blur(8px);
        }}
        
        h1 {{
            margin: 0 0 5px 0;
            font-size: 20px;
            color: #58a6ff;
            font-weight: 600;
        }}
        
        .subtitle {{
            margin: 0;
            font-size: 12px;
            color: #8b949e;
        }}
        
        #sidebar {{
            position: absolute;
            top: 20px;
            right: 20px;
            width: 300px;
            z-index: 10;
            background: rgba(22, 27, 34, 0.85);
            padding: 20px;
            border-radius: 12px;
            border: 1px solid #30363d;
            box-shadow: 0 4px 12px rgba(0,0,0,0.5);
            backdrop-filter: blur(8px);
            max-height: 80vh;
            overflow-y: auto;
        }}
        
        .section-title {{
            font-size: 14px;
            text-transform: uppercase;
            letter-spacing: 1px;
            color: #8b949e;
            border-bottom: 1px solid #21262d;
            padding-bottom: 5px;
            margin-top: 0;
            margin-bottom: 12px;
        }}
        
        .node-detail {{
            display: none;
        }}
        
        .node-name {{
            font-size: 18px;
            font-weight: bold;
            color: #f0f6fc;
            margin-bottom: 8px;
        }}
        
        .node-type {{
            display: inline-block;
            padding: 3px 8px;
            border-radius: 20px;
            font-size: 11px;
            font-weight: bold;
            text-transform: uppercase;
            margin-bottom: 15px;
        }}
        
        .type-service {{ background-color: #388bfd33; color: #58a6ff; border: 1px solid #388bfd66; }}
        .type-pipeline {{ background-color: #56d36433; color: #3fb950; border: 1px solid #56d36466; }}
        .type-concept {{ background-color: #bc8cff33; color: #d2a8ff; border: 1px solid #bc8cff66; }}
        .type-person {{ background-color: #e3b34133; color: #f2cc60; border: 1px solid #e3b34166; }}
        .type-database {{ background-color: #ff7b7233; color: #ff7b72; border: 1px solid #ff7b7266; }}
        .type-artifact {{ background-color: #79c0ff33; color: #79c0ff; border: 1px solid #79c0ff66; }}
        
        .label-text {{
            font-size: 12px;
            color: #8b949e;
            margin-bottom: 3px;
        }}
        
        .value-text {{
            font-size: 13px;
            color: #c9d1d9;
            margin-bottom: 15px;
            line-height: 1.4;
        }}
        
        .pill-list {{
            display: flex;
            flex-wrap: wrap;
            gap: 5px;
            margin-bottom: 15px;
        }}
        
        .pill {{
            background: #21262d;
            border: 1px solid #30363d;
            border-radius: 4px;
            padding: 2px 6px;
            font-size: 11px;
            color: #8b949e;
        }}
        
        .source-link {{
            display: block;
            font-size: 11px;
            color: #58a6ff;
            text-decoration: none;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            margin-bottom: 5px;
        }}
        
        .source-link:hover {{
            text-decoration: underline;
        }}
        
        svg {{
            width: 100vw;
            height: 100vh;
        }}
        
        .node {{
            stroke-width: 2px;
            cursor: pointer;
            transition: stroke-width 0.1s ease;
        }}
        
        .node:hover {{
            stroke-width: 4px;
            stroke: #fff !important;
        }}
        
        .link {{
            stroke-opacity: 0.6;
            stroke-width: 1.5px;
            fill: none;
        }}
        
        .edge-label {{
            fill: #8b949e;
            font-size: 10px;
            pointer-events: none;
        }}
        
        .node-label {{
            fill: #c9d1d9;
            font-size: 11px;
            pointer-events: none;
            text-shadow: 0 1px 4px rgba(0,0,0,0.8);
        }}
        
        /* Legends */
        #legend {{
            margin-top: 15px;
        }}
        .legend-item {{
            display: flex;
            align-items: center;
            margin-bottom: 6px;
            font-size: 12px;
        }}
        .legend-color {{
            width: 12px;
            height: 12px;
            border-radius: 50%;
            margin-right: 8px;
        }}
    </style>
</head>
<body>
    <div id="header">
        <h1>Personal Knowledge Graph</h1>
        <p class="subtitle" id="stats-summary"></p>
    </div>
    
    <div id="sidebar">
        <div id="empty-state">
            <h3 class="section-title">Knowledge Graph</h3>
            <p style="font-size: 13px; color: #8b949e; line-height: 1.5;">
                Click any node in the graph to view details, dependencies, description, and source links.
            </p>
            <div id="legend">
                <h4 class="section-title" style="margin-top: 20px;">Legend</h4>
                <div class="legend-item"><div class="legend-color" style="background-color: #58a6ff;"></div>Service</div>
                <div class="legend-item"><div class="legend-color" style="background-color: #3fb950;"></div>Pipeline</div>
                <div class="legend-item"><div class="legend-color" style="background-color: #d2a8ff;"></div>Concept</div>
                <div class="legend-item"><div class="legend-color" style="background-color: #ff7b72;"></div>Database</div>
                <div class="legend-item"><div class="legend-color" style="background-color: #79c0ff;"></div>Artifact</div>
                <div class="legend-item"><div class="legend-color" style="background-color: #f2cc60;"></div>Person</div>
            </div>
        </div>
        
        <div id="detail-pane" class="node-detail">
            <div class="node-name" id="det-name">canonical-entity</div>
            <div class="node-type" id="det-type">concept</div>
            
            <div class="label-text">Description</div>
            <div class="value-text" id="det-desc">No description available.</div>
            
            <div class="label-text">Aliases</div>
            <div class="pill-list" id="det-aliases"></div>
            
            <div class="label-text">Source Documents</div>
            <div id="det-docs"></div>
        </div>
    </div>
    
    <svg id="viz"></svg>
    
    <script>
        const data = {graph_json};
        
        document.getElementById('stats-summary').innerText = 
            `Total: ${{data.nodes.length}} nodes, ${{data.links.length}} edges`;
            
        const width = window.innerWidth;
        const height = window.innerHeight;
        
        const colors = {{
            "SERVICE": "#58a6ff",
            "PIPELINE": "#3fb950",
            "CONCEPT": "#d2a8ff",
            "PERSON": "#f2cc60",
            "DATABASE": "#ff7b72",
            "ARTIFACT": "#79c0ff"
        }};
        
        const defaultColor = "#bc8cff";
        
        const svg = d3.select("#viz");
        
        // Add zoom behavior
        const container = svg.append("g");
        svg.call(d3.zoom()
            .scaleExtent([0.1, 4])
            .on("zoom", (event) => {{
                container.attr("transform", event.transform);
            }}));
            
        // Setup markers for arrowheads
        svg.append("defs").selectAll("marker")
            .data(["suit"])
            .enter().append("marker")
            .attr("id", d => d)
            .attr("viewBox", "0 -5 10 10")
            .attr("refX", 22)
            .attr("refY", 0)
            .attr("markerWidth", 6)
            .attr("markerHeight", 6)
            .attr("orient", "auto")
            .append("path")
            .attr("d", "M0,-5L10,0L0,5")
            .attr("fill", "#30363d");

        // Force simulation
        const simulation = d3.forceSimulation(data.nodes)
            .force("link", d3.forceLink(data.links).id(d => d.id).distance(120))
            .force("charge", d3.forceManyBody().strength(-300))
            .force("center", d3.forceCenter(width / 2, height / 2))
            .force("collision", d3.forceCollide().radius(30));
            
        // Draw links
        const link = container.append("g")
            .attr("class", "links")
            .selectAll("path")
            .data(data.links)
            .enter().append("path")
            .attr("class", "link")
            .attr("stroke", "#30363d")
            .attr("marker-end", "url(#suit)");
            
        // Draw edge labels
        const edgeLabel = container.append("g")
            .selectAll("text")
            .data(data.links)
            .enter().append("text")
            .attr("class", "edge-label")
            .attr("text-anchor", "middle")
            .text(d => d.predicate);

        // Draw nodes
        const node = container.append("g")
            .attr("class", "nodes")
            .selectAll("circle")
            .data(data.nodes)
            .enter().append("circle")
            .attr("class", "node")
            .attr("r", d => d.type === "SERVICE" || d.type === "PIPELINE" ? 12 : 8)
            .attr("fill", d => colors[d.type] || defaultColor)
            .attr("stroke", "#0d1117")
            .on("click", (event, d) => showNodeDetails(d))
            .call(d3.drag()
                .on("start", dragstarted)
                .on("drag", dragged)
                .on("end", dragended));
                
        // Draw labels
        const label = container.append("g")
            .selectAll("text")
            .data(data.nodes)
            .enter().append("text")
            .attr("class", "node-label")
            .attr("dx", 15)
            .attr("dy", 4)
            .text(d => d.id);
            
        simulation.on("tick", () => {{
            link.attr("d", d => {{
                // Simple straight line path
                return `M${{d.source.x}},${{d.source.y}} L${{d.target.x}},${{d.target.y}}`;
            }});
            
            node
                .attr("cx", d => d.x)
                .attr("cy", d => d.y);
                
            label
                .attr("x", d => d.x)
                .attr("y", d => d.y);
                
            edgeLabel
                .attr("x", d => (d.source.x + d.target.x) / 2)
                .attr("y", d => (d.source.y + d.target.y) / 2 - 5);
        }});
        
        function showNodeDetails(d) {{
            document.getElementById('empty-state').style.display = 'none';
            
            const detailPane = document.getElementById('detail-pane');
            detailPane.style.display = 'block';
            
            document.getElementById('det-name').innerText = d.id;
            
            const typeBadge = document.getElementById('det-type');
            typeBadge.innerText = d.type;
            typeBadge.className = `node-type type-${{d.type.toLowerCase()}}`;
            
            document.getElementById('det-desc').innerText = d.description || "No description available.";
            
            const aliasesContainer = document.getElementById('det-aliases');
            aliasesContainer.innerHTML = '';
            if (d.aliases && d.aliases.length > 0) {{
                d.aliases.forEach(alias => {{
                    const pill = document.createElement('span');
                    pill.className = 'pill';
                    pill.innerText = alias;
                    aliasesContainer.appendChild(pill);
                }});
            }} else {{
                aliasesContainer.innerHTML = '<span class="subtitle">None</span>';
            }}
            
            const docsContainer = document.getElementById('det-docs');
            docsContainer.innerHTML = '';
            if (d.source_docs && d.source_docs.length > 0) {{
                d.source_docs.forEach(doc => {{
                    const link = document.createElement('a');
                    link.className = 'source-link';
                    link.href = doc;
                    link.target = '_blank';
                    
                    // Format pretty link text
                    let linkText = doc;
                    if (doc.startsWith('file://')) {{
                        linkText = doc.substring(doc.lastIndexOf('/') + 1);
                    }}
                    link.innerText = linkText;
                    docsContainer.appendChild(link);
                }});
            }} else {{
                docsContainer.innerHTML = '<span class="subtitle">None</span>';
            }}
        }}

        function dragstarted(event, d) {{
            if (!event.active) simulation.alphaTarget(0.3).restart();
            d.fx = d.x;
            d.fy = d.y;
        }}

        function dragged(event, d) {{
            d.fx = event.x;
            d.fy = event.y;
        }}

        function dragended(event, d) {{
            if (!event.active) simulation.alphaTarget(0);
            d.fx = null;
            d.fy = null;
        }}
    </script>
</body>
</html>
"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(
        f"\nSuccess! Open this file in your browser to view the interactive graph:\nfile://{os.path.abspath(output_path)}"
    )


if __name__ == "__main__":
    main()
