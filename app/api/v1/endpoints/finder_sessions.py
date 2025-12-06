# app/api/v1/endpoints/finder_sessions.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.models.finder_sessions import FinderSession
from app.models.entities import Entity

router = APIRouter()


@router.get("/sessions", response_model=List[dict])
async def get_user_finder_sessions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 20
):
    """
    Get all finder sessions for the current user.
    Returns sessions ordered by most recent first.
    """
    sessions = db.query(FinderSession).filter(
        FinderSession.user_id == current_user.id
    ).order_by(
        FinderSession.created_at.desc()
    ).offset(skip).limit(limit).all()
    
    return [session.to_dict() for session in sessions]


@router.get("/sessions/{session_id}", response_model=List[dict])
async def get_finder_session(
    session_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all entities found in a specific finder session, flattened.
    """
    from app.models.finder_session_results import FinderSessionResult
    from app.models.entity_profiles import EntityProfile
    
    # Single query to fetch everything flattened
    results = db.query(
        Entity, 
        EntityProfile, 
        FinderSessionResult,
        FinderSession
    ).join(
        FinderSessionResult, Entity.id == FinderSessionResult.entity_id
    ).join(
        EntityProfile, Entity.id == EntityProfile.entity_id
    ).join(
        FinderSession, FinderSessionResult.session_id == FinderSession.id
    ).filter(
        FinderSession.id == session_id,
        FinderSession.user_id == current_user.id
    ).all()
    
    linked_entities = []
    if results:
        for entity, profile, fs_result, session in results:
            entity_data = {
                "name": entity.name,
                "entity_type": entity.entity_type.value,
                "entity_id": str(entity.id),
                "finder_session_result_id": str(fs_result.id),
                "finder_session_id": str(session.id),
                "email": profile.email,
                "title": profile.title,
                "linkedin_url": profile.linkedin_url,
                "raw_input": session.raw_input,
                "synthesized_query": session.synthesized_query,
                "intent_reasoning": session.intent_reasoning
            }
            linked_entities.append(entity_data)
            
    return linked_entities


@router.delete("/sessions/{session_id}")
async def delete_finder_session(
    session_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a finder session."""
    session = db.query(FinderSession).filter(
        FinderSession.id == session_id,
        FinderSession.user_id == current_user.id
    ).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Finder session not found"
        )
    
    db.delete(session)
    db.commit()
    
    return {"message": "Session deleted successfully"}


@router.post("/sessions/{session_id}/fetch_more")
async def fetch_more_results(
    session_id: UUID,
    page: int = 1,
    per_page: int = 10,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Fetch more results for an existing finder session (pagination).
    Triggers a background task to fetch the next page of results using the same search criteria.
    """
    session = db.query(FinderSession).filter(
        FinderSession.id == session_id,
        FinderSession.user_id == current_user.id
    ).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Finder session not found"
        )
    
    # Determine next page
    current_pagination = session.pagination_state or {"page": 1, "per_page": 10}
    
    # If user didn't specify page, use next page from state
    # Note: We rely on the client to usually track this, but this is a safe fallback
    # or if we want auto-increment logic on server side.
    
    # If the user explicitly passes page=1 (default), we might want to check if they meant "next page"
    # But usually explicit params override.
    
    # Let's implement the requested logic:
    # "check for the past execution... then pass that page & per_page"
    # "Once it fetches it updates in the database" -> This happens in the task
    
    # If the user sends the DEFAULT page=1, we assume they want the NEXT page based on DB state.
    # If they send page > 1, we respect it.
    
    target_page = page
    target_per_page = per_page
    
    if page == 1:
        # Check DB state
        last_page = current_pagination.get("page", 1)
        target_page = last_page + 1
        target_per_page = current_pagination.get("per_page", 10)
        
    # Trigger background task
    from app.agents.tasks import continue_finder_session
    task = continue_finder_session.delay(str(session_id), target_page, target_per_page)
    
    return {
        "message": "Fetching more results started",
        "task_id": str(task.id),
        "session_id": str(session_id),
        "page": target_page,
        "per_page": target_per_page
    }
