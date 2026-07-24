# Multi-Node Chat Agent Architecture

## System Flow Diagram

```mermaid
graph TD
    Start([START: User Message]) --> PB["<b>Profile Builder</b><br/>(SubAgent)<br/>———<br/>Extract Preferences<br/>Validate Completeness"]
    
    PB -->|incomplete| PB_Ask["Ask Follow-up<br/>Question"]
    PB_Ask --> PB_End([END])
    
    PB -->|complete| PB_Persist["Persist to DB:<br/>ClientProfile +<br/>DemographicTarget rows"]
    PB_Persist --> DA["<b>Data Analyst</b><br/>(SubAgent)<br/>———<br/>Resolve Location<br/>Select Categories<br/>Pick Geography Level"]
    
    DA --> DA_LLM["LLM: Extract<br/>LocationFilters"]
    DA_LLM --> DA_Logic["Deterministic:<br/>_select_categories<br/>_pick_geography_level"]
    DA_Logic --> DA_Plan["Build AnalysisPlan:<br/>location + categories<br/>+ geography_level"]
    DA_Plan --> RB["<b>Report Builder Loop</b><br/>(3 sub-nodes)"]
    
    RB --> RB_LLM["<b>ReportBuilderLLM</b><br/>(SubAgent)<br/>———<br/>LLM + Tools"]
    
    RB_LLM -->|has tool calls| RB_Check{"Tool Call<br/>Count < 8?"}
    RB_LLM -->|no tool calls| RB_Final
    
    RB_Check -->|yes| RB_Tools["<b>ReportToolExecutor</b><br/>(Non-SubAgent)<br/>———<br/>Execute: get_aggregation_tool<br/>Return ToolMessage results"]
    RB_Check -->|no| RB_Final
    
    RB_Tools --> RB_Loop["Append results<br/>to messages"]
    RB_Loop --> RB_LLM
    
    RB_Final["<b>FinalizeReport</b><br/>(SubAgent)<br/>———<br/>LLM: structured output<br/>Generate Report schema"]
    RB_Final --> RB_Persist["Persist to DB:<br/>Report (JSONB)"]
    RB_Persist --> End([END: Return Report])
    
    classDef subagentstyle fill:#4a90e2,stroke:#2c5aa0,stroke-width:2px,color:#fff
    classDef executestyle fill:#f39c12,stroke:#d68910,stroke-width:2px,color:#fff
    classDef llmstyle fill:#7cb342,stroke:#558b2f,stroke-width:2px,color:#fff
    classDef dbstyle fill:#ab47bc,stroke:#7b1fa2,stroke-width:2px,color:#fff
    classDef endstyle fill:#26a69a,stroke:#00695c,stroke-width:2px,color:#fff
    
    class PB,DA,RB_LLM,RB_Final subagentstyle
    class RB_Tools executestyle
    class DA_LLM,RB_LLM llmstyle
    class PB_Persist,RB_Persist dbstyle
    class Start,PB_End,End endstyle
```

## State Flow & Package Structure

```mermaid
graph LR
    subgraph "Input State"
        Messages["messages: list"]
        Profile["client_profile:<br/>ClientProfileRef | None"]
        ProfileComplete["profile_complete: bool"]
    end
    
    subgraph "Profile Builder Package"
        PBNode["ProfileBuilder(SubAgent)<br/>+ Preferences model<br/>+ _match_demographic_key"]
        PBPrompts["prompts.py<br/>DISCOVERY_PROMPT<br/>ASK_USER_FOR_MISSING_PREFERENCES"]
        PBNode -.-> PBPrompts
    end
    
    subgraph "Data Analyst Package"
        DANode["DataAnalyst(SubAgent)<br/>+ _select_categories<br/>+ _pick_geography_level"]
        DAPrompts["prompts.py<br/>LOCATION_EXTRACTION_PROMPT"]
        DANode -.-> DAPrompts
    end
    
    subgraph "Report Builder Package"
        RBLLMNode["ReportBuilderLLM(SubAgent)"]
        RBToolNode["ReportToolExecutor<br/>(Non-SubAgent)"]
        RBFinalNode["FinalizeReport(SubAgent)"]
        RBPrompts["prompts.py<br/>REPORT_BUILDER_CONTEXT_PROMPT<br/>FINALIZE_REPORT_PROMPT"]
        RBLLMNode -.-> RBPrompts
        RBFinalNode -.-> RBPrompts
    end
    
    subgraph "Base Infrastructure"
        SubAgentBase["SubAgent(ABC)<br/>in base.py<br/>———<br/>__init__: self.llm<br/>__call__: abstract"]
        RunnableConfig["RunnableConfig<br/>from langchain_core"]
    end
    
    subgraph "Output State"
        AnalysisPlan["analysis_plan: AnalysisPlan | None"]
        Report["report: Report | None"]
    end
    
    Messages --> PBNode
    Profile --> PBNode
    ProfileComplete --> PBNode
    
    PBNode --> DANode
    DANode --> RBLLMNode
    RBLLMNode --> RBToolNode
    RBToolNode --> RBLLMNode
    RBLLMNode --> RBFinalNode
    
    RBFinalNode --> Report
    DANode --> AnalysisPlan
    
    PBNode -.-> SubAgentBase
    DANode -.-> SubAgentBase
    RBLLMNode -.-> SubAgentBase
    RBFinalNode -.-> SubAgentBase
    
    SubAgentBase -.-> RunnableConfig
```

## Database Schema

```mermaid
graph LR
    subgraph "ClientProfile Table"
        CP["id (PK)<br/>conversation_id (UK)<br/>name<br/>business_type<br/>service_description<br/>location_preference<br/>target_income_min<br/>target_income_max"]
    end
    
    subgraph "DemographicTarget Table"
        DT["id (PK)<br/>client_profile_id (FK)<br/>demographic_key<br/>constraint_type<br/>min_value<br/>max_value<br/>importance_weight"]
    end
    
    subgraph "Report Table"
        R["id (PK)<br/>client_profile_id (FK)<br/>conversation_id<br/>title<br/>subtitle<br/>geography_type<br/>geography_value<br/>summary (JSONB)<br/>sections (JSONB)"]
    end
    
    CP -->|1:N| DT
    CP -->|1:N| R
```

## Tool Integration

```mermaid
graph TD
    LLM["ReportBuilderLLM<br/>(bound with tool)"]
    Tool["get_aggregation_tool<br/>(@tool decorator)<br/>———<br/>Async wrapper<br/>over get_aggregation service"]
    
    Service["get_aggregation service<br/>(src/core/services/zips)"]
    DB["Database:<br/>uszips table"]
    
    LLM -->|bind_tools| Tool
    Tool -->|ainvoke| Service
    Service -->|query| DB
    
    Tool -->|returns| JSON["JSON string:<br/>AggregationResponse"]
    JSON -->|appended to| Messages["message history<br/>as ToolMessage"]
    
    classDef toolstyle fill:#e74c3c,stroke:#c0392b,stroke-width:2px,color:#fff
    classDef servicestyle fill:#3498db,stroke:#2980b9,stroke-width:2px,color:#fff
    classDef datastyle fill:#2ecc71,stroke:#27ae60,stroke-width:2px,color:#fff
    
    class Tool toolstyle
    class Service servicestyle
    class DB datastyle
```

## Key Design Decisions

| Aspect | Choice | Rationale |
|--------|--------|-----------|
| **Node Architecture** | SubAgent(ABC) base class | Eliminates LLM duplication; __call__ makes instances directly usable as LangGraph nodes |
| **Packaging** | Per-agent packages | Each agent owns its node, prompts, and helpers; clean separation of concerns |
| **Prompts** | Templates + .format() | No f-string reassembly in node bodies; prompts stay in prompts.py; readable call sites |
| **Bounded ReAct Loop** | 8-call safety cap | Prevents runaway LLM tool calls; deterministic completion path |
| **Report Storage** | JSONB (immutable) | No relational breakdown needed; reports are snapshots; fast queries without JOINs |
| **Profile Reload** | DB as source of truth | Checkpointer is authoritative for messages; DB is authoritative for committed profiles (guards against schema drift) |
| **Location Resolution** | Data Analyst node | Separates concerns: Profile Builder asks business questions; Data Analyst resolves geography for querying |

