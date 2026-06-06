from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.schemas.user import GoogleAuthRequest, GoogleAuthResponse, GoogleUserProfile
from app.services.auth import create_access_token
from app.services.google_auth import verify_google_token

router = APIRouter(prefix="/api/auth", tags=["google-auth"])


@router.post("/google", response_model=GoogleAuthResponse)
async def google_login(body: GoogleAuthRequest, db: AsyncSession = Depends(get_db)):
    if not body.idToken:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Required request body parameter 'idToken' is missing.",
        )

    try:
        payload = verify_google_token(body.idToken)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid google credential. Backend verification failed.",
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

    return GoogleAuthResponse(
        token=access_token,
        user=GoogleUserProfile(
            id=str(user.id),
            name=user.name,
            email=user.email,
            avatarUrl=user.avatar_url,
        ),
    )
