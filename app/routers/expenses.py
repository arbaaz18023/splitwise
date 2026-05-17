from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.dependencies import get_current_user
from app.models.expense import Expense, ExpenseSplit
from app.models.group import Group, GroupMember
from app.models.user import User
from app.schemas.expense import ExpenseCreate, ExpenseResponse, ExpenseSplitResponse, ExpenseUpdate

router = APIRouter(prefix="/groups/{group_id}/expenses", tags=["expenses"])


async def _check_membership(db: AsyncSession, group_id: int, user_id: int):
    result = await db.execute(
        select(GroupMember).where(GroupMember.group_id == group_id, GroupMember.user_id == user_id)
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a group member")


async def _get_group_or_404(db: AsyncSession, group_id: int) -> Group:
    result = await db.execute(select(Group).where(Group.id == group_id))
    group = result.scalar_one_or_none()
    if group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
    return group


async def _get_group_member_ids(db: AsyncSession, group_id: int) -> list[int]:
    result = await db.execute(
        select(GroupMember.user_id).where(GroupMember.group_id == group_id)
    )
    return [row[0] for row in result.all()]


async def _build_response(db: AsyncSession, expense: Expense) -> ExpenseResponse:
    # Load splits with user names
    result = await db.execute(
        select(ExpenseSplit, User.name)
        .join(User, ExpenseSplit.user_id == User.id)
        .where(ExpenseSplit.expense_id == expense.id)
    )
    splits = [
        ExpenseSplitResponse(user_id=split.user_id, user_name=name, amount=split.amount)
        for split, name in result.all()
    ]
    return ExpenseResponse(
        id=expense.id,
        group_id=expense.group_id,
        paid_by=expense.paid_by,
        amount=expense.amount,
        description=expense.description,
        split_type=expense.split_type,
        created_at=expense.created_at,
        updated_at=expense.updated_at,
        splits=splits,
    )


def _calculate_splits(expense_amount: float, split_type: str, splits_data, member_ids: list[int]) -> list[dict]:
    """Calculate split amounts based on split_type."""
    if split_type == "equal":
        user_ids = [s.user_id for s in splits_data] if splits_data else member_ids
        per_person = round(expense_amount / len(user_ids), 2)
        return [{"user_id": uid, "amount": per_person} for uid in user_ids]

    elif split_type == "exact":
        if not splits_data:
            raise HTTPException(status_code=400, detail="Exact split requires splits list")
        total = sum(s.amount for s in splits_data)
        if abs(total - expense_amount) > 0.01:
            raise HTTPException(status_code=400, detail="Split amounts must sum to total")
        return [{"user_id": s.user_id, "amount": s.amount} for s in splits_data]

    elif split_type == "percentage":
        if not splits_data:
            raise HTTPException(status_code=400, detail="Percentage split requires splits list")
        total_pct = sum(s.percentage for s in splits_data)
        if abs(total_pct - 100) > 0.01:
            raise HTTPException(status_code=400, detail="Percentages must sum to 100")
        return [
            {"user_id": s.user_id, "amount": round(expense_amount * s.percentage / 100, 2)}
            for s in splits_data
        ]

    raise HTTPException(status_code=400, detail=f"Invalid split_type: {split_type}")


@router.post("", response_model=ExpenseResponse, status_code=status.HTTP_201_CREATED)
async def create_expense(
    group_id: int,
    data: ExpenseCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_group_or_404(db, group_id)
    await _check_membership(db, group_id, current_user.id)

    member_ids = await _get_group_member_ids(db, group_id)
    calculated_splits = _calculate_splits(data.amount, data.split_type, data.splits, member_ids)

    expense = Expense(
        group_id=group_id,
        paid_by=data.paid_by,
        amount=data.amount,
        description=data.description,
        split_type=data.split_type,
    )
    db.add(expense)
    await db.flush()

    for s in calculated_splits:
        db.add(ExpenseSplit(expense_id=expense.id, user_id=s["user_id"], amount=s["amount"]))
    await db.commit()
    await db.refresh(expense)

    return await _build_response(db, expense)


@router.get("", response_model=list[ExpenseResponse])
async def list_expenses(
    group_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_group_or_404(db, group_id)
    await _check_membership(db, group_id, current_user.id)

    result = await db.execute(
        select(Expense).where(Expense.group_id == group_id).order_by(Expense.created_at.desc())
    )
    expenses = result.scalars().all()
    return [await _build_response(db, e) for e in expenses]


@router.get("/{expense_id}", response_model=ExpenseResponse)
async def get_expense(
    group_id: int,
    expense_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_group_or_404(db, group_id)
    await _check_membership(db, group_id, current_user.id)

    result = await db.execute(
        select(Expense).where(Expense.id == expense_id, Expense.group_id == group_id)
    )
    expense = result.scalar_one_or_none()
    if expense is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Expense not found")

    return await _build_response(db, expense)


@router.put("/{expense_id}", response_model=ExpenseResponse)
async def update_expense(
    group_id: int,
    expense_id: int,
    data: ExpenseUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    group = await _get_group_or_404(db, group_id)
    await _check_membership(db, group_id, current_user.id)

    result = await db.execute(
        select(Expense).where(Expense.id == expense_id, Expense.group_id == group_id)
    )
    expense = result.scalar_one_or_none()
    if expense is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Expense not found")

    # Only creator or group creator can edit
    if current_user.id != expense.paid_by and current_user.id != group.created_by:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to edit this expense")

    if data.description is not None:
        expense.description = data.description
    if data.amount is not None:
        expense.amount = data.amount
    if data.paid_by is not None:
        expense.paid_by = data.paid_by
    if data.split_type is not None:
        expense.split_type = data.split_type

    # Recalculate splits if amount, split_type, or splits changed
    if data.splits is not None or data.amount is not None or data.split_type is not None:
        member_ids = await _get_group_member_ids(db, group_id)
        calculated_splits = _calculate_splits(
            expense.amount, expense.split_type, data.splits, member_ids
        )
        # Delete old splits
        old_splits = await db.execute(
            select(ExpenseSplit).where(ExpenseSplit.expense_id == expense.id)
        )
        for old in old_splits.scalars().all():
            await db.delete(old)
        # Add new splits
        for s in calculated_splits:
            db.add(ExpenseSplit(expense_id=expense.id, user_id=s["user_id"], amount=s["amount"]))

    await db.commit()
    await db.refresh(expense)
    return await _build_response(db, expense)


@router.delete("/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_expense(
    group_id: int,
    expense_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    group = await _get_group_or_404(db, group_id)
    await _check_membership(db, group_id, current_user.id)

    result = await db.execute(
        select(Expense).where(Expense.id == expense_id, Expense.group_id == group_id)
    )
    expense = result.scalar_one_or_none()
    if expense is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Expense not found")

    if current_user.id != expense.paid_by and current_user.id != group.created_by:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to delete this expense")

    await db.delete(expense)
    await db.commit()
