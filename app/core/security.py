from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Union
from jose import JWTError, jwt
from passlib.context import CryptContext
import uuid

from app.config.settings import get_settings
from app.schemas.user import TokenType, TokenPayload

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def create_access_token(
    subject: str, 
    expires_delta: Optional[timedelta] = None,
    token_type: TokenType = TokenType.ACCESS
) -> str:
    settings = get_settings()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
    
    to_encode = {
        "exp": expire, 
        "sub": str(subject),
        "token_type": token_type,
        "jti": str(uuid.uuid4())
    }
    
    encoded_jwt = jwt.encode(
        to_encode, 
        settings.SECRET_KEY, 
        algorithm=settings.ALGORITHM
    )
    return encoded_jwt

def create_refresh_token(
    subject: str,
    expires_delta: Optional[timedelta] = None
) -> str:
    settings = get_settings()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            days=settings.REFRESH_TOKEN_EXPIRE_DAYS
        )
    
    return create_access_token(
        subject=subject,
        expires_delta=expire - datetime.utcnow(),
        token_type=TokenType.REFRESH
    )

def decode_token(token: str) -> Dict[str, Any]:
    settings = get_settings()
    return jwt.decode(
        token,
        settings.SECRET_KEY,
        algorithms=[settings.ALGORITHM],
        options={"verify_aud": False}
    )

def verify_token(token: str) -> TokenPayload:
    from fastapi import HTTPException, status
    from jose.exceptions import ExpiredSignatureError
    
    try:
        payload = decode_token(token)
        token_data = TokenPayload(**payload)
        return token_data
    except ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e
