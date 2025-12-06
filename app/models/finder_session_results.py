# app/models/finder_session_results.py
import uuid
from sqlalchemy import Column, DateTime, ForeignKey, Integer, Float, JSON
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class FinderSessionResult(Base):
    __tablename__ = "finder_session_results"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    session_id = Column(UUID(as_uuid=True), ForeignKey("finder_sessions.id", ondelete="CASCADE"), nullable=False)
    entity_id = Column(UUID(as_uuid=True), ForeignKey("entities.id", ondelete="CASCADE"), nullable=False)

    # Optional: Rank in the search results
    rank = Column(Integer, nullable=True)
    
    # Optional: Relevance score if available
    score = Column(Float, nullable=True)

    # Optional: Store specific metadata about why this result matched this session
    match_reasoning = Column(JSONB, default=dict)

    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("FinderSession", back_populates="session_results")
    entity = relationship("Entity")
