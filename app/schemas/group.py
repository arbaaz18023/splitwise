from datetime import datetime

from pydantic import BaseModel


class GroupCreate(BaseModel):
    name: str
    description: str | None = None
    member_ids: list[int] = []


class AddMembers(BaseModel):
    user_ids: list[int]


class GroupMemberResponse(BaseModel):
    id: int
    email: str
    name: str
    joined_at: datetime


class GroupResponse(BaseModel):
    id: int
    name: str
    description: str | None
    created_by: int
    created_at: datetime
    members: list[GroupMemberResponse]


class GroupListResponse(BaseModel):
    id: int
    name: str
    description: str | None
    created_at: datetime


class BalanceResponse(BaseModel):
    user_id: int
    user_name: str
    balance: float
