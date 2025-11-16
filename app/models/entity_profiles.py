# app/models/entity_profiles.py
import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, Float
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class EntityProfile(Base):
    __tablename__ = "entity_profiles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    entity_id = Column(UUID(as_uuid=True), ForeignKey("entities.id", ondelete="CASCADE"), nullable=False)

    # Flattened attributes (cleaned + normalized)
    name = Column(String)
    title = Column(String)
    email = Column(String)
    phone = Column(String)
    company_name = Column(String)
    company_domain = Column(String)
    location = Column(String)
    industry = Column(String)
    employee_count = Column(Integer)
    revenue = Column(Float)
    linkedin_url = Column(String)
    website_url = Column(String)

    # Additional flexible attributes
    data = Column(JSONB, default=dict)

    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    entity = relationship("Entity", back_populates="profiles")
