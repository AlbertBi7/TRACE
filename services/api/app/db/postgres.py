"""
TRACE — PostgreSQL connection pool using asyncpg.
Provides acquire/release helpers for the async connection pool.
"""

import asyncpg
from typing import Optional

_pool: Optional[asyncpg.Pool] = None


async def init_postgres(dsn: str) -> asyncpg.Pool:
    """Initialize the connection pool. Called once at app startup."""
    global _pool
    _pool = await asyncpg.create_pool(
        dsn=dsn,
        min_size=2,
        max_size=10,
        command_timeout=30,
    )
    return _pool


async def get_pool() -> asyncpg.Pool:
    """Return the active connection pool."""
    if _pool is None:
        raise RuntimeError("PostgreSQL pool not initialized. Call init_postgres() first.")
    return _pool


async def close_postgres():
    """Close the pool. Called at app shutdown."""
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
