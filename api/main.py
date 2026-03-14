"""
FastAPI application — REST API for the Personal Finance Tracker.

Provides endpoints for managing transactions, budgets, and analytics.
Auto-generates interactive API docs at /docs (Swagger UI).

To run:
    uvicorn api.main:app --reload
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from db.database import init_db
from api.routes import transactions, analytics, budgets


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


@app.get("/", tags=["Health"])
def root():
    """Health check endpoint."""
    return {
        "status": "running",
        "app": "Personal Finance Tracker",
        "docs": "/docs",
    }
