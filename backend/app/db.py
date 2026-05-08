from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncGenerator

from sqlalchemy import DateTime, event, TypeDecorator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

_DB_PATH = Path(__file__).resolve().parent.parent / "vision.db"
engine = create_async_engine(f"sqlite+aiosqlite:///{_DB_PATH}", echo=False)
async_session = async_sessionmaker(engine, expire_on_commit=False)


@event.listens_for(engine.sync_engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()


class TZDateTime(TypeDecorator):
    """DateTime that ensures all values read from DB are UTC-aware.

    SQLite doesn't persist timezone info, so naive datetimes are re-tagged UTC.
    """
    impl = DateTime
    cache_ok = True

    def process_result_value(self, value, dialect):
        if value is not None and isinstance(value, datetime) and value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
