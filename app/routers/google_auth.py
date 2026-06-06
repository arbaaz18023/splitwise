from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.refresh_token import RefreshToken
from app.schemas.user import (
    GoogleAuthRequest,
    GoogleAuthResponse,
    GoogleUserProfile,
    RefreshTokenRequest,
    RefreshTokenResponse,
    LogoutResponse,
)
from app.services.auth import (
    create_access_token,
    generate_refresh_token,
    store_refresh_token,
    rotate_refresh_token,
)
from app.services.google_auth import verify_google_token

router = APIRouter(prefix="/api/auth", tags=["google-auth"])


def _error(status_code: int, error: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": error, "message": message},
    )


@router.post("/google", response_model=GoogleAuthResponse)
async def google_login(body: GoogleAuthRequest, db: AsyncSession = Depends(get_db)):
    if not body.idToken:
        return _error(
            status.HTTP_400_BAD_REQUEST,
            "Bad Request",
            "Required request body parameter 'idToken' is missing.",
        )

    try:
        payload = verify_google_token(body.idToken)
    except ValueError:
        return _error(
            status.HTTP_401_UNAUTHORIZED,
            "Unauthorized",
            "Invalid google credential. Backend verification failed.",
        )

    google_id: str = payload.get("sub", "")
    name: str = payload.get("name", "")
    email: str | None = payload.get("email")
    avatar_url: str | None = payload.get("picture")

    result = await db.execute(select(User).where(User.google_id == google_id))
    user = result.scalar_one_or_none()

    if user is None and email:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

    if user is None:
        user = User(
            email=email or f"{google_id}@google.oauth",
            name=name,
            hashed_password=None,
            google_id=google_id,
            avatar_url=avatar_url,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
    else:
        updated = False
        if user.google_id != google_id:
            user.google_id = google_id
            updated = True
        if avatar_url and user.avatar_url != avatar_url:
            user.avatar_url = avatar_url
            updated = True
        if updated:
            await db.commit()
            await db.refresh(user)

    access_token = create_access_token(user.id)
    raw_refresh, refresh_hash = generate_refresh_token()
    await store_refresh_token(user.id, refresh_hash, db)

    return GoogleAuthResponse(
        token=access_token,
        refreshToken=raw_refresh,
        user=GoogleUserProfile(
            id=str(user.id),
            name=user.name,
            email=user.email,
            avatarUrl=user.avatar_url,
        ),
    )


@router.post("/refresh", response_model=RefreshTokenResponse)
async def refresh_token(body: RefreshTokenRequest, db: AsyncSession = Depends(get_db)):
    if not body.refreshToken:
        return _error(
            status.HTTP_400_BAD_REQUEST,
            "Bad Request",
            "Required request body parameter 'refreshToken' is missing.",
        )

    try:
        new_raw_refresh, _, user_id = await rotate_refresh_token(body.refreshToken, db)
    except HTTPException:
        return _error(
            status.HTTP_401_UNAUTHORIZED,
            "Unauthorized",
            "Invalid or expired refresh token. User must re-authenticate.",
        )

    new_access_token = create_access_token(user_id)
    return RefreshTokenResponse(token=new_access_token, refreshToken=new_raw_refresh)


@router.post("/logout", response_model=LogoutResponse)
async def logout(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == current_user.id, RefreshToken.is_revoked == False)
        .values(is_revoked=True)
    )
    await db.commit()

    return LogoutResponse(message="Successfully logged out and session token invalidated.")
