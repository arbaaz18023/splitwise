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
from app.schemas.api_group import (
    ApiAddMembers,
    ApiAddMembersResponse,
    ApiGroupCreate,
    ApiGroupResponse,
    ApiMemberResponse,
)

router = APIRouter(prefix="/api/groups", tags=["api-groups"])


def _fmt_date(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.strftime("%b %d, %Y")


async def _get_group_or_404(db: AsyncSession, group_id: int) -> Group:
    result = await db.execute(select(Group).where(Group.id == group_id))
    group = result.scalar_one_or_none()
    if group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
    return group


async def _is_member(db: AsyncSession, group_id: int, user_id: int) -> bool:
    result = await db.execute(
        select(GroupMember).where(
            GroupMember.group_id == group_id,
            GroupMember.user_id == user_id,
        )
    )
    return result.scalar_one_or_none() is not None


async def _get_members(db: AsyncSession, group_id: int) -> list[ApiMemberResponse]:
    result = await db.execute(
        select(User)
        .join(GroupMember, User.id == GroupMember.user_id)
        .where(GroupMember.group_id == group_id)
    )
    return [
        ApiMemberResponse(id=str(u.id), name=u.name, email=u.email)
        for u in result.scalars().all()
    ]


async def _get_user_or_404(db: AsyncSession, user_id: int) -> User:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User {user_id} not found")
    return user


async def _calc_user_balance(db: AsyncSession, group_id: int, user_id: int) -> float:
    balance = 0.0
    expenses_result = await db.execute(
        select(Expense).where(Expense.group_id == group_id)
    )
    for expense in expenses_result.scalars().all():
        if expense.paid_by == user_id:
            balance += expense.amount
        splits_result = await db.execute(
            select(ExpenseSplit).where(
                ExpenseSplit.expense_id == expense.id,
                ExpenseSplit.user_id == user_id,
            )
        )
        split = splits_result.scalar_one_or_none()
        if split:
            balance -= split.amount
    return round(balance, 2)


async def _build_group_response(
    db: AsyncSession, group: Group, current_user_id: int
) -> ApiGroupResponse:
    members = await _get_members(db, group.id)
    creator = await _get_user_or_404(db, group.created_by)
    total_balance = await _calc_user_balance(db, group.id, current_user_id)
    return ApiGroupResponse(
        id=str(group.id),
        name=group.name,
        members=members,
        createdBy=ApiMemberResponse(
            id=str(creator.id), name=creator.name, email=creator.email
        ),
        createdAt=_fmt_date(group.created_at),
        totalBalance=total_balance,
    )


async def _get_or_create_guest(db: AsyncSession, name: str, phone: Optional[str]) -> User:
    placeholder_email = f"guest_{phone.replace(' ', '').replace('+', '').replace('(', '').replace(')', '').replace('-', '')}@guest.splitwise" if phone else f"guest_{name.lower().replace(' ', '_')}@guest.splitwise"
    result = await db.execute(select(User).where(User.email == placeholder_email))
    existing = result.scalar_one_or_none()
    if existing:
        return existing
    user = User(
        email=placeholder_email,
        name=name,
        hashed_password=None,
        phone_number=phone,
    )
    db.add(user)
    await db.flush()
    return user


@router.get("", response_model=list[ApiGroupResponse])
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
    return [await _build_group_response(db, g, current_user.id) for g in groups]


@router.post("", response_model=ApiGroupResponse, status_code=status.HTTP_201_CREATED)
async def create_group(
    data: ApiGroupCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not data.name or not data.name.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Group name cannot be blank")

    group = Group(name=data.name.strip(), created_by=current_user.id)
    db.add(group)
    await db.flush()

    member_user_ids: set[int] = {current_user.id}

    for m in data.members:
        if m.id is not None:
            try:
                uid = int(m.id)
                member_user_ids.add(uid)
            except ValueError:
                pass
        elif m.name:
            guest = await _get_or_create_guest(db, m.name, m.phoneNumber)
            member_user_ids.add(guest.id)

    for uid in member_user_ids:
        db.add(GroupMember(group_id=group.id, user_id=uid))

    await db.commit()
    await db.refresh(group)
    return await _build_group_response(db, group, current_user.id)


@router.get("/{group_id}", response_model=ApiGroupResponse)
async def get_group(
    group_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    group = await _get_group_or_404(db, group_id)
    if not await _is_member(db, group_id, current_user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
    return await _build_group_response(db, group, current_user.id)


@router.post("/{group_id}/members", response_model=ApiAddMembersResponse)
async def add_members(
    group_id: int,
    data: ApiAddMembers,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    group = await _get_group_or_404(db, group_id)
    if not await _is_member(db, group_id, current_user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")

    for member_id_str in data.memberIds:
        try:
            uid = int(member_id_str)
        except ValueError:
            continue
        if not await _is_member(db, group_id, uid):
            db.add(GroupMember(group_id=group_id, user_id=uid))

    await db.commit()
    return ApiAddMembersResponse(message="Members successfully added to the group.")
