import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.schemas.user import TokenData

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

REFRESH_TOKEN_EXPIRE_DAYS = 30


def _truncate_password(password: str) -> str:
    return password.encode("utf-8")[:72].decode("utf-8", errors="ignore")


def hash_password(password: str) -> str:
    try:
        return pwd_context.hash(_truncate_password(password))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error hashing password: {str(e)}",
        )


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return pwd_context.verify(_truncate_password(plain_password), hashed_password)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error verifying password: {str(e)}",
        )


def create_access_token(user_id: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = {"sub": str(user_id), "exp": expire}
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def verify_token(token: str) -> TokenData | None:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id = int(payload.get("sub"))
        return TokenData(user_id=user_id)
    except (JWTError, ValueError, TypeError):
        return None


def _hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode()).hexdigest()


def generate_refresh_token() -> tuple[str, str]:
    raw = secrets.token_urlsafe(64)
    hashed = _hash_token(raw)
    return raw, hashed


async def store_refresh_token(user_id: int, token_hash: str, db: AsyncSession) -> None:
    from app.models.refresh_token import RefreshToken
    expires_at = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    record = RefreshToken(user_id=user_id, token_hash=token_hash, expires_at=expires_at)
    db.add(record)
    await db.commit()


async def rotate_refresh_token(
    old_raw_token: str,
    db: AsyncSession,
) -> tuple[str, str, int]:
    from app.models.refresh_token import RefreshToken

    old_hash = _hash_token(old_raw_token)
    result = await db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == old_hash)
    )
    record = result.scalar_one_or_none()

    if record is None or record.is_revoked:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    now = datetime.now(timezone.utc)
    expires_at = record.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < now:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token expired")

    user_id = record.user_id

    record.is_revoked = True
    await db.flush()

    new_raw, new_hash = generate_refresh_token()
    new_expires = now + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    new_record = RefreshToken(user_id=user_id, token_hash=new_hash, expires_at=new_expires)
    db.add(new_record)
    await db.commit()

    return new_raw, new_hash, user_id


async def revoke_refresh_token(raw_token: str, db: AsyncSession) -> None:
    from app.models.refresh_token import RefreshToken

    token_hash = _hash_token(raw_token)
    result = await db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    )
    record = result.scalar_one_or_none()
    if record and not record.is_revoked:
        record.is_revoked = True
        await db.commit()
