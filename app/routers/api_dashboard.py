import logging
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

logger = logging.getLogger(__name__)

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
    logger.info("GET /api/dashboard/summary — user_id=%s", current_user.id)
    try:
        gm_result = await db.execute(
            select(GroupMember.group_id).where(GroupMember.user_id == current_user.id)
        )
        group_ids = [row[0] for row in gm_result.all()]
        logger.debug("user_id=%s belongs to group_ids=%s", current_user.id, group_ids)

        if not group_ids:
            logger.info("user_id=%s has no groups — returning zero balances", current_user.id)
            return DashboardSummaryResponse(
                overallBalance=0.0,
                totalOwedToYou=0.0,
                totalYouOwe=0.0,
                recentExpenses=[],
            )

        expenses_result = await db.execute(
            select(Expense).where(Expense.group_id.in_(group_ids))
        )
        all_expenses = expenses_result.scalars().all()
        logger.debug("user_id=%s found %d expenses across groups", current_user.id, len(all_expenses))

        total_owed_to_you = 0.0
        total_you_owe = 0.0

        for expense in all_expenses:
            if expense.paid_by == current_user.id:
                splits_result = await db.execute(
                    select(ExpenseSplit).where(
                        ExpenseSplit.expense_id == expense.id,
                        ExpenseSplit.user_id != current_user.id,
                    )
                )
                for split in splits_result.scalars().all():
                    total_owed_to_you += split.amount
            else:
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
        logger.info(
            "user_id=%s balances: owedToYou=%.2f youOwe=%.2f overall=%.2f",
            current_user.id, total_owed_to_you, total_you_owe, overall_balance,
        )

        recent_result = await db.execute(
            select(Expense)
            .where(Expense.group_id.in_(group_ids))
            .order_by(Expense.created_at.desc())
            .limit(RECENT_LIMIT)
        )
        recent_expenses = recent_result.scalars().all()
        logger.debug("user_id=%s recent_expenses count=%d", current_user.id, len(recent_expenses))

        payer_ids = list({e.paid_by for e in recent_expenses})
        payers_result = await db.execute(select(User).where(User.id.in_(payer_ids)))
        payers_map = {u.id: u for u in payers_result.scalars().all()}

        recent = []
        for expense in recent_expenses:
            payer = payers_map.get(expense.paid_by)
            if not payer:
                logger.warning("Payer not found for expense_id=%s paid_by=%s", expense.id, expense.paid_by)
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
    except Exception:
        logger.exception("Unexpected error in get_dashboard_summary for user_id=%s", current_user.id)
        raise
