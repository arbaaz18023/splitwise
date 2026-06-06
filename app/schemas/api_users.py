from typing import Optional

from pydantic import BaseModel, EmailStr


class ApiUserResponse(BaseModel):
    id: str
    name: str
    email: str
    avatarUrl: Optional[str] = None


class ApiUserUpdate(BaseModel):
    name: str
    email: Optional[str] = None
