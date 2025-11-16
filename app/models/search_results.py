# app/models/search/search_results.py
import uuid
from sqlalchemy import Column, DateTime, ForeignKey, Integer, Float, JSON
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class SearchResult(Base):
    __tablename__ = "search_results"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    search_id = Column(UUID(as_uuid=True), ForeignKey("searches.id", ondelete="CASCADE"), nullable=False)
    entity_id = Column(UUID(as_uuid=True), ForeignKey("entities.id", ondelete="CASCADE"), nullable=False)

    rank = Column(Integer, nullable=True)
    score = Column(Float, nullable=True)

    # Optional: store raw payload from provider used during this search
    raw_payload = Column(JSONB, default=dict)

    created_at = Column(DateTime, default=datetime.utcnow)

    search = relationship("Search", back_populates="results")
    entity = relationship("Entity")
