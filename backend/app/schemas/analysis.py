"""Analysis schemas."""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel


class AnalysisRequest(BaseModel):
    """Request to analyze an alert."""
    alert_content: str
    time_range_minutes: int = 30  # Look back time in minutes
    datasource_ids: Optional[List[int]] = None  # Specific datasources to query, None for all


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


class AnalysisResponse(BaseModel):
    """Complete analysis response."""
    id: int
    user_id: int
    alert_content: str
    context_data: Optional[ContextData] = None
    analysis_result: Optional[AnalysisResult] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


class AnalysisListItem(BaseModel):
    """Analysis session list item."""
    id: int
    alert_content: str
    created_at: datetime
    has_result: bool
    
    class Config:
        from_attributes = True
