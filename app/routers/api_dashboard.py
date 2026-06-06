from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.expense import Expense, ExpenseSplit
from app.models.group import GroupMember
from app.models.user import User
from app.schemas.api_dashboard import DashboardExpense, DashboardPaidBy, DashboardSummaryResponse

router = APIRouter(prefix="/api/dashboard", tags=["api-dashboard"])

RECENT_LIMIT = 20


def _fmt_date(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.strftime("%b %d, %Y")


@router.get("/summary", response_model=DashboardSummaryResponse)
async def get_dashboard_summary(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Fetch all group IDs the current user belongs to
    gm_result = await db.execute(
        select(GroupMember.group_id).where(GroupMember.user_id == current_user.id)
    )
    group_ids = [row[0] for row in gm_result.all()]

    if not group_ids:
        return DashboardSummaryResponse(
            overallBalance=0.0,
            totalOwedToYou=0.0,
            totalYouOwe=0.0,
            recentExpenses=[],
        )

    # Fetch all expenses across those groups
    expenses_result = await db.execute(
        select(Expense).where(Expense.group_id.in_(group_ids))
    )
    all_expenses = expenses_result.scalars().all()

    total_owed_to_you = 0.0
    total_you_owe = 0.0

    for expense in all_expenses:
        if expense.paid_by == current_user.id:
            # Sum what others owe the current user (all splits except user's own)
            splits_result = await db.execute(
                select(ExpenseSplit).where(
                    ExpenseSplit.expense_id == expense.id,
                    ExpenseSplit.user_id != current_user.id,
                )
            )
            for split in splits_result.scalars().all():
                total_owed_to_you += split.amount
        else:
            # Sum what the current user owes to the payer
            split_result = await db.execute(
                select(ExpenseSplit).where(
                    ExpenseSplit.expense_id == expense.id,
                    ExpenseSplit.user_id == current_user.id,
                )
            )
            split = split_result.scalar_one_or_none()
            if split:
                total_you_owe += split.amount

    total_owed_to_you = round(total_owed_to_you, 2)
    total_you_owe = round(total_you_owe, 2)
    overall_balance = round(total_owed_to_you - total_you_owe, 2)

    # Fetch recent expenses across those groups (sorted newest first, limited)
    recent_result = await db.execute(
        select(Expense)
        .where(Expense.group_id.in_(group_ids))
        .order_by(Expense.created_at.desc())
        .limit(RECENT_LIMIT)
    )
    recent_expenses = recent_result.scalars().all()

    # Bulk-load payers
    payer_ids = list({e.paid_by for e in recent_expenses})
    payers_result = await db.execute(select(User).where(User.id.in_(payer_ids)))
    payers_map = {u.id: u for u in payers_result.scalars().all()}

    recent = []
    for expense in recent_expenses:
        payer = payers_map.get(expense.paid_by)
        recent.append(
            DashboardExpense(
                id=str(expense.id),
                title=expense.description,
                amount=expense.amount,
                paidBy=DashboardPaidBy(
                    id=str(payer.id) if payer else str(expense.paid_by),
                    name=payer.name if payer else "Unknown",
                    email=payer.email if payer else "",
                    avatarUrl=payer.avatar_url if payer else None,
                ),
                timestamp=_fmt_date(expense.created_at),
            )
        )

    return DashboardSummaryResponse(
        overallBalance=overall_balance,
        totalOwedToYou=total_owed_to_you,
        totalYouOwe=total_you_owe,
        recentExpenses=recent,
    )
