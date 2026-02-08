"""DataSource model."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Enum, JSON
from app.database import Base
import enum


class DataSourceType(str, enum.Enum):
    """Supported data source types."""
    ELK = "elk"
    LOKI = "loki"
    PROMETHEUS = "prometheus"


class DataSource(Base):
    """Data source configuration model."""
    
    __tablename__ = "datasources"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    type = Column(
        Enum(DataSourceType, values_callable=lambda x: [e.value for e in x]),
        nullable=False
    )
    host = Column(String(255), nullable=False)
    port = Column(Integer, nullable=False)
    auth_token = Column(String(500), nullable=True)
    config = Column(JSON, nullable=True)  # Additional configuration like index, path, etc.
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<DataSource(id={self.id}, name={self.name}, type={self.type})>"
