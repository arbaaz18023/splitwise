from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.user import (
    UserCreate,
    UserResponse,
    LoginResponse,
    RefreshRequest,
    LogoutRequest,
)
from app.services.auth import (
    hash_password,
    verify_password,
    create_access_token,
    generate_refresh_token,
    store_refresh_token,
    rotate_refresh_token,
    revoke_refresh_token,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=LoginResponse, status_code=status.HTTP_201_CREATED)
async def signup(user_in: UserCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == user_in.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        email=user_in.email,
        name=user_in.name,
        hashed_password=hash_password(user_in.password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    access_token = create_access_token(user.id)
    raw_refresh, refresh_hash = generate_refresh_token()
    await store_refresh_token(user.id, refresh_hash, db)

    return LoginResponse(access_token=access_token, refresh_token=raw_refresh)


@router.post("/login", response_model=LoginResponse)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == form_data.username))
    user = result.scalar_one_or_none()
    if not user or not user.hashed_password or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    access_token = create_access_token(user.id)
    raw_refresh, refresh_hash = generate_refresh_token()
    await store_refresh_token(user.id, refresh_hash, db)

    return LoginResponse(access_token=access_token, refresh_token=raw_refresh)


@router.post("/refresh", response_model=LoginResponse)
async def refresh_token(body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    new_raw_refresh, _, user_id = await rotate_refresh_token(body.refresh_token, db)
    new_access_token = create_access_token(user_id)
    return LoginResponse(access_token=new_access_token, refresh_token=new_raw_refresh)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(body: LogoutRequest, db: AsyncSession = Depends(get_db)):
    await revoke_refresh_token(body.refresh_token, db)


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user
