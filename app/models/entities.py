# app/models/entities.py
import uuid
from sqlalchemy import Column, String, JSON, DateTime, Enum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base
import enum


class EntityType(enum.Enum):
    PERSON = "person"
    COMPANY = "company"
    INVESTOR = "investor"
    FUND = "fund"
    PRODUCT = "product"
    ORGANIZATION = "organization"


class Entity(Base):
    __tablename__ = "entities"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_type = Column(Enum(EntityType), nullable=False)
    name = Column(String, nullable=False)

    # Minimal canonical identity (name, domain, email, etc.)
    canonical_profile = Column(JSONB, default=dict)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    sources = relationship("EntitySource", back_populates="entity", cascade="all, delete-orphan")
    profiles = relationship("EntityProfile", back_populates="entity", cascade="all, delete-orphan")
