"""
Pydantic schemas for FastAPI request/response validation.

These models define what data the API accepts and returns.
FastAPI uses them to auto-generate documentation (Swagger UI).
"""

from datetime import date
from pydantic import BaseModel, field_validator


class TransactionCreate(BaseModel):
    """Request body for creating a transaction."""
    date: date
    description: str
    amount: float
    category: str | None = None

    @field_validator("description")
    @classmethod
    def description_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Description must not be empty")
        return v.strip()

    @field_validator("amount")
    @classmethod
    def amount_not_zero(cls, v: float) -> float:
        if v == 0:
            raise ValueError("Amount must not be zero")
        return round(v, 2)


class TransactionResponse(BaseModel):
    """Response for a single transaction."""
    id: int
    date: date
    description: str
    amount: float
    category: str
    transaction_type: str

    model_config = {"from_attributes": True}


class BudgetCreate(BaseModel):
    """Request body for setting a budget."""
    category: str
    monthly_limit: float

    @field_validator("monthly_limit")
    @classmethod
    def limit_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("Monthly limit must be positive")
        return round(v, 2)


class BudgetResponse(BaseModel):
    """Response for a single budget."""
    id: int
    category: str
    monthly_limit: float

    model_config = {"from_attributes": True}


class ImportResponse(BaseModel):
    """Response for a CSV import."""
    total_rows: int
    imported: int
    skipped: int
    errors: list[str]


class MessageResponse(BaseModel):
    """Simple message response."""
    message: str
