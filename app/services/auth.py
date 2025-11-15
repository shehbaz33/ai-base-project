from datetime import datetime, timedelta
from typing import Optional, Tuple
from sqlalchemy.orm import Session
from jose import JWTError
import uuid
from app.config.settings import get_settings

from app.core.security import (
    get_password_hash, 
    verify_password, 
    create_access_token,
    create_refresh_token,
    verify_token
)
from app.models.user import User, RefreshToken
from app.schemas.user import UserCreate, TokenResponse, TokenPayload
from app.core.exceptions import (
    InvalidCredentialsException,
    InactiveUserException,
    InvalidTokenException
)

class AuthService:
    @staticmethod
    def _process_password(password: str) -> str:
        """
        Safely truncate password to 72 bytes without breaking UTF-8.
        """
        encoded = password.encode("utf-8")

        if len(encoded) <= 72:
            return password

        # truncate safely
        truncated = encoded[:72]

        # Ensure we don't cut in the middle of a UTF-8 multibyte character
        while True:
            try:
                return truncated.decode("utf-8")
            except UnicodeDecodeError:
                truncated = truncated[:-1]   # remove one byte and retry


    @staticmethod
    def authenticate_user(db: Session, email: str, password: str) -> User:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            raise InvalidCredentialsException()
        
        # Process password to handle length limitations
        processed_password = AuthService._process_password(password)
        
        if not verify_password(processed_password, user.hashed_password):
            raise InvalidCredentialsException()
        if not user.is_active:
            raise InactiveUserException()
        return user

    @staticmethod
    def create_user(db: Session, user_in: UserCreate) -> User:
        # Process password to handle length limitations before hashing
        processed_password = AuthService._process_password(user_in.password)
        
        hashed_password = get_password_hash(processed_password)
        
        db_user = User(
            email=user_in.email,
            hashed_password=hashed_password,
            full_name=user_in.full_name,
        )
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        return db_user

    @staticmethod
    def create_tokens(db: Session, user_id: uuid.UUID) -> TokenResponse:
        # Create access token
        settings = get_settings()
        access_token = create_access_token(
            subject=str(user_id)
        )
        
        # Create refresh token
        refresh_token = create_refresh_token(
            subject=str(user_id)
        )
        
        # Store refresh token in database
        refresh_token_db = RefreshToken(
            user_id=user_id,
            token=refresh_token,
            expires_at=datetime.now() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        )
        db.add(refresh_token_db)
        db.commit()
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer"
        )

    @staticmethod
    def refresh_tokens(db: Session, refresh_token: str) -> TokenResponse:
        try:
            # Verify refresh token
            token_data = verify_token(refresh_token)
            
            if token_data.token_type != "refresh":
                raise InvalidTokenException("Invalid token type")
            
            # Check if token exists and is not revoked
            token_in_db = db.query(RefreshToken).filter(
                RefreshToken.token == refresh_token,
                RefreshToken.is_revoked == False,
                RefreshToken.expires_at > datetime.utcnow()
            ).first()
            
            if not token_in_db:
                raise InvalidTokenException("Invalid or expired refresh token")
            
            # Create new tokens
            return AuthService.create_tokens(db, token_in_db.user_id)
            
        except JWTError as e:
            raise InvalidTokenException("Invalid token") from e

    @staticmethod
    def revoke_refresh_token(db: Session, refresh_token: str) -> None:
        token = db.query(RefreshToken).filter(
            RefreshToken.token == refresh_token,
            RefreshToken.is_revoked == False
        ).first()
        
        if token:
            token.is_revoked = True
            db.add(token)
            db.commit()

    @staticmethod
    def revoke_all_user_refresh_tokens(db: Session, user_id: uuid.UUID) -> None:
        db.query(RefreshToken).filter(
            RefreshToken.user_id == user_id,
            RefreshToken.is_revoked == False
        ).update({"is_revoked": True})
        db.commit()
