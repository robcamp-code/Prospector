#!/usr/bin/env python
"""Script to run the Chat agent interactively."""

import argparse
import asyncio
import sys

from langchain_core.messages import AIMessage, HumanMessage


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Run Chat Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Start interactive chat
  python scripts/run_chat.py

  # Continue an existing conversation
  python scripts/run_chat.py <conversation-id>

  # Send a single message
  python scripts/run_chat.py -m "Hello, tell me about site selection"
        """,
    )
    parser.add_argument(
        "conversation_id",
        nargs="?",
        help="Conversation ID to continue an existing chat",
    )
    parser.add_argument(
        "--message",
        "-m",
        help="Single message to send (non-interactive mode)",
    )
    return parser.parse_args()


async def interactive_chat(conversation_id: str | None = None):
    """Run an interactive chat session."""
    from src.agents.chat import ChatAgent

    agent = ChatAgent()
    thread_id = conversation_id

    print("=" * 60)
    print("PROSPECTOR CHAT")
    if thread_id:
        print(f"Continuing conversation: {thread_id}")
    else:
        print("Starting new conversation")
    print("Type 'quit' or 'exit' to end, 'history' to see messages")
    print("=" * 60)

    while True:
        try:
            user_input = input("\nYou: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!")
            break

        if not user_input:
            continue

        if user_input.lower() in ("quit", "exit"):
            print("Goodbye!")
            break

        if user_input.lower() == "history":
            if thread_id:
                messages = await agent.get_history(thread_id)
                print("\n--- Conversation History ---")
                for msg in messages:
                    if isinstance(msg, HumanMessage):
                        print(f"\nYou: {msg.content}")
                    elif isinstance(msg, AIMessage):
                        print(f"\nAssistant: {msg.content}")
                print("--- End History ---")
            else:
                print("No conversation started yet.")
            continue

        try:
            result = await agent.chat(user_input, thread_id=thread_id)
            thread_id = result["thread_id"]
            state = result.get("state", {})

            # Handle LangGraph state format
            if "chat" in state:
                state = state["chat"]

            messages = state.get("messages", [])
            for msg in reversed(messages):
                if isinstance(msg, AIMessage) and msg.content:
                    print(f"\nAssistant: {msg.content}")
                    break

        except Exception as e:
            print(f"\nError: {e}")

    if thread_id:
        print(f"\nConversation ID: {thread_id}")
        print("(Use this ID to continue this conversation)")


async def single_message(message: str, conversation_id: str | None = None):
    """Send a single message and print the response."""
    from src.agents.chat import ChatAgent

    agent = ChatAgent()

    print("=" * 60)
    print("PROSPECTOR CHAT")
    print("=" * 60)
    print(f"\nYou: {message}\n")

    try:
        result = await agent.chat(message, thread_id=conversation_id)
        thread_id = result["thread_id"]
        state = result.get("state", {})

        if "chat" in state:
            state = state["chat"]

        messages = state.get("messages", [])
        for msg in reversed(messages):
            if isinstance(msg, AIMessage) and msg.content:
                print(f"Assistant: {msg.content}")
                break

        print(f"\n{'=' * 60}")
        print(f"Conversation ID: {thread_id}")

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


async def main():
    """Run the chat agent."""
    args = parse_args()

    if args.message:
        await single_message(args.message, args.conversation_id)
    else:
        await interactive_chat(args.conversation_id)


if __name__ == "__main__":
    asyncio.run(main())
