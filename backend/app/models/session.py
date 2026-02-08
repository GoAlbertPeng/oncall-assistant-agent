"""Analysis Session model with conversation support."""
from datetime import datetime
from sqlalchemy import Column, Integer, Text, DateTime, JSON, ForeignKey, String, Enum as SQLEnum
from sqlalchemy.orm import relationship
from app.database import Base
import enum


class AnalysisStatus(enum.Enum):
    """Analysis session status."""
    PENDING = "pending"
    INTENT_UNDERSTANDING = "intent_understanding"
    DATA_COLLECTION = "data_collection"
    LLM_ANALYSIS = "llm_analysis"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    ERROR = "error"


class MessageRole(enum.Enum):
    """Message role in conversation."""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class AnalysisSession(Base):
    """Alert analysis session model with conversation history."""
    
    __tablename__ = "sessions"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    alert_content = Column(Text, nullable=False)
    context_data = Column(JSON, nullable=True)  # Collected logs and metrics
    analysis_result = Column(JSON, nullable=True)  # LLM analysis result
    
    # New fields for conversation support
    status = Column(String(50), default="pending")  # Analysis status
    messages = Column(JSON, default=list)  # Conversation messages list
    intent = Column(JSON, nullable=True)  # Parsed intent from alert
    current_stage = Column(String(50), nullable=True)  # Current analysis stage
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", backref="sessions")
    
    def __repr__(self):
        return f"<AnalysisSession(id={self.id}, user_id={self.user_id}, status={self.status})>"
    
    def add_message(self, role: str, content: str, stage: str = None, data: dict = None):
        """Add a message to the conversation."""
        if self.messages is None:
            self.messages = []
        
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow().isoformat(),
        }
        if stage:
            message["stage"] = stage
        if data:
            message["data"] = data
        
        # Create new list to trigger SQLAlchemy change detection
        self.messages = self.messages + [message]
