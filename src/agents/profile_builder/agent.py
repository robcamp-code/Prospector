"""ProfileBuilder agent for creating client profiles from business descriptions."""

from typing import Annotated

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode
from typing_extensions import TypedDict

from langgraph.graph.message import add_messages
from src.agents.profile_builder.prompts import get_system_prompt
from src.agents.profile_builder.tools import profile_builder_tools
from src.core.config import get_settings


class ProfileBuilderState(TypedDict):
    """State for the ProfileBuilder agent."""

    messages: Annotated[list, add_messages]
    service_description: str
    conversation_id: str | None
    profile_id: int | None
    error: str | None


class ProfileBuilderAgent:
    """Agent that creates client profiles from business descriptions.

    This agent analyzes a business description and creates:
    1. A ClientProfile record with business info and place types
    2. DemographicTarget records for customer targeting
    """

    def __init__(self, model: str | None = None):
        settings = get_settings()
        self.model = model or settings.model
        self.llm = ChatOpenAI(model=self.model, temperature=0)
        self.tools = profile_builder_tools
        self.llm_with_tools = self.llm.bind_tools(self.tools)

    def _build_graph(self) -> StateGraph:
        """Build the ProfileBuilder graph."""

        def analyze_and_save(state: ProfileBuilderState) -> dict:
            """Analyze description and call tools to save profile."""
            messages = state["messages"]

            # Prepend system message if not present
            if not messages or not isinstance(messages[0], SystemMessage):
                messages = [SystemMessage(content=get_system_prompt())] + list(messages)

            # Add context about conversation_id for the tool
            context_msg = ""
            if state.get("conversation_id"):
                context_msg = f"\n\nIMPORTANT: Use conversation_id='{state['conversation_id']}' when calling save_client_profile."

            if context_msg and len(messages) > 1:
                # Append context to the last human message
                last_human_idx = None
                for i, msg in enumerate(messages):
                    if isinstance(msg, HumanMessage):
                        last_human_idx = i
                if last_human_idx is not None:
                    messages[last_human_idx] = HumanMessage(
                        content=messages[last_human_idx].content + context_msg
                    )

            response = self.llm_with_tools.invoke(messages)
            return {"messages": [response]}

        def should_continue(state: ProfileBuilderState) -> str:
            """Determine if we should continue to tools or end."""
            messages = state["messages"]
            last_message = messages[-1]

            # If there are tool calls, go to tools node
            if hasattr(last_message, "tool_calls") and last_message.tool_calls:
                return "tools"

            # Otherwise end
            return END

        # Build graph
        graph = StateGraph(ProfileBuilderState)

        # Add nodes
        graph.add_node("analyze_and_save", analyze_and_save)
        graph.add_node("tools", ToolNode(self.tools))

        # Set entry point
        graph.set_entry_point("analyze_and_save")

        # Add conditional edge from analyze_and_save
        graph.add_conditional_edges(
            "analyze_and_save",
            should_continue,
            {"tools": "tools", END: END},
        )

        # Tools always go back to analyze_and_save
        graph.add_edge("tools", "analyze_and_save")

        return graph

    def run(
        self, service_description: str, conversation_id: str | None = None
    ) -> dict:
        """Run the ProfileBuilder to create a profile (synchronous).

        Args:
            service_description: Description of the business
            conversation_id: Optional conversation ID to link the profile to

        Returns:
            Dict with profile_id and any errors
        """
        graph = self._build_graph()
        agent = graph.compile()

        input_state = {
            "messages": [HumanMessage(content=service_description)],
            "service_description": service_description,
            "conversation_id": conversation_id,
            "profile_id": None,
            "error": None,
        }

        final_state = agent.invoke(input_state)

        return {
            "profile_id": final_state.get("profile_id"),
            "error": final_state.get("error"),
        }
