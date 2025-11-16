# app/models/entity_sources.py
import uuid
from sqlalchemy import Column, String, JSON, DateTime, ForeignKey, Float
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class EntitySource(Base):
    __tablename__ = "entity_sources"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    entity_id = Column(UUID(as_uuid=True), ForeignKey("entities.id", ondelete="CASCADE"), nullable=False)
    provider = Column(String, nullable=False)  # 'apollo', 'clearbit', 'pdls' ...
    provider_entity_id = Column(String, nullable=False)

    raw_data = Column(JSONB, nullable=False)
    confidence_score = Column(Float, default=1.0)

    created_at = Column(DateTime, default=datetime.utcnow)

    entity = relationship("Entity", back_populates="sources")
