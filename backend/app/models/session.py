"""Analysis Session model."""
from datetime import datetime
from sqlalchemy import Column, Integer, Text, DateTime, JSON, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class AnalysisSession(Base):
    """Alert analysis session model."""
    
    __tablename__ = "sessions"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    alert_content = Column(Text, nullable=False)
    context_data = Column(JSON, nullable=True)  # Collected logs and metrics
    analysis_result = Column(JSON, nullable=True)  # LLM analysis result
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", backref="sessions")
    
    def __repr__(self):
        return f"<AnalysisSession(id={self.id}, user_id={self.user_id})>"
