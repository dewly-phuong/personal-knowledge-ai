"""
Chart generation tool: generate_chart.
"""

from typing import List

from langchain_core.tools import tool


@tool
def generate_chart(
    chart_type: str,
    title: str,
    labels: List[str],
    values: List[float],
    x_label: str = "",
    y_label: str = "",
) -> str:
    """
    Render a visual chart (pie, bar, or line) directly in the chat.

    USE WHEN: user explicitly asks for a chart, graph, or visualization.
    ALWAYS call knowledge_search FIRST to retrieve and aggregate data, then call this.
    NEVER pass column names or field references — pass computed label strings and numeric values directly.

    Args:
        chart_type: "pie", "bar", or "line"
        title: Chart title
        labels: List of category or x-axis label strings, e.g. ["Compute", "Database", "Storage"]
        values: List of numeric values matching each label, e.g. [1500.0, 800.0, 300.0]
        x_label: X-axis label (bar/line only, optional)
        y_label: Y-axis label (bar/line only, optional)
    """
    try:
        import plotly.graph_objects as go
        import plotly.io as pio

        chart_type = chart_type.lower().strip()
        if chart_type == "pie":
            fig = go.Figure(
                data=[
                    go.Pie(
                        labels=labels,
                        values=values,
                        hole=0.3,
                        textinfo="label+percent",
                    )
                ]
            )
        elif chart_type == "bar":
            fig = go.Figure(
                data=[
                    go.Bar(
                        x=labels,
                        y=values,
                        text=[f"{v:,.2f}" for v in values],
                        textposition="auto",
                    )
                ]
            )
            fig.update_layout(xaxis_title=x_label, yaxis_title=y_label)
        elif chart_type == "line":
            fig = go.Figure(
                data=[
                    go.Scatter(
                        x=labels,
                        y=values,
                        mode="lines+markers",
                        text=[f"{v:,.2f}" for v in values],
                    )
                ]
            )
            fig.update_layout(xaxis_title=x_label, yaxis_title=y_label)
        else:
            return f"Error: Unsupported chart_type '{chart_type}'. Use 'pie', 'bar', or 'line'."

        fig.update_layout(title=title, template="plotly_white")
        return f"CHART_JSON:{pio.to_json(fig)}"
    except Exception as e:
        return f"Error generating chart: {e}"
