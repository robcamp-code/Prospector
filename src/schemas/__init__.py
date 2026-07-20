"""Pydantic schemas for API requests and responses."""

from src.schemas.charts import (
    AggregatedStatistics,
    Chart,
    ChartConfig,
    ChartDataPoint,
    DemographicReportData,
    DemographicSection,
    OpportunityDataPoint,
)
from src.schemas.chat import (
    ChatResponse,
    ClientProfileSummary,
    ConversationListItem,
    ConversationResponse,
    MessageResponse,
    SendMessageRequest,
    StartConversationRequest,
)
from src.schemas.report import (
    BubbleDataPoint,
    CategoricalDataPoint,
    DistributionDataPoint,
    Report,
    ReportSection,
    ReportSummary,
    Visualization,
    VisualizationConfig,
)

__all__ = [
    # Chat schemas
    "StartConversationRequest",
    "SendMessageRequest",
    "MessageResponse",
    "ConversationResponse",
    "ChatResponse",
    "ConversationListItem",
    "ClientProfileSummary",
    # Chart schemas (legacy)
    "ChartDataPoint",
    "ChartConfig",
    "Chart",
    "DemographicSection",
    "OpportunityDataPoint",
    "AggregatedStatistics",
    "DemographicReportData",
    # Report schemas
    "CategoricalDataPoint",
    "DistributionDataPoint",
    "BubbleDataPoint",
    "VisualizationConfig",
    "Visualization",
    "ReportSection",
    "ReportSummary",
    "Report",
]
