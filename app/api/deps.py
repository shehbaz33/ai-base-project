from typing import Generator, Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.orm import Session

from app.core.security import verify_token
from app.database import SessionLocal
from app.models.user import User
from app.schemas.user import TokenType
from app.core.exceptions import (
    InvalidTokenException,
    InactiveUserException,
    PermissionDeniedException
)

# OAuth2 scheme for token authentication
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login")


def get_db() -> Generator:
    """Dependency function that yields db sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
) -> User:
    """
    Dependency to get the current user from the JWT token.
    
    Args:
        db: Database session
        token: JWT token from Authorization header
        
    Returns:
        User: The authenticated user
        
    Raises:
        HTTPException: If the token is invalid, expired, or user not found
    """
    try:
        # Verify the token and get the payload
        payload = verify_token(token)
        
        # Check if this is an access token
        if payload.token_type != TokenType.ACCESS:
            raise InvalidTokenException("Invalid token type. Access token required.")
        
        # Get user ID from token
        user_id = payload.sub
        if not user_id:
            raise InvalidTokenException("Invalid token payload: missing user ID")
            
        # Get user from database
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise InvalidTokenException("User not found")
            
        if not user.is_active:
            raise InactiveUserException("Inactive user")
            
        return user
        
    except HTTPException:
        # Re-raise HTTP exceptions from verify_token
        raise
    except Exception as e:
        # Handle any other exceptions
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e


def get_current_active_superuser(
    current_user: User = Depends(get_current_user),
) -> User:
    """Dependency to check if the current user is a superuser."""
    if not current_user.is_superuser:
        raise PermissionDeniedException(
            "The user doesn't have enough privileges"
        )
    return current_user
