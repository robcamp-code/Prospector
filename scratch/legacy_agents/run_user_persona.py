#!/usr/bin/env python
"""Script to run the User Persona Agent on a query."""

import asyncio
import sys
import uuid
from pathlib import Path


async def main():
    """Run the User Persona Agent."""
    # Import here to ensure environment is loaded
    from src.agents.user_persona import UserPersonaAgent

    # Read query from file or use default
    query_file = Path("evals/query_1.txt")
    if query_file.exists():
        query = query_file.read_text().strip()
    else:
        print("No query file found at evals/query_1.txt")
        sys.exit(1)

    print("=" * 60)
    print("USER PERSONA AGENT")
    print("=" * 60)
    print(f"\nQuery:\n{query}\n")
    print("=" * 60)

    agent = UserPersonaAgent()

    print("\nRunning agent...\n")

    try:
        # Use unique thread_id to avoid stale checkpointer data
        thread_id = f"eval-{uuid.uuid4().hex[:8]}"
        print(f"Thread ID: {thread_id}\n")
        result = await agent.run(query, thread_id=thread_id)
        print("\n" + "=" * 60)
        print("RESULT")
        print("=" * 60)

        # Extract the final message from the respond node
        if result and "respond" in result:
            messages = result["respond"].get("messages", [])
            if messages:
                last_message = messages[-1]
                print(f"\nAgent Response:\n{last_message.content}")

        # Also check execute_save for tool results
        if result and "execute_save" in result:
            messages = result["execute_save"].get("messages", [])
            if messages:
                for msg in messages:
                    if hasattr(msg, "content"):
                        print(f"\nTool Result:\n{msg.content}")

        print("\n" + "=" * 60)
        print("Agent run completed successfully!")

    except Exception as e:
        print(f"\nError running agent: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
