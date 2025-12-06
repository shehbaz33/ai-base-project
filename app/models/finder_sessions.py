# app/models/finder_sessions.py
import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey, Float, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class FinderSession(Base):
    """
    Stores the complete state of a Finder Agent execution.
    This allows users to revisit and reuse the analysis for finding similar people/companies.
    """
    __tablename__ = "finder_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # User who initiated the search
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    # Task ID from Celery (for tracking)
    task_id = Column(String, unique=True, nullable=False, index=True)
    
    # Original user input
    raw_input = Column(Text, nullable=False)
    
    # Detected intent
    intent_type = Column(String, nullable=True)  # e.g., "selling_product", "investor_search"
    intent_confidence = Column(Float, nullable=True)
    intent_reasoning = Column(Text, nullable=True)
    
    # Product/Entity understanding (JSONB for flexible schema)
    product_understanding = Column(JSONB, default=dict)
    # Contains: entity_name, core_value_prop, pain_points_solved, beneficiaries, ideal_industries
    
    # ICP Profile
    icp_profile = Column(JSONB, default=dict)
    # Contains: industry, company_size, budget_signals, etc.
    
    # Buyer Personas
    personas = Column(JSONB, default=list)
    # List of personas with titles, responsibilities, pain_points
    
    # Discovery queries/plan
    discovery_queries = Column(JSONB, default=dict)
    # The generated discovery plan for Apollo
    
    # Synthesized Apollo query (the final optimized query)
    synthesized_query = Column(Text, nullable=True)

    # Results from Apollo
    results = Column(JSONB, default=list)
    
    # Scraped content (if URL was provided)
    scraped_content = Column(Text, nullable=True)
    
    # Status of the session
    status = Column(String, default="processing")  # processing, completed, failed, needs_clarification
    
    # Follow-up questions (if clarification needed)
    follow_up_questions = Column(JSONB, default=list)

    # Actual Apollo Query Parameters used (for pagination/re-use)
    apollo_query_params = Column(JSONB, default=dict)
    
    # Pagination state
    pagination_state = Column(JSONB, default=lambda: {"page": 1, "per_page": 10})
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    
    # Relationship to user
    user = relationship("User", back_populates="finder_sessions")
    
    # Relationship to results
    session_results = relationship("FinderSessionResult", back_populates="session", cascade="all, delete-orphan")
    
    def to_dict(self):
        """Convert to dictionary for API responses"""
        execution_time = None
        if self.completed_at and self.created_at:
            execution_time = (self.completed_at - self.created_at).total_seconds()

        entities_fetched = 0
        if self.results and isinstance(self.results, list):
            entities_fetched = len(self.results)

        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "task_id": self.task_id,
            "raw_input": self.raw_input,
            "intent_type": self.intent_type,
            "intent_confidence": self.intent_confidence,
            "product_understanding": self.product_understanding,
            "icp_profile": self.icp_profile,
            "personas": self.personas,
            "discovery_queries": self.discovery_queries,
            "synthesized_query": self.synthesized_query,
            "apollo_query_params": self.apollo_query_params,
            "pagination_state": self.pagination_state,
            "results": entities_fetched,
            "metrics": {
                "execution_time_seconds": execution_time,
                "entities_fetched": entities_fetched
            },
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }
