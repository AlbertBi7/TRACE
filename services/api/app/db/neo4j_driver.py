"""
TRACE — Neo4j driver singleton.
Provides session helpers and parameterized Cypher execution.
"""

from neo4j import AsyncGraphDatabase, AsyncDriver
from typing import Optional, Any

_driver: Optional[AsyncDriver] = None


async def init_neo4j(uri: str, user: str, password: str) -> AsyncDriver:
    """Initialize the Neo4j driver. Called once at app startup."""
    global _driver
    _driver = AsyncGraphDatabase.driver(uri, auth=(user, password))
    # Verify connectivity
    await _driver.verify_connectivity()
    return _driver


def get_driver() -> AsyncDriver:
    """Return the active Neo4j driver."""
    if _driver is None:
        raise RuntimeError("Neo4j driver not initialized. Call init_neo4j() first.")
    return _driver


async def run_cypher(query: str, parameters: dict[str, Any] | None = None, db: str = "neo4j") -> list[dict]:
    """Execute a parameterized Cypher query and return results as list of dicts."""
    driver = get_driver()
    async with driver.session(database=db) as session:
        result = await session.run(query, parameters or {})
        records = await result.data()
        return records


async def close_neo4j():
    """Close the driver. Called at app shutdown."""
    global _driver
    if _driver:
        await _driver.close()
        _driver = None
