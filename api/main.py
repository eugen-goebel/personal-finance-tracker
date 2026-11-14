"""
FastAPI application — REST API for the Personal Finance Tracker.

Provides endpoints for managing transactions, budgets, and analytics.
Auto-generates interactive API docs at /docs (Swagger UI).

To run:
    uvicorn api.main:app --reload
"""

import math
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

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


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    """Answer 422 as FastAPI does, minus an echoed NaN or infinity.

    FastAPI copies the rejected value into each error under "input". NaN and
    infinity cannot be encoded as JSON, so echoing a rejected non-finite amount
    would turn the 422 into a 500. Those values are left out; everything else
    stays as in FastAPI's default response.
    """
    errors = []
    for error in exc.errors():
        value = error.get("input")
        if isinstance(value, float) and not math.isfinite(value):
            error = {key: item for key, item in error.items() if key != "input"}
        errors.append(error)
    return JSONResponse(status_code=422, content={"detail": jsonable_encoder(errors)})


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
