# app/models/search/searches.py
import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class Search(Base):
    __tablename__ = "searches"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    query = Column(String, nullable=False)

    # Optional structured filters
    filters = Column(JSONB, default=dict)

    created_at = Column(DateTime, default=datetime.utcnow)

    results = relationship("SearchResult", back_populates="search", cascade="all, delete-orphan")
