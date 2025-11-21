from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app import crud
from app.schemas.search import Search, SearchWithResults, SearchResult

router = APIRouter()

@router.get("/get_recent_searches")
async def get_recent_searches(
    limit: int = 10,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get the most recent searches for the current user.
    Returns:
        {
            "data": [
                {
                    "id": "uuid",
                    "user_id": "uuid",
                    "query": "search query",
                    "filters": {},
                    "created_at": "datetime",
                    "updated_at": "datetime"
                }
            ],
            "status": true,
            "message": "Recent searches retrieved successfully"
        }
    """
    try:
        searches = crud.get_recent_searches(
            db=db,
            user_id=current_user.id,
            limit=limit
        )
        
        # Transform the results to match the Search schema
        search_results = [
            Search(
                id=search['id'],
                user_id=current_user.id,
                query=search['query'],
                filters=search['filters'],
                created_at=search['created_at'],
                updated_at=search.get('updated_at', search['created_at'])
            ).dict()
            for search in searches
        ]
        
        return {
            "data": search_results,
            "status": True,
            "message": "Recent searches retrieved successfully"
        }
        
    except Exception as e:
        # Log the error for debugging
        print(f"Error in get_recent_searches: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "data": [],
                "status": False,
                "message": f"Error retrieving recent searches: {str(e)}"
            }
        )

@router.get("/get_all_searches")
async def get_all_searches(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get all searches for the current user with pagination.
    
    - **skip**: Number of records to skip (for pagination)
    - **limit**: Maximum number of records to return (for pagination)
    """
    try:
        searches = crud.search.get_user_searches(
            db=db,
            user_id=current_user.id,
            skip=skip,
            limit=limit
        )
        
        search_results = [
            Search(
                id=search['id'],
                user_id=current_user.id,
                query=search['query'],
                filters=search['filters'],
                created_at=search['created_at'],
                updated_at=search.get('updated_at', search['created_at'])
            ).dict()
            for search in searches
        ]

        return {
            "data": search_results,
            "status": True,
            "message": "All searches retrieved successfully"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "data": [],
                "status": False,
                "message": f"Error retrieving all searches: {str(e)}"
            }
        )

@router.get("/{search_id}")
async def get_search_by_id(
    search_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get a specific search by ID with all its results and entity details.
    
    - **search_id**: The UUID of the search to retrieve
    
    Returns:
        {
            "data": {
                "id": "uuid",
                "user_id": "uuid",
                "query": "search query",
                "filters": {},
                "created_at": "datetime",
                "updated_at": "datetime",
                "results": [...]
            },
            "status": true,
            "message": "Search retrieved successfully"
        }
    """
    try:
        search_with_results = crud.search.get_search_with_results(
            db=db,
            search_id=search_id,
            user_id=current_user.id
        )

        if not search_with_results:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "data": None,
                    "status": False,
                    "message": "Search not found or access denied"
                }
            )
            
        return {
            "data": search_with_results,
            "status": True,
            "message": "Search retrieved successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in get_search_by_id: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "data": None,
                "status": False,
                "message": f"Error retrieving search: {str(e)}"
            }
        )


@router.get("/entities/unique")
async def get_unique_entities(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get all unique entities from the user's search history.
    
    - **skip**: Number of records to skip (for pagination)
    - **limit**: Maximum number of records to return (for pagination)
    """
    try:
        # Get unique entities
        entities = crud.get_unique_entities_from_searches(
            db=db,
            user_id=current_user.id,
            skip=skip,
            limit=limit
        )
        
        # Get total count using the new function
        total_count = crud.get_unique_entities_count(
            db=db,
            user_id=current_user.id
        )

        return {
            "data": entities,
            "status": True,
            "message": "Unique entities retrieved successfully",
            "pagination": {
                "total": total_count,
                "skip": skip,
                "limit": limit
            }
        }
        
    except Exception as e:
        print(f"Error in get_unique_entities: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "data": [],
                "status": False,
                "message": f"Error retrieving unique entities: {str(e)}"
            }
        )