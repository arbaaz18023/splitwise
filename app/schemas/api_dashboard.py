from typing import Optional

from pydantic import BaseModel


class DashboardPaidBy(BaseModel):
    id: str
    name: str
    email: str
    avatarUrl: Optional[str] = None


class DashboardExpense(BaseModel):
    id: str
    title: str
    amount: float
    paidBy: DashboardPaidBy
    timestamp: str


class DashboardSummaryResponse(BaseModel):
    overallBalance: float
    totalOwedToYou: float
    totalYouOwe: float
    recentExpenses: list[DashboardExpense]
