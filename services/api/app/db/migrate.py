"""
TRACE — PostgreSQL Migration Runner
Applies idempotent SQL migrations from db/postgres/migrations at API startup.
Tracks applied files in schema_migrations so each runs at most once.
"""

import asyncpg
import logging
from pathlib import Path

logger = logging.getLogger("trace.migrate")


async def run_migrations(dsn: str, migrations_dir: str) -> None:
    """Apply all not-yet-applied *.sql files in migrations_dir, in filename order."""
    conn = await asyncpg.connect(dsn)
    try:
        await conn.execute(
            """CREATE TABLE IF NOT EXISTS schema_migrations (
                   filename   VARCHAR(255) PRIMARY KEY,
                   applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
               )"""
        )
        applied = {r["filename"] for r in await conn.fetch("SELECT filename FROM schema_migrations")}

        files = sorted(Path(migrations_dir).glob("*.sql"))
        if not files:
            logger.warning(f"No migration files found in {migrations_dir}")
            return

        for f in files:
            if f.name in applied:
                continue
            sql = f.read_text(encoding="utf-8")
            async with conn.transaction():
                await conn.execute(sql)
                await conn.execute("INSERT INTO schema_migrations (filename) VALUES ($1)", f.name)
            logger.info(f"Applied migration: {f.name}")
    finally:
        await conn.close()
