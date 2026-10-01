from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text

from app.api.router import api_router
from app.config import settings
from app.database import Base, SessionLocal, engine
from app.services.seed import seed_if_empty


def _ensure_columns() -> None:
    """轻量迁移：create_all 不会给已存在的表补列，这里给旧库补 clearance_m。"""
    inspector = inspect(engine)
    if "pillars" in inspector.get_table_names():
        existing = {c["name"] for c in inspector.get_columns("pillars")}
        with engine.begin() as conn:
            if "clearance_m" not in existing:
                conn.execute(
                    text("ALTER TABLE pillars ADD COLUMN clearance_m FLOAT NOT NULL DEFAULT 0")
                )


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(bind=engine)
    _ensure_columns()
    if settings.seed_on_empty:
        db = SessionLocal()
        try:
            seed_if_empty(db)
        finally:
            db.close()
    yield


app = FastAPI(title="StallSpan", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router, prefix="/api")
