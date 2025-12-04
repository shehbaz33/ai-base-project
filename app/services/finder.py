# app/services/finder.py

from sqlalchemy.orm import Session
from datetime import datetime
import uuid

from app.models.finder_sessions import FinderSession


def create_finder_session(
    db: Session,
    user_id: str,
    task_id: str,
    raw_input: str,
    intent_type: str = None,
    intent_confidence: float = None,
    intent_reasoning: str = None,
    product_understanding: dict = None,
    icp_profile: dict = None,
    personas: list = None,
    discovery_queries: dict = None,
    scraped_content: str = None,
    follow_up_questions: list = None,
) -> FinderSession:
    """
    Create a new finder session in the database.
    """
    session = FinderSession(
        id=uuid.uuid4(),
        user_id=uuid.UUID(user_id) if user_id else None,
        task_id=task_id,
        raw_input=raw_input,
        intent_type=intent_type,
        intent_confidence=intent_confidence,
        intent_reasoning=intent_reasoning,
        product_understanding=product_understanding or {},
        icp_profile=icp_profile or {},
        personas=personas or [],
        discovery_queries=discovery_queries or {},
        scraped_content=scraped_content,
        status="processing",
        follow_up_questions=follow_up_questions or [],
        created_at=datetime.utcnow()
    )
    
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def update_finder_session_query(
    db: Session,
    session: FinderSession,
    synthesized_query: str
) -> FinderSession:
    """
    Update the synthesized query for a finder session.
    """
    session.synthesized_query = synthesized_query
    db.commit()
    db.refresh(session)
    return session


def update_finder_session_status(
    db: Session,
    session: FinderSession,
    status: str
) -> FinderSession:
    """
    Update the status of a finder session.
    Status can be: processing, completed, failed, needs_clarification
    """
    session.status = status
    session.completed_at = datetime.utcnow()
    db.commit()
    db.refresh(session)
    return session
