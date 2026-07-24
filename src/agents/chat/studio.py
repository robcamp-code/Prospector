"""LangGraph Studio entrypoint — referenced by langgraph.json (langgraph dev).

Exposes the uncompiled StateGraph; the LangGraph API server compiles it with
its own checkpointer. The FastAPI path (ChatAgent.chat) is unaffected and
keeps using the Postgres checkpointer.
"""

from src.agents.chat.agent import ChatAgent

graph = ChatAgent()._build_graph_structure()
