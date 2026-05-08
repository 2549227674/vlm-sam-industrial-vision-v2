from pathlib import Path
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

_DB_PATH = Path(__file__).resolve().parent.parent / "vision.db"
engine = create_async_engine(f"sqlite+aiosqlite:///{_DB_PATH}", echo=False)
async_session = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        yield session
