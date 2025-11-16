# app/api/v1/endpoints/search.py
from typing import List
from app.api.deps import get_current_user
from app.database import get_db
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.models.user import User
from app import crud
from app.schemas.search import SearchResult

router = APIRouter()

@router.get("/history", response_model=List[SearchResult])
def get_search_history(
    skip: int = 0,
    limit: int = 10,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve search history for the current user."""
    search_results = crud.search.get_user_search_results(
        db, user_id=current_user.id, skip=skip, limit=limit
    )
    return search_results

@router.get("/{search_id}", response_model=SearchResult)
def get_search_result(
    search_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific search result by ID."""
    search_result = crud.search.get_search_result_with_entities(
        db, search_id=search_id, user_id=current_user.id
    )
    if not search_result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Search result not found"
        )
    return search_result