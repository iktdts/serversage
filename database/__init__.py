# File: database/__init__.py

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool
import logging
from typing import AsyncGenerator
from contextlib import asynccontextmanager

from .models import Base

logger = logging.getLogger(__name__)

# Global engine and session factory
_engine = None
_async_session_factory = None


def init_engine(database_url: str, echo: bool = False):
    """
    Initialize the async database engine and session factory.
    Should be called once during application startup.
    
    Args:
        database_url: PostgreSQL connection URL (e.g., postgresql+asyncpg://user:pass@host/db)
        echo: Whether to log all SQL statements (useful for debugging)
    """
    global _engine, _async_session_factory
    
    if _engine is not None:
        logger.warning("Database engine already initialized. Skipping re-initialization.")
        return
    
    logger.info(f"Initializing database engine with URL: {database_url.split('@')[-1]}")  # Log without credentials
    
    _engine = create_async_engine(
        database_url,
        echo=echo,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
        pool_recycle=3600,  # Recycle connections after 1 hour
    )
    
    _async_session_factory = async_sessionmaker(
        _engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    logger.info("Database engine and session factory initialized successfully.")


async def create_tables():
    """
    Create all database tables defined in models.
    Should be called after init_engine during application startup.
    """
    global _engine
    
    if _engine is None:
        raise RuntimeError("Database engine not initialized. Call init_engine() first.")
    
    logger.info("Creating database tables...")
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created successfully.")


async def drop_tables():
    """
    Drop all database tables. USE WITH CAUTION - for development/testing only.
    """
    global _engine
    
    if _engine is None:
        raise RuntimeError("Database engine not initialized. Call init_engine() first.")
    
    logger.warning("Dropping all database tables...")
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    logger.warning("All database tables dropped.")


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Async context manager for getting a database session.
    
    Usage:
        async with get_session() as session:
            # Use session here
            result = await session.execute(...)
    """
    global _async_session_factory
    
    if _async_session_factory is None:
        raise RuntimeError("Session factory not initialized. Call init_engine() first.")
    
    async with _async_session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def close_engine():
    """
    Dispose of the database engine and close all connections.
    Should be called during application shutdown.
    """
    global _engine, _async_session_factory
    
    if _engine is not None:
        logger.info("Closing database engine...")
        await _engine.dispose()
        _engine = None
        _async_session_factory = None
        logger.info("Database engine closed.")


# Re-export models for convenience
from .models import Role, AssignedRole, RoleHistory, UnmappedSkill, UserPreference

__all__ = [
    "init_engine",
    "create_tables",
    "drop_tables",
    "get_session",
    "close_engine",
    "Role",
    "AssignedRole",
    "RoleHistory",
    "UnmappedSkill",
    "UserPreference",
]
