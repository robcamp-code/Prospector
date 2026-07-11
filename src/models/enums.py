"""Enumeration types for the Prospector system."""

from enum import Enum


class ServiceType(str, Enum):
    """Type of service offered (B2B, B2C, or both)."""

    B2B = "b2b"
    B2C = "b2c"
    BOTH = "both"
    UNKNOWN = "unknown"


class DeliverableVisibility(str, Enum):
    """Visibility type of deliverables."""

    VISUAL = "visual"
    TECHNICAL = "technical"
    MIXED = "mixed"
    UNKNOWN = "unknown"


class SalesCycle(str, Enum):
    """
    The type of sales cycle the service provider has.

    Transactional - high velocity, think photographer or hair cut service
    Considered - Need to establish trust before the buyer picks your services.
    Building an MVP or a platform will require more than one phone call most likely
    """

    TRANSACTIONAL = "transactional"
    CONSIDERED = "considered"
    UNKNOWN = "unknown"


class TargetClientSize(str, Enum):
    """Target client company size."""

    SOLO = "solo"
    SMB = "smb"
    MID_MARKET = "mid_market"
    ENTERPRISE = "enterprise"
    UNKNOWN = "unknown"


class GeographyScope(str, Enum):
    """Where the user services must be performed."""

    LOCAL = "local"
    REGIONAL = "regional"
    REMOTE_GLOBAL = "remote_global"
    UNKNOWN = "unknown"


class ContentCapacity(str, Enum):
    """Content creation capacity."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    UNKNOWN = "unknown"


class SourceType(str, Enum):
    """Source of persona information."""

    QUESTIONNAIRE = "questionnaire"
    FILE_UPLOAD = "file_upload"
    UNKNOWN = "unknown"
