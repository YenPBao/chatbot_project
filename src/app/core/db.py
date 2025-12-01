from __future__ import annotations
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import ( AsyncSession, async_sessionmaker, create_async_engine,)
from sqlalchemy.orm import DeclarativeBase
from app.core.config import settings  


DB_URL = settings.database_url
if DB_URL is None:
    raise RuntimeError("DATABASE_URL is not set. Put it in your .env or ENV.")

engine = create_async_engine(
    DB_URL,
    echo=settings.debug,     
    pool_pre_ping=True,      
    future=True,
)

SessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    autoflush=False,
    expire_on_commit=False,  
)

class Base(DeclarativeBase):
    pass

@asynccontextmanager
async def session_factory() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as db:
        try:
            yield db
            await db.commit()
        except Exception:
            await db.rollback()
            raise

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with session_factory() as db:
        yield db
