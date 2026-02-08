"""DataSource schemas."""
from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel
from app.models.datasource import DataSourceType


class DataSourceCreate(BaseModel):
    """Schema for creating a data source."""
    name: str
    type: DataSourceType
    host: str
    port: int
    auth_token: Optional[str] = None
    config: Optional[Dict[str, Any]] = None  # index_name for ELK, labels for Loki, etc.


class DataSourceUpdate(BaseModel):
    """Schema for updating a data source."""
    name: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = None
    auth_token: Optional[str] = None
    config: Optional[Dict[str, Any]] = None


class DataSourceResponse(BaseModel):
    """Data source response schema."""
    id: int
    name: str
    type: DataSourceType
    host: str
    port: int
    auth_token: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class DataSourceTestResponse(BaseModel):
    """Response for data source connection test."""
    success: bool
    message: str
    latency_ms: Optional[float] = None
