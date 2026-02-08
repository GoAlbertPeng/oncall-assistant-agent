"""Ticket schemas."""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel
from app.models.ticket import TicketLevel, TicketStatus


class TicketCreate(BaseModel):
    """Schema for creating a ticket."""
    session_id: Optional[int] = None
    title: str
    root_cause: Optional[str] = None
    level: TicketLevel = TicketLevel.P3


class TicketUpdate(BaseModel):
    """Schema for updating a ticket."""
    title: Optional[str] = None
    root_cause: Optional[str] = None
    level: Optional[TicketLevel] = None
    status: Optional[TicketStatus] = None


class TicketResponse(BaseModel):
    """Ticket response schema."""
    ticket_no: str
    session_id: Optional[int] = None
    handler_id: int
    title: str
    root_cause: Optional[str] = None
    level: TicketLevel
    status: TicketStatus
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
