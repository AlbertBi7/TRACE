"""
TRACE — FastAPI Application Entry Point
Bootstraps the app: lifespan events, middleware, and router mounting.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.config import settings
from app.db.postgres import init_postgres, close_postgres
from app.db.migrate import run_migrations
from app.db.neo4j_driver import init_neo4j, close_neo4j
from app.auth.security import hash_password
import logging
import uuid

logger = logging.getLogger("trace")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan: initialize DB connections on startup, clean up on shutdown.
    Also seeds the demo accounts if they don't exist (for local dev convenience).
    """
    logger.info("Starting TRACE API...")

    # Initialize PostgreSQL
    pool = await init_postgres(settings.database_url)
    logger.info("PostgreSQL connected")

    # Apply pending migrations (idempotent, tracked in schema_migrations)
    try:
        await run_migrations(settings.database_url, settings.migrations_dir)
    except Exception as e:
        logger.warning(f"Migration run skipped/failed (non-fatal): {e}")

    # Initialize Neo4j
    try:
        await init_neo4j(settings.neo4j_uri, settings.neo4j_user, settings.neo4j_password)
        logger.info("Neo4j connected")
    except Exception as e:
        logger.warning(f"Neo4j connection failed (will retry on use): {e}")

    # Seed demo accounts once. Idempotent: existing rows are never modified,
    # so admin password resets survive API restarts.
    try:
        demo_accounts = [
            {
                "id": "a0000000-0000-0000-0000-000000000001",
                "email": "admin@trace.dev",
                "password": "TraceAdmin123!",
                "full_name": "System Administrator",
                "role": "admin",
            },
            {
                "id": "a0000000-0000-0000-0000-000000000002",
                "email": "investigator@trace.dev",
                "password": "TraceInvestigator123!",
                "full_name": "Demo Investigator",
                "role": "investigator",
            },
        ]
        for acct in demo_accounts:
            existing = await pool.fetchval("SELECT 1 FROM users WHERE email = $1", acct["email"])
            if existing:
                continue
            await pool.execute(
                """INSERT INTO users (id, email, password_hash, full_name, role, is_active)
                   VALUES ($1, $2, $3, $4, $5, true)
                   ON CONFLICT (email) DO NOTHING""",
                acct["id"],
                acct["email"],
                hash_password(acct["password"]),
                acct["full_name"],
                acct["role"],
            )
            logger.info(f"Seeded demo account: {acct['email']}")
        # NOTE: demo emails use .dev — pydantic's EmailStr (email-validator) rejects
        # .local/.localhost/.test etc. as special-use domains, which broke login.

    except Exception as e:
        logger.warning(f"Seed check skipped (tables may not exist yet): {e}")

    yield

    # Shutdown
    logger.info("Shutting down TRACE API...")
    await close_postgres()
    await close_neo4j()
    logger.info("Shutdown complete")


app = FastAPI(
    title="TRACE API",
    description="TRACE — AI-powered network analysis for investigative teams. An explainable co-pilot that surfaces evidence; humans decide.",
    version="1.0.0",
    lifespan=lifespan,
)

# ─── CORS ─────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url, "http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Global Exception Handler ─────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


# ─── Mount Routers ────────────────────────────────────────
from app.auth.router import router as auth_router
from app.routers.users import router as users_router
from app.routers.cases import router as cases_router
from app.routers.documents import router as documents_router
from app.routers.extraction import router as extraction_router
from app.routers.resolution import router as resolution_router
from app.routers.graph import router as graph_router
from app.routers.analysis import router as analysis_router
from app.routers.chat import router as chat_router
from app.routers.audit import router as audit_router

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(cases_router)
app.include_router(documents_router)
app.include_router(extraction_router)
app.include_router(resolution_router)
app.include_router(graph_router)
app.include_router(analysis_router)
app.include_router(chat_router)
app.include_router(audit_router)


# ─── Health Check ─────────────────────────────────────────
@app.get("/api/health", tags=["system"])
async def health_check():
    """Health check endpoint for Docker and monitoring."""
    return {"status": "healthy", "service": "trace-api"}
