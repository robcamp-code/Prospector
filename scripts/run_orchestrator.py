#!/usr/bin/env python
"""Script to run the Orchestrator agent."""

import argparse
import asyncio
import sys
from pathlib import Path


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Run Orchestrator Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Start a fresh conversation
  python scripts/run_orchestrator.py

  # Continue an existing conversation
  python scripts/run_orchestrator.py orchestrator-abc12345

  # Send a custom query (fresh conversation)
  python scripts/run_orchestrator.py -q "Find me leads in Miami"

  # Send a custom query to existing conversation
  python scripts/run_orchestrator.py orchestrator-abc12345 -q "What about Tampa?"
        """,
    )
    parser.add_argument(
        "chat_id",
        nargs="?",
        help="Chat ID to continue an existing conversation",
    )
    parser.add_argument(
        "--query",
        "-q",
        help="Query to send (overrides file/default)",
    )
    return parser.parse_args()


def get_query(args) -> str:
    """Get the query to send, from args, file, or default."""
    if args.query:
        return args.query

    # Default test query
    default_query = """I own a window cleaning franchise called Crystal Clear Windows in Atlanta.
We specialize in residential exterior window cleaning for homeowners.
Our ideal customers are typically middle to upper-middle class homeowners
who value curb appeal and don't have time to clean their own windows."""

    # Read query from file or use default
    query_file = Path("evals/query_1.txt")
    if query_file.exists():
        return query_file.read_text().strip()

    return default_query


async def main():
    """Run the Orchestrator agent."""
    args = parse_args()

    # Import here to ensure environment is loaded
    from src.agents.orchestrator import Orchestrator

    query = get_query(args)
    is_continuation = args.chat_id is not None

    print("=" * 60)
    print("ORCHESTRATOR AGENT")
    if is_continuation:
        print(f"Continuing conversation: {args.chat_id}")
    else:
        print("Starting fresh conversation")
    print("=" * 60)
    print(f"\nQuery:\n{query}\n")
    print("=" * 60)

    orchestrator = Orchestrator()

    print("\nRunning orchestrator...\n")

    try:
        if is_continuation:
            result = await orchestrator.continue_conversation(query, args.chat_id)
        else:
            result = await orchestrator.run(query)

        thread_id = result.get("thread_id", "unknown")
        state = result.get("state", {})

        print("\n" + "=" * 60)
        print("RESULT")
        print("=" * 60)

        # Extract messages from state
        if state:
            # The state structure from create_react_agent
            # could be nested under different keys
            messages = None

            # Check for agent key (common with create_react_agent)
            if "agent" in state:
                messages = state["agent"].get("messages", [])
            elif "messages" in state:
                messages = state["messages"]

            if messages:
                print("\nFinal Messages:")
                for msg in messages[-3:]:  # Last 3 messages
                    msg_type = type(msg).__name__
                    content = getattr(msg, "content", str(msg))
                    if content:
                        print(f"\n[{msg_type}]")
                        print(
                            content[:500] + "..."
                            if len(str(content)) > 500
                            else content
                        )

            # Check for client_profile in state
            client_profile = None
            if "agent" in state:
                client_profile = state["agent"].get("client_profile")
            elif "client_profile" in state:
                client_profile = state["client_profile"]

            if client_profile:
                print("\n" + "-" * 40)
                print("CLIENT PROFILE IN STATE:")
                print("-" * 40)
                print(f"  Profile ID: {client_profile.profile_id}")
                print(f"  Name: {client_profile.name}")
                print(f"  Business Type: {client_profile.business_type}")
                print(
                    f"  Income Range: ${client_profile.target_income_min:,} - ${client_profile.target_income_max:,}"
                )
                print(
                    f"  Age Range: {client_profile.target_age_min} - {client_profile.target_age_max}"
                )
                print(f"  Competitor Types: {client_profile.competitor_types}")
                print(f"  Complementary Types: {client_profile.complimentary_types}")

        # Display chat ID prominently for continuation
        print("\n" + "=" * 60)
        print(f"Chat ID: {thread_id}")
        print("(Use this ID to continue this conversation)")
        print("=" * 60)
        print("\nOrchestrator run completed successfully!")

    except Exception as e:
        print(f"\nError running orchestrator: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
