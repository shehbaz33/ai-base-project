from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional
from datetime import datetime
from uuid import UUID
from enum import Enum

class TokenType(str, Enum):
    ACCESS = "access"
    REFRESH = "refresh"

class TokenBase(BaseModel):
    token: str
    token_type: TokenType
    expires_at: datetime

class TokenCreate(TokenBase):
    user_id: UUID

class Token(TokenBase):
    id: UUID
    user_id: UUID
    is_revoked: bool
    created_at: datetime
    
    class Config:
        orm_mode = True

class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None

class UserCreate(UserBase):
    password: str = Field(..., min_length=8, max_length=72)

class UserUpdate(UserBase):
    password: Optional[str] = Field(None, min_length=8, max_length=72)

class UserInDBBase(UserBase):
    id: UUID
    is_active: bool
    is_superuser: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True

class User(UserInDBBase):
    pass

class UserInDB(UserInDBBase):
    hashed_password: str

class TokenPayload(BaseModel):
    sub: UUID = None
    exp: int = None
    token_type: TokenType

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class RefreshTokenRequest(BaseModel):
    refresh_token: str
