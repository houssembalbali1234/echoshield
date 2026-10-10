from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.auth import router as auth_router
from app.api.circles import router as circles_router
from app.api.health import router as health_router
from app.core.config import get_settings
from app.core.redis import redis_client
from app.db.session import engine

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await redis_client.aclose()
    await engine.dispose()


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)

app.include_router(health_router, prefix="/api")
app.include_router(auth_router, prefix="/api")
app.include_router(circles_router, prefix="/api")