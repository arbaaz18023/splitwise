import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.expense import Expense, ExpenseSplit
from app.models.group import Group, GroupMember
from app.models.user import User
from app.schemas.api_expenses import ApiExpenseCreate, ApiExpenseResponse, ApiExpenseUser

logger = logging.getLogger(__name__)

groups_router = APIRouter(prefix="/api/groups", tags=["api-expenses"])
expenses_router = APIRouter(prefix="/api/expenses", tags=["api-expenses"])


def _fmt_date(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.strftime("%b %d, %Y")


def _to_api_user(user: User) -> ApiExpenseUser:
    return ApiExpenseUser(
        id=str(user.id),
        name=user.name,
        email=user.email,
        avatarUrl=user.avatar_url,
    )


async def _get_expense_or_404(db: AsyncSession, expense_id: int) -> Expense:
    result = await db.execute(select(Expense).where(Expense.id == expense_id))
    expense = result.scalar_one_or_none()
    if expense is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Expense not found")
    return expense


async def _build_api_response(db: AsyncSession, expense: Expense) -> ApiExpenseResponse:
    payer_result = await db.execute(select(User).where(User.id == expense.paid_by))
    payer = payer_result.scalar_one_or_none()

    splits_result = await db.execute(
        select(User)
        .join(ExpenseSplit, User.id == ExpenseSplit.user_id)
        .where(ExpenseSplit.expense_id == expense.id)
    )
    participants = [_to_api_user(u) for u in splits_result.scalars().all()]

    return ApiExpenseResponse(
        id=str(expense.id),
        title=expense.description,
        amount=expense.amount,
        paidBy=_to_api_user(payer) if payer else ApiExpenseUser(
            id=str(expense.paid_by), name="Unknown", email=""
        ),
        splitMethod=expense.split_type.upper(),
        participants=participants,
        timestamp=_fmt_date(expense.created_at),
        groupId=str(expense.group_id) if expense.group_id else None,
    )


@groups_router.get("/{group_id}/expenses", response_model=list[ApiExpenseResponse])
async def list_group_expenses(
    group_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    logger.info("GET /api/groups/%s/expenses — user_id=%s", group_id, current_user.id)
    try:
        group_result = await db.execute(select(Group).where(Group.id == group_id))
        if group_result.scalar_one_or_none() is None:
            logger.warning("list_group_expenses: group_id=%s not found", group_id)
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")

        result = await db.execute(
            select(Expense)
            .where(Expense.group_id == group_id)
            .order_by(Expense.created_at.desc())
        )
        expenses = result.scalars().all()
        logger.info("list_group_expenses: group_id=%s returning %d expenses", group_id, len(expenses))
        return [await _build_api_response(db, e) for e in expenses]
    except HTTPException:
        raise
    except Exception:
        logger.exception("Unexpected error in list_group_expenses: group_id=%s", group_id)
        raise


@expenses_router.post("", response_model=ApiExpenseResponse, status_code=status.HTTP_201_CREATED)
async def create_expense(
    data: ApiExpenseCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    logger.info(
        "POST /api/expenses — user_id=%s title=%r amount=%s groupId=%s splitMethod=%s participants=%s",
        current_user.id, data.title, data.amount, data.groupId, data.splitMethod, data.participantIds,
    )
    try:
        if data.amount <= 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Amount must be greater than 0")
        if not data.participantIds:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="participantIds cannot be empty")
        if not data.title or not data.title.strip():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Title cannot be blank")

        try:
            paid_by_id = int(data.paidById)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid paidById: {data.paidById}")

        group_id: Optional[int] = None
        if data.groupId:
            try:
                group_id = int(data.groupId)
            except ValueError:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid groupId: {data.groupId}")
            group_result = await db.execute(select(Group).where(Group.id == group_id))
            if group_result.scalar_one_or_none() is None:
                logger.warning("create_expense: group_id=%s not found", group_id)
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Group not found")

        participant_ids: list[int] = []
        for pid_str in data.participantIds:
            try:
                participant_ids.append(int(pid_str))
            except ValueError:
                logger.warning("create_expense: invalid participant id %r — skipping", pid_str)

        if not participant_ids:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No valid participant IDs provided")

        split_type = data.splitMethod.lower() if data.splitMethod.lower() in ("equal", "unequal") else "equal"
        per_person = round(data.amount / len(participant_ids), 2)

        expense = Expense(
            group_id=group_id,
            paid_by=paid_by_id,
            amount=data.amount,
            description=data.title.strip(),
            split_type=split_type,
        )
        db.add(expense)
        await db.flush()
        logger.debug("create_expense: flushed expense id=%s", expense.id)

        for uid in participant_ids:
            db.add(ExpenseSplit(expense_id=expense.id, user_id=uid, amount=per_person))

        await db.commit()
        await db.refresh(expense)
        logger.info("create_expense: created expense id=%s group_id=%s amount=%s", expense.id, group_id, data.amount)
        return await _build_api_response(db, expense)
    except HTTPException:
        raise
    except Exception:
        logger.exception("Unexpected error in create_expense for user_id=%s", current_user.id)
        raise


@expenses_router.delete("/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_expense(
    expense_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    logger.info("DELETE /api/expenses/%s — user_id=%s", expense_id, current_user.id)
    try:
        expense = await _get_expense_or_404(db, expense_id)
        await db.delete(expense)
        await db.commit()
        logger.info("delete_expense: expense_id=%s deleted by user_id=%s", expense_id, current_user.id)
    except HTTPException:
        raise
    except Exception:
        logger.exception("Unexpected error in delete_expense: expense_id=%s user_id=%s", expense_id, current_user.id)
        raise
