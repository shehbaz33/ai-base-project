# app/api/v1/endpoints/finder_sessions.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.models.finder_sessions import FinderSession

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


@router.get("/sessions/{session_id}", response_model=dict)
async def get_finder_session(
    session_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get a specific finder session by ID.
    Can be used to rerun searches with the same parameters.
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
    
    return session.to_dict()


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
