"""Analysis schemas."""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel


class AnalysisRequest(BaseModel):
    """Request to analyze an alert."""
    alert_content: str
    time_range_minutes: int = 30  # Look back time in minutes
    datasource_ids: Optional[List[int]] = None  # Specific datasources to query, None for all


class ContinueAnalysisRequest(BaseModel):
    """Request to continue analysis with follow-up."""
    message: str  # User's follow-up message
    

class LogEntry(BaseModel):
    """A single log entry."""
    timestamp: str
    level: str
    message: str
    source: Optional[str] = None


class MetricDataPoint(BaseModel):
    """A single metric data point."""
    timestamp: str
    value: float
    metric_name: str


class ContextData(BaseModel):
    """Collected context data from data sources."""
    logs: List[LogEntry] = []
    metrics: List[Dict[str, Any]] = []
    collection_status: Dict[str, str] = {}  # datasource_id -> status


class AnalysisResult(BaseModel):
    """LLM analysis result."""
    root_cause: str
    evidence: str
    category: str  # code_issue, config_issue, resource_bottleneck, dependency_failure
    temporary_solution: str
    permanent_solution: str
    confidence: Optional[float] = None


class IntentResult(BaseModel):
    """Parsed intent from alert content."""
    summary: str  # Brief summary of the alert
    alert_type: str  # Type: performance, error, availability, etc.
    affected_system: Optional[str] = None  # Affected system/service
    keywords: List[str] = []  # Extracted keywords for searching
    suggested_metrics: List[str] = []  # Suggested metrics to query


class ConversationMessage(BaseModel):
    """A message in the analysis conversation."""
    role: str  # user, assistant, system
    content: str
    timestamp: str
    stage: Optional[str] = None  # Which analysis stage produced this
    data: Optional[Dict[str, Any]] = None  # Additional structured data


class AnalysisResponse(BaseModel):
    """Complete analysis response."""
    id: int
    user_id: int
    alert_content: str
    status: str = "pending"
    current_stage: Optional[str] = None
    intent: Optional[IntentResult] = None
    context_data: Optional[ContextData] = None
    analysis_result: Optional[AnalysisResult] = None
    messages: List[ConversationMessage] = []
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class AnalysisListItem(BaseModel):
    """Analysis session list item."""
    id: int
    alert_content: str
    status: str
    created_at: datetime
    has_result: bool
    
    class Config:
        from_attributes = True


class StreamEvent(BaseModel):
    """Server-Sent Event for streaming analysis."""
    event: str  # stage_start, stage_progress, stage_complete, message, error, done
    stage: Optional[str] = None
    content: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    progress: Optional[int] = None  # 0-100
