from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from typing import Any
import uuid

from app.api.deps import get_db, get_current_user
from app.schemas.user import (
    UserCreate, 
    User as UserSchema,
    TokenResponse,
    RefreshTokenRequest
)
from app.models.user import User
from app.services.auth import AuthService
from app.core.exceptions import (
    InvalidCredentialsException,
    InactiveUserException,
    InvalidTokenException,
    UserAlreadyExistsException
)
from app.utils.api_response import create_api_response

router = APIRouter()

@router.post("/register", response_model=dict, status_code=status.HTTP_201_CREATED)
async def register(
    user_in: UserCreate,
    db: Session = Depends(get_db)
) -> Any:
    """
    Register a new user.
    """
    # Check if user already exists
    existing_user = db.query(User).filter(User.email == user_in.email).first()
    if existing_user:
        raise UserAlreadyExistsException()
    
    # Create new user
    user = AuthService.create_user(db=db, user_in=user_in)
    return create_api_response(data=user, message="User registered successfully")

@router.post("/login", response_model=dict)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
) -> Any:
    """
    OAuth2 compatible token login, get an access token for future requests.
    """
    try:
        # Authenticate user
        user = AuthService.authenticate_user(
            db=db, 
            email=form_data.username, 
            password=form_data.password
        )
        
        # Create tokens
        tokens = AuthService.create_tokens(db=db, user_id=user.id)
        return create_api_response(data=tokens, message="Login successful")
        
    except (InvalidCredentialsException, InactiveUserException) as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

@router.post("/refresh-token", response_model=dict)
async def refresh_token(
    token_in: RefreshTokenRequest,
    db: Session = Depends(get_db)
) -> Any:
    """
    Refresh access token using a valid refresh token.
    """
    try:
        tokens = AuthService.refresh_tokens(db=db, refresh_token=token_in.refresh_token)
        return create_api_response(data=tokens, message="Token refreshed")
    except InvalidTokenException as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )

@router.post("/logout")
async def logout(
    token_in: RefreshTokenRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """
    Log out by revoking the provided refresh token.
    """
    AuthService.revoke_refresh_token(db=db, refresh_token=token_in.refresh_token)
    return create_api_response(data=[], message="Successfully logged out")

@router.post("/logout-all")
async def logout_all(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Log out from all devices by revoking all refresh tokens for the current user.
    """
    AuthService.revoke_all_user_refresh_tokens(db=db, user_id=current_user.id)
    return create_api_response(data=[], message="Successfully logged out from all devices")
