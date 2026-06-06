from typing import Optional

from pydantic import BaseModel


class ApiMemberInput(BaseModel):
    id: Optional[str] = None
    name: Optional[str] = None
    phoneNumber: Optional[str] = None


class ApiGroupCreate(BaseModel):
    name: str
    members: list[ApiMemberInput] = []


class ApiAddMembers(BaseModel):
    memberIds: list[str]


class ApiMemberResponse(BaseModel):
    id: str
    name: str
    email: Optional[str] = None


class ApiGroupResponse(BaseModel):
    id: str
    name: str
    members: list[ApiMemberResponse]
    createdBy: ApiMemberResponse
    createdAt: str
    totalBalance: float


class ApiAddMembersResponse(BaseModel):
    message: str
