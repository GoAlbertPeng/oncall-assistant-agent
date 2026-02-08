"""Ticket model."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Enum, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base
import enum


class TicketLevel(str, enum.Enum):
    """Ticket severity levels."""
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


class TicketStatus(str, enum.Enum):
    """Ticket status values."""
    NEW = "new"
    PROCESSING = "processing"
    CLOSED = "closed"


class Ticket(Base):
    """Ticket model for incident management."""
    
    __tablename__ = "tickets"
    
    ticket_no = Column(String(20), primary_key=True)  # OC + date + sequence
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=True)
    handler_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(255), nullable=False)
    root_cause = Column(Text, nullable=True)
    ai_analysis = Column(Text, nullable=True)  # AI分析结果
    level = Column(Enum('P1', 'P2', 'P3', name='ticketlevel'), default='P3')
    status = Column(Enum('new', 'processing', 'closed', name='ticketstatus'), default='new')
    created_at = Column(DateTime, default=datetime.utcnow)
    closed_at = Column(DateTime, nullable=True)
    
    # Relationships
    session = relationship("AnalysisSession", backref="tickets")
    handler = relationship("User", backref="handled_tickets")
    
    def __repr__(self):
        return f"<Ticket(ticket_no={self.ticket_no}, status={self.status})>"
