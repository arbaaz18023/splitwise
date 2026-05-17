from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.group import Group, GroupMember
from app.models.user import User
from app.schemas.group import (
    AddMembers,
    BalanceResponse,
    GroupCreate,
    GroupListResponse,
    GroupMemberResponse,
    GroupResponse,
)

router = APIRouter(prefix="/groups", tags=["groups"])


async def _is_member(db: AsyncSession, group_id: int, user_id: int) -> bool:
    result = await db.execute(
        select(GroupMember).where(
            GroupMember.group_id == group_id, GroupMember.user_id == user_id
        )
    )
    return result.scalar_one_or_none() is not None


async def _get_group_or_404(db: AsyncSession, group_id: int) -> Group:
    result = await db.execute(select(Group).where(Group.id == group_id))
    group = result.scalar_one_or_none()
    if group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
    return group


async def _get_members_response(db: AsyncSession, group_id: int) -> list[GroupMemberResponse]:
    result = await db.execute(
        select(User, GroupMember.joined_at)
        .join(GroupMember, User.id == GroupMember.user_id)
        .where(GroupMember.group_id == group_id)
    )
    return [
        GroupMemberResponse(id=user.id, email=user.email, name=user.name, joined_at=joined_at)
        for user, joined_at in result.all()
    ]


@router.post("", response_model=GroupResponse, status_code=status.HTTP_201_CREATED)
async def create_group(
    data: GroupCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    group = Group(name=data.name, description=data.description, created_by=current_user.id)
    db.add(group)
    await db.flush()

    # Add creator as member
    member_ids = set(data.member_ids) | {current_user.id}
    for uid in member_ids:
        db.add(GroupMember(group_id=group.id, user_id=uid))
    await db.commit()
    await db.refresh(group)

    members = await _get_members_response(db, group.id)
    return GroupResponse(
        id=group.id, name=group.name, description=group.description,
        created_by=group.created_by, created_at=group.created_at, members=members,
    )


@router.get("", response_model=list[GroupListResponse])
async def list_groups(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Group)
        .join(GroupMember, Group.id == GroupMember.group_id)
        .where(GroupMember.user_id == current_user.id)
    )
    groups = result.scalars().all()
    return [
        GroupListResponse(id=g.id, name=g.name, description=g.description, created_at=g.created_at)
        for g in groups
    ]


@router.get("/{group_id}", response_model=GroupResponse)
async def get_group(
    group_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    group = await _get_group_or_404(db, group_id)
    if not await _is_member(db, group_id, current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a group member")

    members = await _get_members_response(db, group.id)
    return GroupResponse(
        id=group.id, name=group.name, description=group.description,
        created_by=group.created_by, created_at=group.created_at, members=members,
    )


@router.post("/{group_id}/members", response_model=GroupResponse)
async def add_members(
    group_id: int,
    data: AddMembers,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    group = await _get_group_or_404(db, group_id)
    if group.created_by != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the group creator can add members")

    for uid in data.user_ids:
        if not await _is_member(db, group_id, uid):
            db.add(GroupMember(group_id=group_id, user_id=uid))
    await db.commit()

    members = await _get_members_response(db, group.id)
    return GroupResponse(
        id=group.id, name=group.name, description=group.description,
        created_by=group.created_by, created_at=group.created_at, members=members,
    )


@router.delete("/{group_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    group_id: int,
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    group = await _get_group_or_404(db, group_id)
    if group.created_by != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the group creator can remove members")

    result = await db.execute(
        select(GroupMember).where(
            GroupMember.group_id == group_id, GroupMember.user_id == user_id
        )
    )
    member = result.scalar_one_or_none()
    if member is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")
    await db.delete(member)
    await db.commit()


@router.get("/{group_id}/balances", response_model=list[BalanceResponse])
async def get_balances(
    group_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_group_or_404(db, group_id)
    if not await _is_member(db, group_id, current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a group member")

    from app.models.expense import Expense, ExpenseSplit

    # Get all members
    result = await db.execute(
        select(User)
        .join(GroupMember, User.id == GroupMember.user_id)
        .where(GroupMember.group_id == group_id)
    )
    users = result.scalars().all()

    # Calculate balances: positive = owed money, negative = owes money
    balances = {u.id: 0.0 for u in users}

    # Get all expenses in this group
    expenses_result = await db.execute(
        select(Expense).where(Expense.group_id == group_id)
    )
    expenses = expenses_result.scalars().all()

    for expense in expenses:
        # The payer is owed the total amount
        balances[expense.paid_by] = balances.get(expense.paid_by, 0.0) + expense.amount

        # Each split user owes their share
        splits_result = await db.execute(
            select(ExpenseSplit).where(ExpenseSplit.expense_id == expense.id)
        )
        splits = splits_result.scalars().all()
        for split in splits:
            balances[split.user_id] = balances.get(split.user_id, 0.0) - split.amount

    return [
        BalanceResponse(user_id=u.id, user_name=u.name, balance=round(balances[u.id], 2))
        for u in users
    ]
