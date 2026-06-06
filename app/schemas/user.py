from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class UserCreate(BaseModel):
    email: str
    name: str
    password: str


class UserResponse(BaseModel):
    id: int
    email: str
    name: str
    created_at: datetime

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    user_id: int | None = None


class GoogleAuthRequest(BaseModel):
    idToken: str


class GoogleUserProfile(BaseModel):
    id: str
    name: str
    email: Optional[str] = None
    avatarUrl: Optional[str] = None


class GoogleAuthResponse(BaseModel):
    token: str
    user: GoogleUserProfile
