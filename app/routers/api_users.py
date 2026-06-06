import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.api_users import ApiUserResponse, ApiUserUpdate

logger = logging.getLogger(__name__)

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
    logger.info("GET /api/users/me — user_id=%s", current_user.id)
    return _to_response(current_user)


@router.put("/me", response_model=ApiUserResponse)
async def update_me(
    data: ApiUserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    logger.info("PUT /api/users/me — user_id=%s name=%r email=%r", current_user.id, data.name, data.email)
    try:
        if not data.name or not data.name.strip():
            logger.warning("update_me rejected: blank name, user_id=%s", current_user.id)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Name cannot be blank",
            )

        if data.email is not None:
            email_val = data.email.strip()
            if "@" not in email_val or "." not in email_val.split("@")[-1]:
                logger.warning("update_me rejected: invalid email %r user_id=%s", email_val, current_user.id)
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid email format",
                )
            if email_val != current_user.email:
                existing = await db.execute(
                    select(User).where(User.email == email_val, User.id != current_user.id)
                )
                if existing.scalar_one_or_none():
                    logger.warning("update_me rejected: email %r already in use, user_id=%s", email_val, current_user.id)
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Email already in use",
                    )
            current_user.email = email_val

        current_user.name = data.name.strip()
        await db.commit()
        await db.refresh(current_user)
        logger.info("Profile updated: user_id=%s new_name=%r new_email=%r", current_user.id, current_user.name, current_user.email)
        return _to_response(current_user)
    except HTTPException:
        raise
    except Exception:
        logger.exception("Unexpected error in update_me for user_id=%s", current_user.id)
        raise


@router.get("/search", response_model=list[ApiUserResponse])
async def search_users(
    query: Optional[str] = Query(default=None),
    email: Optional[str] = Query(default=None),
    phoneSuffix: Optional[str] = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    logger.info(
        "GET /api/users/search — user_id=%s query=%r email=%r phoneSuffix=%r",
        current_user.id, query, email, phoneSuffix,
    )
    try:
        if not any([query, email, phoneSuffix]):
            logger.debug("search_users: no params provided — returning empty list")
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
        logger.info("search_users: found %d results for user_id=%s", len(users), current_user.id)
        return [_to_response(u) for u in users]
    except Exception:
        logger.exception("Unexpected error in search_users for user_id=%s", current_user.id)
        raise
