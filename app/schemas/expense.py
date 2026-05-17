from datetime import datetime

from pydantic import BaseModel


class SplitItem(BaseModel):
    user_id: int
    amount: float | None = None
    percentage: float | None = None


class ExpenseCreate(BaseModel):
    description: str
    amount: float
    paid_by: int
    split_type: str = "equal"
    splits: list[SplitItem] | None = None


class ExpenseUpdate(BaseModel):
    description: str | None = None
    amount: float | None = None
    paid_by: int | None = None
    split_type: str | None = None
    splits: list[SplitItem] | None = None


class ExpenseSplitResponse(BaseModel):
    user_id: int
    user_name: str
    amount: float


class ExpenseResponse(BaseModel):
    id: int
    group_id: int
    paid_by: int
    amount: float
    description: str
    split_type: str
    created_at: datetime
    updated_at: datetime
    splits: list[ExpenseSplitResponse]
