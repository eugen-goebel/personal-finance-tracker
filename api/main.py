"""
FastAPI application — REST API for the Personal Finance Tracker.

Provides endpoints for managing transactions, budgets, and analytics.
Auto-generates interactive API docs at /docs (Swagger UI).

To run:
    uvicorn api.main:app --reload
"""

from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI

# Load .env before the imports below, so db.database sees DATABASE_URL when it
# reads it at module level. Real environment variables still win, which is how
# docker-compose passes the database location.
load_dotenv()

from api.routes import analytics, budgets, savings_goals, transactions  # noqa: E402
from db.database import init_db  # noqa: E402


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create database tables on startup."""
    init_db()
    yield


app = FastAPI(
    title="Personal Finance Tracker API",
    description="Manage transactions, budgets, and financial analytics",
    version="1.0.0",
    lifespan=lifespan,
)

# Register route modules
app.include_router(transactions.router)
app.include_router(analytics.router)
app.include_router(budgets.router)
app.include_router(savings_goals.router)


@app.get("/", tags=["Health"])
def root():
    """Health check endpoint."""
    return {
        "status": "running",
        "app": "Personal Finance Tracker",
        "docs": "/docs",
    }
