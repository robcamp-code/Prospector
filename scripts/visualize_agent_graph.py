#!/usr/bin/env python
"""Generate a visual representation of the multi-node chat agent graph.

Usage:
    python scripts/visualize_agent_graph.py [output_dir] [filename]

Example:
    python scripts/visualize_agent_graph.py docs agent-graph.png
    python scripts/visualize_agent_graph.py . agent-flow.mermaid.md
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.agents.chat.agent import ChatAgent


def main():
    """Generate and save agent graph visualization."""
    output_dir = sys.argv[1] if len(sys.argv) > 1 else "docs"
    filename = sys.argv[2] if len(sys.argv) > 2 else "agent-graph.png"

    print(f"Generating agent graph visualization...")
    print(f"Output directory: {output_dir}")
    print(f"Filename: {filename}")

    try:
        agent = ChatAgent()
        output_path = agent.visualize(output_dir=output_dir, filename=filename)
        print(f"✓ Graph visualization saved to: {output_path}")
        return 0
    except Exception as e:
        print(f"✗ Error generating visualization: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
