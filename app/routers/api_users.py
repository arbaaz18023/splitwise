from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.api_users import ApiUserResponse, ApiUserUpdate

router = APIRouter(prefix="/api/users", tags=["api-users"])


def _to_response(user: User) -> ApiUserResponse:
    return ApiUserResponse(
        id=str(user.id),
        name=user.name,
        email=user.email,
        avatarUrl=user.avatar_url,
    )


@router.get("/me", response_model=ApiUserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return _to_response(current_user)


@router.put("/me", response_model=ApiUserResponse)
async def update_me(
    data: ApiUserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not data.name or not data.name.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Name cannot be blank",
        )

    if data.email is not None:
        email_val = data.email.strip()
        if "@" not in email_val or "." not in email_val.split("@")[-1]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid email format",
            )
        # Check uniqueness if email is changing
        if email_val != current_user.email:
            existing = await db.execute(
                select(User).where(User.email == email_val, User.id != current_user.id)
            )
            if existing.scalar_one_or_none():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already in use",
                )
        current_user.email = email_val

    current_user.name = data.name.strip()
    await db.commit()
    await db.refresh(current_user)
    return _to_response(current_user)


@router.get("/search", response_model=list[ApiUserResponse])
async def search_users(
    query: Optional[str] = Query(default=None),
    email: Optional[str] = Query(default=None),
    phoneSuffix: Optional[str] = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not any([query, email, phoneSuffix]):
        return []

    filters = []

    if email:
        filters.append(User.email == email.strip())

    if phoneSuffix:
        filters.append(User.phone_number.like(f"%{phoneSuffix.strip()}"))

    if query:
        q = f"%{query.strip()}%"
        filters.append(
            or_(
                User.name.ilike(q),
                User.email.ilike(q),
            )
        )

    result = await db.execute(
        select(User).where(or_(*filters)).limit(50)
    )
    users = result.scalars().all()
    return [_to_response(u) for u in users]
