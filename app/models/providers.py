# app/models/providers.py
import uuid
from sqlalchemy import Column, String, JSON, DateTime
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
from app.database import Base

class Provider(Base):
    __tablename__ = "providers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, unique=True, nullable=False, index=True)
    base_url = Column(String, nullable=True)
    provider_metadata = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
