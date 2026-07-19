from typing import Annotated, Any, Literal, Optional
import json
import pathlib

from langchain_core.messages import SystemMessage, AIMessage, HumanMessage
from langchain.chat_models import init_chat_model
from langgraph.graph import START, END, StateGraph
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field
from typing_extensions import TypedDict
from sqlalchemy import delete

from src.agents.orchestrator.prompts import (
    DISCOVERY_PROMPT,
    INITIAL_MESSAGE,
    ASK_USER_FOR_MISSING_PREFERENCES,
    DEMOGRAPHIC_EXTRACTION_PROMPT,
    format_demographics_for_prompt,
)
from src.agents.orchestrator.demographics import DEMOGRAPHICS, MetricType
from src.models import ClientProfile, DemographicTarget
from src.core.database import AsyncSessionLocal
from src.core.state import ClientProfileRef, DemographicTargetRef


# ANSI color codes for pretty output
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'


def pretty_print_state(title: str, state: dict[str, Any], color: str = Colors.CYAN) -> None:
    """Pretty print state changes with formatted JSON."""
    print(f"\n{color}{Colors.BOLD}{'='*60}{Colors.ENDC}")
    print(f"{color}{Colors.BOLD}{title}{Colors.ENDC}")
    print(f"{color}{'='*60}{Colors.ENDC}")

    for key, value in state.items():
        print(f"\n{Colors.YELLOW}{Colors.BOLD}{key}:{Colors.ENDC}")
        if value is None:
            print(f"  {Colors.DIM}None{Colors.ENDC}")
        elif isinstance(value, BaseModel):
            print(f"{Colors.GREEN}{json.dumps(value.model_dump(), indent=2, default=str)}{Colors.ENDC}")
        elif isinstance(value, list):
            if len(value) == 0:
                print(f"  {Colors.DIM}[]{Colors.ENDC}")
            else:
                for i, item in enumerate(value):
                    if hasattr(item, 'content'):
                        role = getattr(item, 'type', 'message')
                        content = item.content[:100] + '...' if len(str(item.content)) > 100 else item.content
                        print(f"  {Colors.BLUE}[{i}] {role}: {content}{Colors.ENDC}")
                    elif isinstance(item, dict):
                        print(f"  {Colors.GREEN}{json.dumps(item, indent=4, default=str)}{Colors.ENDC}")
                    else:
                        print(f"  {Colors.GREEN}{item}{Colors.ENDC}")
        elif isinstance(value, dict):
            print(f"{Colors.GREEN}{json.dumps(value, indent=2, default=str)}{Colors.ENDC}")
        elif isinstance(value, bool):
            color_val = Colors.GREEN if value else Colors.RED
            print(f"  {color_val}{value}{Colors.ENDC}")
        else:
            print(f"  {Colors.GREEN}{value}{Colors.ENDC}")

    print(f"{color}{'='*60}{Colors.ENDC}\n")


class Preferences(BaseModel):
    """Preferences model with optional fields for incremental extraction."""
    name: Optional[str] = None
    business_category: Optional[str] = Field(default=None, description="What category (fitness, restaurant, retail, service, etc.)?")
    services_products: Optional[str] = Field(default=None, description="What do they offer? What's their specialty?")
    price_point: Optional[str] = Field(default=None, description="Budget, mid-market, premium, or luxury?")
    target_customer: Optional[str] = Field(default=None, description="Who are their ideal customers? Age range? Income level? socio economic status")
    location_preferences: Optional[str] = Field(default=None, description="Particular region, east, west cost or any states in particular? Urban, suburban, or rural areas?")

    def is_complete(self) -> bool:
        """Check if all required preferences have been gathered."""
        return all([
            self.name,
            self.business_category,
            self.services_products,
            self.price_point,
            self.target_customer,
            self.location_preferences
        ])

    def missing_fields(self) -> list[str]:
        """Returns list of missing field names for LLM context."""
        field_names = {
            "name": "Business Name",
            "business_category": "Business Category",
            "services_products": "Services/Products",
            "price_point": "Price Point",
            "target_customer": "Target Customer",
            "location_preferences": "Location Preferences"
        }
        missing = []
        if not self.name:
            missing.append(field_names["name"])
        if not self.business_category:
            missing.append(field_names["business_category"])
        if not self.services_products:
            missing.append(field_names["services_products"])
        if not self.price_point:
            missing.append(field_names["price_point"])
        if not self.target_customer:
            missing.append(field_names["target_customer"])
        if not self.location_preferences:
            missing.append(field_names["location_preferences"])
        return missing


class DemographicTargetExtraction(BaseModel):
    """Single demographic target extracted by LLM."""

    demographic_key: str = Field(description="Must match valid key from DEMOGRAPHICS")
    constraint_type: Literal["range", "threshold_min", "threshold_max", "percentage"]
    min_value: float | None = None
    max_value: float | None = None
    target_percentage: float | None = None
    percentage_operator: Literal["gt", "lt", "gte", "lte", "eq"] | None = None
    importance_weight: float = Field(default=0.5, ge=0, le=1)
    reasoning: str = Field(description="Why this demographic matters for the business")


class DemographicTargetsExtraction(BaseModel):
    """Collection of demographic targets."""

    targets: list[DemographicTargetExtraction]
    needs_more_info: bool = False
    follow_up_question: str | None = None


class GlobalState(TypedDict):
    """Global State object shared between nodes."""

    messages: Annotated[list, add_messages]
    preferences: Preferences
    client_profile: ClientProfileRef | None
    asked_for_more: bool



class Orchestrator:

    def __init__(self):
        """Initialize Model."""
        self.llm = init_chat_model("openai:gpt-4.1")
        self.graph: StateGraph = StateGraph(GlobalState)

    
    def initial_router(self, state: GlobalState):
        """Initial router for agent"""
        client_profile = state["client_profile"]

        # Check if profile exists and has required fields
        step_2_complete = client_profile is not None and all([
            client_profile.profile_id,
            client_profile.name,
            client_profile.business_type,
            client_profile.service_description
        ])
        # Check if we have enough demographic targets (>3)
        step_3_complete = (
            client_profile is not None
            and len(client_profile.target_demographics) > 3
        )

        # STEP 1: Prompt user until preferences are complete and the AI doesn't need to ask for more
        if not state["preferences"].is_complete():
            return "discovery"

        elif state["asked_for_more"]:
            return END

        # STEP 2 save a bare minimum profile
        elif not step_2_complete:
            return "profile_builder"

        # STEP 3: Extract demographic targets
        elif not step_3_complete:
            return "get_target_demographics"

        # STEP 4: Query node (ready to search)
        return "query_node"
    
    def discovery_agent(self, state: GlobalState) -> dict:
        """
        Chat with the user and gather business preferences incrementally.
        Uses two LLM calls: one for extraction, one for response generation.
        """
        
        current_prefs = state.get("preferences") or Preferences()
        
        extraction_llm = self.llm.with_structured_output(Preferences)
        extracted = extraction_llm.invoke(state["messages"])

        updated = Preferences(
            name=extracted.name or current_prefs.name,
            business_category=extracted.business_category or current_prefs.business_category,
            services_products=extracted.services_products or current_prefs.services_products,
            price_point=extracted.price_point or current_prefs.price_point,
            target_customer=extracted.target_customer or current_prefs.target_customer,
            location_preferences=extracted.location_preferences or current_prefs.location_preferences,
        )

        missing = updated.missing_fields()
        if missing:
            response = self.llm.invoke(ASK_USER_FOR_MISSING_PREFERENCES)
            return {
                "messages": [response],
                "preferences": updated,
                "asked_for_more": True
            }
        
        return {"preferences": updated, "asked_for_more": False}

    

    def route_after_discovery(self, state: GlobalState) -> str:
        """Route to profile_builder if preferences complete, otherwise loop back to discovery."""
        preferences = state.get("preferences")
        if preferences and preferences.is_complete():
            return "profile_builder"
        return "prompt_for_preferences"

    async def profile_builder(self, state: GlobalState) -> dict:
        """Build ClientProfile directly from preferences - no LLM needed."""
        preferences = state["preferences"]
        client_profile = ClientProfile(
            name=preferences.name,
            business_type=preferences.business_category,
            service_description=preferences.services_products,
        )

        # TODO: add exception handling in case of db failure
        async with AsyncSessionLocal() as session:
            session.add(client_profile)
            await session.commit()
            # No refresh needed - AsyncSessionLocal uses expire_on_commit=False

        # Convert to serializable Pydantic model for state
        client_profile_ref = ClientProfileRef(
            profile_id=client_profile.id,
            name=client_profile.name,
            business_type=client_profile.business_type,
            service_description=client_profile.service_description,
        )

        return {"client_profile": client_profile_ref}

    
    def _get_valid_demographic_keys(self) -> set[str]:
        """Returns set of valid demographic keys from DEMOGRAPHICS mapping."""
        valid_keys = set()
        for category in DEMOGRAPHICS.categories.values():
            for metric_name, metric in category.metrics.items():
                # Skip distribution metrics - they're not directly targetable
                if metric.type != MetricType.DISTRIBUTION:
                    valid_keys.add(metric_name)
        return valid_keys

    async def _persist_demographic_targets(
        self, profile_id: str, targets: list[DemographicTargetRef]
    ) -> None:
        """Delete existing targets and insert new ones."""
        async with AsyncSessionLocal() as session:
            # Delete existing targets for this profile
            await session.execute(
                delete(DemographicTarget).where(
                    DemographicTarget.client_profile_id == profile_id
                )
            )

            # Insert new targets
            for target in targets:
                db_target = DemographicTarget(
                    client_profile_id=profile_id,
                    demographic_key=target.demographic_key,
                    constraint_type=target.constraint_type,
                    min_value=target.min_value,
                    max_value=target.max_value,
                    target_percentage=target.target_percentage,
                    percentage_operator=target.percentage_operator,
                    importance_weight=target.importance_weight,
                )
                session.add(db_target)

            await session.commit()

    async def get_target_demographics(self, state: GlobalState) -> dict:
        """Extract demographic targets from preferences using LLM structured output."""
        preferences = state["preferences"]
        client_profile = state["client_profile"]

        # Format preferences for the prompt
        preferences_text = f"""
Business Name: {preferences.name}
Business Category: {preferences.business_category}
Services/Products: {preferences.services_products}
Price Point: {preferences.price_point}
Target Customer: {preferences.target_customer}
Location Preferences: {preferences.location_preferences}
"""

        # Format demographic keys for prompt
        demographic_keys = format_demographics_for_prompt(DEMOGRAPHICS)

        # Build the extraction prompt
        prompt = DEMOGRAPHIC_EXTRACTION_PROMPT.format(
            preferences=preferences_text,
            demographic_keys=demographic_keys,
        )

        # Call LLM with structured output
        extraction_llm = self.llm.with_structured_output(DemographicTargetsExtraction)
        extraction_result: DemographicTargetsExtraction = extraction_llm.invoke(
            [SystemMessage(content=prompt)]
        )

        # Handle case where LLM needs more info
        if extraction_result.needs_more_info and extraction_result.follow_up_question:
            return {
                "messages": [AIMessage(content=extraction_result.follow_up_question)],
                "asked_for_more": True,
            }

        # Get valid demographic keys for validation
        valid_keys = self._get_valid_demographic_keys()

        # Convert extracted targets to DemographicTargetRef, validating keys
        target_refs: list[DemographicTargetRef] = []
        for target in extraction_result.targets:
            if target.demographic_key not in valid_keys:
                continue

            target_ref = DemographicTargetRef(
                demographic_key=target.demographic_key,
                constraint_type=target.constraint_type,
                min_value=target.min_value,
                max_value=target.max_value,
                target_percentage=target.target_percentage,
                percentage_operator=target.percentage_operator,
                importance_weight=target.importance_weight,
            )
            target_refs.append(target_ref)

        # Persist to database
        if client_profile and client_profile.profile_id:
            await self._persist_demographic_targets(client_profile.profile_id, target_refs)

        # Update client profile ref with targets
        updated_profile = ClientProfileRef(
            profile_id=client_profile.profile_id,
            name=client_profile.name,
            business_type=client_profile.business_type,
            service_description=client_profile.service_description,
            competitor_types=client_profile.competitor_types,
            complimentary_types=client_profile.complimentary_types,
            target_income_min=client_profile.target_income_min,
            target_income_max=client_profile.target_income_max,
            target_demographics=target_refs,
        )

        pretty_print_state(
            "GET_TARGET_DEMOGRAPHICS - Output",
            {"client_profile": updated_profile, "target_count": len(target_refs)},
            Colors.GREEN,
        )

        return {"client_profile": updated_profile}

    def query_node(self, state: GlobalState) -> dict:
        """Stub for query node - implementation out of scope."""
        return {}
    
    def _write_graph(self):
        """write graph to disk for troubleshooting / visualization"""
        pathlib.Path("graph.png").write_bytes(self.graph.get_graph().draw_mermaid_png())
    
    def _build_graph(self):
        graph = StateGraph(GlobalState)

        graph.add_node("initial_router", self.initial_router)
        graph.add_node("discovery", self.discovery_agent)
        graph.add_node("profile_builder", self.profile_builder)
        graph.add_node("get_target_demographics", self.get_target_demographics)
        graph.add_node("query_node", self.query_node)

        # Step 1: Pick up where we left off at any node in the graph
        graph.add_conditional_edges(
            START,
            self.initial_router,
            {
                "discovery": "discovery",
                "profile_builder": "profile_builder",
                "get_target_demographics": "get_target_demographics",
                "query_node": "query_node",
                END: END,
            },
        )

        # Step 2
        graph.add_conditional_edges(
            "discovery",
            self.initial_router,
            {
                "discovery": "discovery",
                "profile_builder": "profile_builder",
                "get_target_demographics": "get_target_demographics",
                "query_node": "query_node",
                END: END,
            },
        )

        # Step 3
        graph.add_conditional_edges(
            "profile_builder",
            self.initial_router,
            {
                "get_target_demographics": "get_target_demographics",
                "query_node": "query_node",
                END: END,
            },
        )

        # Step 4: After demographics, route based on target count
        graph.add_conditional_edges(
            "get_target_demographics",
            self.initial_router,
            {
                "get_target_demographics": "get_target_demographics",
                "query_node": "query_node",
                END: END,
            },
        )

        # Step 5: Query node ends the workflow
        graph.add_edge("query_node", END)

        self.graph = graph.compile()

        self._write_graph()
  
    def _append_message(self, state: GlobalState, user_input: str):
        state["messages"] = state.get("messages", []) + [
                {"role": "user", "content": user_input}
            ]
    
    async def local_chat(self):
        """ chat """
        state = {
            "messages": [AIMessage(content=INITIAL_MESSAGE)],
            "client_profile": None,
            "preferences": Preferences(),
            "asked_for_more": False
        }

        is_first = True
        while True:
            if is_first:

                print(INITIAL_MESSAGE)
                is_first = False

            user_input = input(f"{Colors.BOLD}Message: {Colors.ENDC}")
            if user_input == "exit":
                break

            self._append_message(state, user_input)
            state = await self.graph.ainvoke(state)

            if state.get("messages") and len(state["messages"]) > 0:
                print(state.get("messages")[-1])


if __name__ == "__main__":
    import asyncio
    chat_bot = Orchestrator()
    chat_bot._build_graph()
    asyncio.run(chat_bot.local_chat())




        



# Use the preferences to build a profile (skip if profile already exists)

# Is the user happy/agent happy with their profile

# Build Charts

# Write Report