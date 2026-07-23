"""Pydantic schemas for API requests and responses."""

from src.schemas.aggregation import (
    AggregationResponse,
    AggregationRow,
    GeographyLevel,
)
from src.schemas.chat import (
    ChatResponse,
    ConversationListItem,
    ConversationResponse,
    MessageResponse,
    SendMessageRequest,
    StartConversationRequest,
)
from src.schemas.demographics import (
    CategoryInfo,
    DemographicCategoriesResponse,
    DemographicMetricsResponse,
    MetricInfo,
)
from src.schemas.geography import (
    CBSAListResponse,
    CountyListResponse,
    RegionInfo,
    RegionListResponse,
    ZipListResponse,
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
    # Geography schemas
    "RegionInfo",
    "RegionListResponse",
    "CBSAListResponse",
    "CountyListResponse",
    "ZipListResponse",
    # Demographics schemas
    "MetricInfo",
    "CategoryInfo",
    "DemographicCategoriesResponse",
    "DemographicMetricsResponse",
    # Aggregation schemas
    "GeographyLevel",
    "AggregationRow",
    "AggregationResponse",
    # Report schemas
    "Report",
    "ReportSection",
    "ReportSummary",
    "Visualization",
    "VisualizationConfig",
    "CategoricalDataPoint",
    "DistributionDataPoint",
    "BubbleDataPoint",
]
