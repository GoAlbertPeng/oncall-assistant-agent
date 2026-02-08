"""Ticket schemas."""
from datetime import datetime
from typing import Optional, List, Literal
from pydantic import BaseModel


# Use literal types to match database enum values
TicketLevelType = Literal["P1", "P2", "P3"]
TicketStatusType = Literal["new", "processing", "closed"]


class TicketCreate(BaseModel):
    """Schema for creating a ticket."""
    session_id: Optional[int] = None
    title: str
    root_cause: Optional[str] = None
    ai_analysis: Optional[str] = None  # AI分析结果
    level: TicketLevelType = "P3"


class TicketUpdate(BaseModel):
    """Schema for updating a ticket."""
    title: Optional[str] = None
    root_cause: Optional[str] = None
    ai_analysis: Optional[str] = None
    level: Optional[TicketLevelType] = None
    status: Optional[TicketStatusType] = None


class TicketResponse(BaseModel):
    """Ticket response schema."""
    ticket_no: str
    session_id: Optional[int] = None
    handler_id: int
    title: str
    root_cause: Optional[str] = None
    ai_analysis: Optional[str] = None
    level: TicketLevelType
    status: TicketStatusType
    created_at: datetime
    closed_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class TicketListResponse(BaseModel):
    """Paginated ticket list response."""
    items: List[TicketResponse]
    total: int
    page: int
    page_size: int
