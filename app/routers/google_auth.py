import logging

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

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["google-auth"])


def _error(status_code: int, error: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": error, "message": message},
    )


@router.post("/google", response_model=GoogleAuthResponse)
async def google_login(body: GoogleAuthRequest, db: AsyncSession = Depends(get_db)):
    logger.info("POST /api/auth/google — idToken present=%s", bool(body.idToken))
    if not body.idToken:
        logger.warning("google_login: missing idToken")
        return _error(
            status.HTTP_400_BAD_REQUEST,
            "Bad Request",
            "Required request body parameter 'idToken' is missing.",
        )

    try:
        payload = verify_google_token(body.idToken)
    except ValueError as e:
        logger.warning("google_login: token verification failed — %s", e)
        return _error(
            status.HTTP_401_UNAUTHORIZED,
            "Unauthorized",
            "Invalid google credential. Backend verification failed.",
        )

    google_id: str = payload.get("sub", "")
    name: str = payload.get("name", "")
    email: str | None = payload.get("email")
    avatar_url: str | None = payload.get("picture")
    logger.debug("google_login: google_id=%s email=%s", google_id, email)

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
        logger.info("google_login: new user created — user_id=%s email=%s", user.id, user.email)
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
            logger.debug("google_login: existing user profile updated — user_id=%s", user.id)
        else:
            logger.debug("google_login: existing user login — user_id=%s", user.id)

    try:
        access_token = create_access_token(user.id)
        raw_refresh, refresh_hash = generate_refresh_token()
        await store_refresh_token(user.id, refresh_hash, db)
        logger.info("google_login: tokens issued for user_id=%s", user.id)
    except Exception:
        logger.exception("google_login: failed to issue tokens for user_id=%s", user.id)
        raise

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
    logger.info("POST /api/auth/refresh — refreshToken present=%s", bool(body.refreshToken))
    if not body.refreshToken:
        logger.warning("refresh_token: missing refreshToken in body")
        return _error(
            status.HTTP_400_BAD_REQUEST,
            "Bad Request",
            "Required request body parameter 'refreshToken' is missing.",
        )

    try:
        new_raw_refresh, _, user_id = await rotate_refresh_token(body.refreshToken, db)
        logger.info("refresh_token: rotated successfully for user_id=%s", user_id)
    except HTTPException as e:
        logger.warning("refresh_token: rotation failed — %s", e.detail)
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
    logger.info("POST /api/auth/logout — user_id=%s", current_user.id)
    try:
        await db.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == current_user.id, RefreshToken.is_revoked == False)
            .values(is_revoked=True)
        )
        await db.commit()
        logger.info("logout: all refresh tokens revoked for user_id=%s", current_user.id)
    except Exception:
        logger.exception("logout: failed to revoke tokens for user_id=%s", current_user.id)
        raise

    return LogoutResponse(message="Successfully logged out and session token invalidated.")
