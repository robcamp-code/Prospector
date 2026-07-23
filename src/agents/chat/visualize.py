"""Visualization utilities for LangGraph agent."""

from pathlib import Path

from langgraph.graph import StateGraph


def _visualize(graph: StateGraph, output_dir: str = "docs", filename: str = "agent-graph.png") -> str:
    """Generate and save a visual representation of the LangGraph.

    Outputs either a PNG diagram or Mermaid markdown of the graph structure.
    Automatically selects format based on filename extension.
    Uses LangGraph's built-in Mermaid rendering.

    Args:
        graph: The compiled LangGraph StateGraph or CompiledGraph
        output_dir: Directory to save the visualization (default: "docs")
        filename: Output filename (default: "agent-graph.png")
               Use ".png" extension to generate PNG (requires graphviz)
               Use ".md" extension to generate Mermaid markdown (always works)

    Returns:
        Path to the generated visualization file
    """
    output_path = Path(output_dir) / filename
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Get the Mermaid graph representation
    try:
        if hasattr(graph, "get_graph"):
            mermaid_graph = graph.get_graph()
        else:
            mermaid_graph = graph
    except Exception as e:
        raise RuntimeError(f"Failed to get graph representation: {e}") from e

    # Determine output format from extension
    file_ext = output_path.suffix.lower()

    if file_ext == ".md":
        # Save as Mermaid markdown (always works)
        try:
            mermaid_str = mermaid_graph.draw_mermaid()
            with open(output_path, "w") as f:
                f.write(f"```mermaid\n{mermaid_str}\n```\n")
            return str(output_path)
        except Exception as e:
            raise RuntimeError(f"Failed to generate Mermaid markdown: {e}") from e

    else:
        # Try to save as PNG (requires graphviz)
        try:
            png_data = mermaid_graph.draw_mermaid_png()
            with open(output_path, "wb") as f:
                f.write(png_data)
            return str(output_path)
        except Exception as e:
            # Fallback: save as Mermaid markdown instead
            try:
                mermaid_str = mermaid_graph.draw_mermaid()
                mermaid_path = output_path.with_suffix(".mermaid.md")
                with open(mermaid_path, "w") as f:
                    f.write(f"```mermaid\n{mermaid_str}\n```\n")
                print(f"Note: PNG generation failed, saved as Mermaid markdown instead: {mermaid_path}")
                return str(mermaid_path)
            except Exception as fallback_error:
                raise RuntimeError(
                    f"Failed to visualize graph as PNG or Mermaid: {e} (fallback: {fallback_error})"
                ) from fallback_error
