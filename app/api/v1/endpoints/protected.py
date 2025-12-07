from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Any, Dict

from app.api.deps import get_db, get_current_user
from app.crud import user as user_crud
from app.schemas.user import User, UserInDB
from app.models.user import User as UserModel
from app.utils.api_response import create_api_response

router = APIRouter()

@router.get("/test-protected")
async def test_protected_route(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> dict:
    """
    Test protected route that requires authentication.
    Returns basic user information if authenticated.
    
    Args:
        current_user: The authenticated user
        db: Database session
        
    Returns:
        Dict with user information and success message
    """
    # Get fresh user data from the database
    db_user = user_crud.get_user(db, user_id=current_user.id)
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return create_api_response(
        data={
            "user_id": str(db_user.id),
            "email": db_user.email,
            "is_active": db_user.is_active,
            "full_name": db_user.full_name,
            "is_superuser": db_user.is_superuser if hasattr(db_user, 'is_superuser') else False
        },
        message="You have successfully accessed the protected route!"
    )

@router.get("/users/me", response_model=dict)
async def read_users_me(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> dict:
    """
    Get current user information with full user details.
    
    Args:
        current_user: The authenticated user
        db: Database session
        
    Returns:
        UserInDB: Full user information
    """
    # Get fresh user data from the database
    db_user = user_crud.get_user(db, user_id=current_user.id)
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return create_api_response(data=db_user, message="User details retrieved")

@router.get("/users/", response_model=dict)
async def read_users(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> dict:
    """
    Retrieve all users (admin only).
    
    Args:
        skip: Number of records to skip (for pagination)
        limit: Maximum number of records to return
        db: Database session
        current_user: The authenticated user
        
    Returns:
        List of users
    """
    users = user_crud.get_users(db, skip=skip, limit=limit)
    return create_api_response(data=users, message="Users retrieved")
