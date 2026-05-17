from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.database import engine, Base
from app.models import user, group, expense  # noqa: F401 - ensure models are registered
from app.routers import auth, groups, expenses


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(title="Splitwise Clone", lifespan=lifespan)
app.include_router(auth.router)
app.include_router(groups.router)
app.include_router(expenses.router)


@app.get("/")
async def root():
    return {"message": "Splitwise Clone API"}
