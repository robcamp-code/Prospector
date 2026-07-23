# Multi-Node Agent Implementation Roadmap

## ✅ Completed Foundation

- `src/core/database/models/client_profile.py` — ClientProfile, DemographicTarget, converters
- `src/core/database/models/report.py` — Report JSONB model
- `src/core/state.py` — ClientProfileRef, DemographicTargetRef (state mirrors)
- `src/schemas/report.py` — Full Report schema (5 visualization types)
- `src/agents/chat/location_filters.py` — LocationFilters model (defensive validators)
- `src/agents/chat/graph_state.py` — GraphState TypedDict (core state definition)
- **Alembic migration** — Creates client_profiles, demographic_targets, reports tables
- **All imports verified working**

## 🚀 Next: Node Implementations

### 1. Profile Builder Node (`src/agents/chat/profile_builder.py`)

**Purpose**: Extract business info + demographic interests from message history; ask follow-ups if incomplete.

**Signature**:
```python
async def profile_builder(state: GraphState, config: RunnableConfig) -> dict
```

**Inputs**:
- `state.messages` — full conversation history
- `state.client_profile` — None (first run) or existing ref (reload case)

**LLM Extraction Target**:
```python
class Preferences(BaseModel):
    name: str | None
    business_type: str | None  # e.g. "retail", "fitness", "hospitality"
    services_products: str | None
    price_point: str | None  # e.g. "budget", "premium"
    target_customer_description: str | None
    location_preference: str | None  # Raw text, e.g. "Atlanta metro area, suburban"
    demographic_interests: str | None  # Free text, e.g. "young professionals, college educated"
```

**Logic**:
1. Call LLM with `with_structured_output(Preferences)` over full message history
2. Merge with existing profile if any
3. Check `is_complete()` — all required fields non-None and non-empty
4. If incomplete:
   - LLM generates a natural follow-up question for ONE missing field
   - Append question to messages
   - Return `{"messages": [...], "profile_complete": False}`
   - Graph routes to `END` (ask user)
5. If complete:
   - Persist to DB: `ClientProfile` row + `DemographicTarget` rows (one per demographic interest extracted by LLM parsing the free text, validated against DEMOGRAPHICS)
   - Convert to ref via `client_profile_to_ref()`
   - Return `{"client_profile": ref, "profile_complete": True}`
   - Graph routes to `data_analyst`

**Key Detail**: Use `config["configurable"]["thread_id"]` as `conversation_id` when creating ClientProfile (same pattern as old orchestrator).

---

### 2. Data Analyst Node (`src/agents/chat/data_analyst.py`)

**Purpose**: Transform profile into a concrete query plan (categories, geography level, resolved location).

**Signature**:
```python
async def data_analyst(state: GraphState) -> dict
```

**Inputs**:
- `state.client_profile` — the built profile with demographics + location preference text

**LLM Extraction Target**:
```python
class LocationFilters(BaseModel):  # Already defined in location_filters.py
    scope: Literal["nationwide", "region", "states", "metros"]
    region_name: str | None
    state_names: list[str]
    cbsa_names: list[str]
    area_type: Literal["urban", "suburban", "rural", "any"]
    reasoning: str
```

**Logic** (no tool calls, pure LLM + deterministic logic):
1. Call LLM with `with_structured_output(LocationFilters)` to parse client's raw location preference
2. Deterministic category selection (function-based, not LLM):
   - Map each `client_profile.target_demographics[*].demographic_key` → CategoryName via `DEMOGRAPHICS.category_for_metric()`
   - Union with `CORE_CATEGORIES = ["income", "age", "education"]`
   - Pad to at least 5 categories using priority order from `DEMOGRAPHICS.get_all_categories()`
   - Fall back to all 11 categories if no targets map
3. Deterministic geography_level picker (function-based):
   - If `location.scope == "nationwide"` → group by "state"
   - If `location.scope == "region"` and `location.region_name` → group by "state"
   - If `location.scope == "states"` → group by "county"
   - If `location.scope == "metros"` → group by "zip" or "city" (user's choice)
   - Rationale: always group one level below the filter so results are chartable (never a single row)
4. Build `AnalysisPlan`:
   ```python
   AnalysisPlan(
       location=location.model_dump(),
       categories=categories,
       geography_level=geography_level,
       reasoning="..."
   )
   ```
5. Return `{"analysis_plan": plan}`
   - Graph routes to `report_builder`

**Note**: This node does NOT interact with the database or `get_aggregation` tool — it's a pure LLM + logic step.

---

### 3. Report Builder Nodes (`src/agents/chat/report_builder.py`)

Three sub-nodes implementing a bounded ReAct loop:

#### 3a. `report_builder_llm` Node

**Purpose**: LLM bound with `get_aggregation_tool`, directed by `AnalysisPlan`, to iteratively fetch data.

**Signature**:
```python
async def report_builder_llm(state: GraphState) -> dict
```

**Context Prompt** (injected into system message):
- `AnalysisPlan` summary: "You are gathering data to build a demographic report. Categories to analyze: [income, age, ...]. Geography level: county. Location: [Atlanta metro, filter by region=South]."
- `client_profile` summary: "Client is a fitness center targeting professionals age 25-45 with $60K-$150K income in suburban areas."
- Instructions: "Use the get_aggregation_tool to fetch demographic data. You can make multiple calls to drill down (e.g., state-level first, then counties within that state). Stop when you have enough data for a comprehensive report (~3-5 tool calls). Then respond naturally (not as JSON) saying you're ready to finalize."

**Tool Binding**:
```python
llm = init_chat_model(settings.model).bind_tools([get_aggregation_tool])
```

**Outputs**:
- If tool calls are made → `{"messages": [...with tool calls and results appended...]}` loop back to `report_tools`
- If no tool calls and natural response → route to `finalize_report`
- Safety valve: if >8 tool calls → force route to `finalize_report`

#### 3b. `report_tools` Node (ToolNode)

**Purpose**: Execute tool calls from the LLM.

**Implementation**:
```python
from langgraph.prebuilt import ToolNode
tools = [get_aggregation_tool]
tools_node = ToolNode(tools)
```

Routes back to `report_builder_llm` (loop until LLM stops calling tools or cap is hit).

#### 3c. `finalize_report` Node

**Purpose**: Convert tool-call transcript into structured Report object; persist to DB.

**Signature**:
```python
async def finalize_report(state: GraphState) -> dict
```

**LLM Structured Output**:
```python
class Report(BaseModel):  # From src/schemas/report.py
    report_id: str
    title: str
    subtitle: str | None
    geography_type: str  # From analysis_plan
    geography_value: str  # e.g. "Metro areas: Atlanta-Sandy Springs-Roswell, GA"
    client_profile_id: str | None
    summary: ReportSummary  # Includes narrative + opportunity_bubble_chart
    sections: list[ReportSection]  # Each with visualizations
    generated_at: str | None
```

**Logic**:
1. Over the `state.messages` transcript (which includes all tool-call results):
   - Call LLM with `with_structured_output(Report)` to synthesize a final Report
   - LLM uses `transformers.py` logic (ported pure functions `to_categorical_data`, `to_distribution_data`, `to_bubble_data`) to shape tool results into visualizations
   - LLM groups categories into sections (reuse old `with_structured_output(SectionGroupingResponse)` pattern)
   - LLM writes narrative summary (old `with_structured_output(SummaryNarrative)` pattern)
2. Persist to DB:
   ```python
   async with AsyncSessionLocal() as session:
       db_report = Report(**report.model_dump())
       session.add(db_report)
       await session.commit()
   ```
3. Return `{"report": report}`
   - Graph routes to `END`

---

## 4. Tool Wrapper: `get_aggregation_tool` (`src/agents/chat/tools.py`)

```python
from langchain_core.tools import tool
from src.core.services.zips import get_aggregation
from src.core.database import AsyncSessionLocal
from src.schemas.aggregation import GeographyLevel

@tool
async def get_aggregation_tool(
    group_by: GeographyLevel,
    metrics: list[str],  # e.g. ["income.median_household_income", "race.distribution"]
    region: str | None = None,
    state: str | None = None,
    county: str | None = None,
    cbsa: str | None = None,
    city: str | None = None,
    sort_by: str | None = None,
    sort_dir: str = "desc",
    limit: int = 50,
) -> str:
    """Fetch aggregated demographic data for geographic regions.
    
    Args:
        group_by: Geography level to group results by
        metrics: List of 'category.metric' strings (e.g., 'income.median_household_income')
        region/state/county/cbsa/city: Optional geographic filters
        sort_by: Metric to sort by (e.g., 'population' or 'income.median_household_income')
        sort_dir: 'asc' or 'desc'
        limit: Max rows to return (1-1000)
    
    Returns:
        JSON string of AggregationResponse with rows, limit, offset, total_count
    """
    async with AsyncSessionLocal() as session:
        try:
            response = await get_aggregation(
                session=session,
                group_by=group_by,
                metric_selectors=metrics,
                region=region,
                state=state,
                county=county,
                cbsa=cbsa,
                city=city,
                sort_by=sort_by,
                sort_dir=sort_dir,
                limit=limit,
                offset=0,
            )
            return response.model_dump_json()
        except Exception as exc:
            # Catch HTTPException and others; return error string so LLM can retry
            return f"Error: {str(exc)}"
```

---

## 5. ChatAgent Update (`src/agents/chat/agent.py`)

Replace the skeleton single-node graph with the three-node graph:

```python
from langgraph.graph import START, StateGraph
from src.agents.chat.graph_state import GraphState
from src.agents.chat.profile_builder import profile_builder
from src.agents.chat.data_analyst import data_analyst
from src.agents.chat.report_builder import (
    report_builder_llm,
    report_tools,
    finalize_report,
)

class ChatAgent:
    def _build_graph_structure(self) -> StateGraph:
        graph = StateGraph(GraphState)
        
        # Add nodes
        graph.add_node("profile_builder", profile_builder)
        graph.add_node("data_analyst", data_analyst)
        graph.add_node("report_builder_llm", report_builder_llm)
        graph.add_node("report_tools", report_tools)
        graph.add_node("finalize_report", finalize_report)
        
        # Wiring
        graph.add_edge(START, "profile_builder")
        graph.add_conditional_edges(
            "profile_builder",
            lambda state: "END" if not state["profile_complete"] else "data_analyst"
        )
        graph.add_edge("data_analyst", "report_builder_llm")
        graph.add_conditional_edges(
            "report_builder_llm",
            lambda state: "report_tools" if state["messages"][-1].tool_calls else "finalize_report",
            # Safety cap: force finalize if >8 tool calls made (count in messages)
        )
        graph.add_edge("report_tools", "report_builder_llm")  # Loop
        graph.add_edge("finalize_report", END)
        
        return graph

    async def chat(self, message: str, thread_id: str | None = None) -> dict:
        # Same as skeleton: generate thread_id, compile graph with checkpointer
        # BUT: before invoking, if thread_id is given, load profile from DB:
        if thread_id:
            async with AsyncSessionLocal() as session:
                profile_row = await session.execute(
                    select(ClientProfile).where(ClientProfile.conversation_id == thread_id)
                )
                profile_row = profile_row.scalar_one_or_none()
                if profile_row:
                    input_state = {
                        "messages": [HumanMessage(content=message)],
                        "client_profile": client_profile_to_ref(profile_row),
                        "profile_complete": True,
                        "analysis_plan": None,
                        "report": None,
                    }
        else:
            input_state = {
                "messages": [HumanMessage(content=message)],
                "client_profile": None,
                "profile_complete": False,
                "analysis_plan": None,
                "report": None,
            }
        
        # Rest same as skeleton: compile, invoke, return {"thread_id": ..., "state": ...}
```

---

## 6. Chat Routes Update (`src/api/routes/chat.py`)

```python
def _build_chat_response(conversation_id: str, state: dict, created_at=None) -> ChatResponse:
    """Build response, checking if report is present."""
    report = state.get("report")
    if report:
        response_text = "Your demographic report is ready."
    else:
        response_text = _extract_assistant_response(state)
    
    return ChatResponse(
        conversation_id=conversation_id,
        message=MessageResponse(role="assistant", content=response_text),
        created_at=created_at,
        report=report,
    )
```

No other major changes needed — routes already call `ChatAgent().chat()` and `ChatAgent().get_history()`.

---

## Testing Checklist

1. **alembic upgrade head** ✅ (already done)
2. **Profile Builder**:
   - Start conversation with incomplete info → node asks follow-up → no report in response
   - Continue with missing field filled → node completes, persists to DB
   - Query DB → ClientProfile row exists with conversation_id matching thread_id, DemographicTarget rows created
3. **Data Analyst**:
   - Check AnalysisPlan is well-formed (categories populated, geography_level matches scope)
4. **Report Builder**:
   - Make multiple get_aggregation_tool calls → verify tool results are in message transcript
   - Finalize → verify Report object is well-formed, persisted to DB
   - Verify report.model_dump_json() matches the user's example JSON shape
5. **Profile Reload**:
   - Start a third message in the same conversation (post-report)
   - Verify ChatAgent reloaded the profile from DB instead of relying on checkpointed state
6. **Happy Path End-to-End**:
   - Send a complete profile in one message (e.g., "Hi, I'm a fitness center targeting professionals in Atlanta, interested in age 25-45 with $60K-$150K income")
   - Verify all three nodes run in sequence
   - Verify report is generated and returned in response

---

## Prompts to Port (from archived code)

- `src/agents/orchestrator/prompts.py`:
  - `DISCOVERY_PROMPT` → use for profile extraction context
  - `ASK_USER_FOR_MISSING_PREFERENCES` → use when generating follow-up question
  - `DEMOGRAPHIC_EXTRACTION_PROMPT` → use for parsing demographic interests into individual targets
- `src/agents/sql_analyst/prompts.py`:
  - `QUERY_EXTRACTION_PROMPT` → use for Report Builder's tool-calling guidance
  - `SECTION_GROUPING_PROMPT` → use for grouping categories into sections
  - `SUMMARY_NARRATIVE_PROMPT` → use for narrative generation
  - `BUBBLE_CHART_CONFIG_PROMPT` → use for opportunity bubble chart selection

These can be restored as-is from the archive or rewritten fresh.

---

## Current Status
- ✅ DB schema and migrations
- ✅ State models and converters
- ✅ Report schema
- ✅ LocationFilters model
- ✅ GraphState TypedDict
- 🚀 Ready to implement: profile_builder, data_analyst, report_builder nodes
- 🚀 Ready to implement: get_aggregation_tool wrapper
- 🚀 Ready to update: ChatAgent graph wiring, chat routes
