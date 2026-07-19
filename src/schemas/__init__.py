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

__all__ = [
    # Chat schemas
    "StartConversationRequest",
    "SendMessageRequest",
    "MessageResponse",
    "ConversationResponse",
    "ChatResponse",
    "ConversationListItem",
    "ClientProfileSummary",
    # Chart schemas
    "ChartDataPoint",
    "ChartConfig",
    "Chart",
    "DemographicSection",
    "OpportunityDataPoint",
    "AggregatedStatistics",
    "DemographicReportData",
]
