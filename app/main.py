from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text

from app.database import engine, Base
from app.models import user, group, expense, refresh_token  # noqa: F401 - ensure models are registered
from app.routers import auth, groups, expenses
from app.routers import google_auth, api_groups, api_dashboard


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text(
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS google_id VARCHAR(255) UNIQUE"
        ))
        await conn.execute(text(
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar_url VARCHAR(1024)"
        ))
        await conn.execute(text(
            "ALTER TABLE users ALTER COLUMN hashed_password DROP NOT NULL"
        ))
        await conn.execute(text(
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS phone_number VARCHAR(50)"
        ))
    yield


app = FastAPI(title="Splitwise Clone", lifespan=lifespan)
app.include_router(auth.router)
app.include_router(groups.router)
app.include_router(expenses.router)
app.include_router(google_auth.router)
app.include_router(api_groups.router)
app.include_router(api_dashboard.router)


@app.get("/")
async def root():
    return {"message": "Splitwise Clone API"}
