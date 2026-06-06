from typing import Optional

from pydantic import BaseModel


class ApiExpenseUser(BaseModel):
    id: str
    name: str
    email: str
    avatarUrl: Optional[str] = None


class ApiExpenseResponse(BaseModel):
    id: str
    title: str
    amount: float
    paidBy: ApiExpenseUser
    splitMethod: str
    participants: list[ApiExpenseUser]
    timestamp: str
    groupId: Optional[str] = None


class ApiExpenseCreate(BaseModel):
    title: str
    amount: float
    paidById: str
    groupId: Optional[str] = None
    splitMethod: str = "EQUAL"
    participantIds: list[str]
