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


# ---------------------------------------------------------------------------
# Savings goals
# ---------------------------------------------------------------------------

class GoalCreate(BaseModel):
    """Payload to create a savings goal."""
    name: str
    target_amount: float
    current_amount: float = 0.0
    target_date: date | None = None

    @field_validator("target_amount")
    @classmethod
    def target_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("target_amount must be positive")
        return round(v, 2)

    @field_validator("current_amount")
    @classmethod
    def current_non_negative(cls, v: float) -> float:
        if v < 0:
            raise ValueError("current_amount cannot be negative")
        return round(v, 2)


class GoalUpdate(BaseModel):
    """Payload to partially update a savings goal."""
    name: str | None = None
    target_amount: float | None = None
    current_amount: float | None = None
    target_date: date | None = None
    clear_target_date: bool = False


class GoalContribution(BaseModel):
    """Payload to add to current_amount of a goal."""
    amount: float

    @field_validator("amount")
    @classmethod
    def positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("contribution must be positive")
        return round(v, 2)


class GoalProgressResponse(BaseModel):
    progress_pct: float
    remaining_amount: float
    days_left: int | None
    monthly_contribution_needed: float | None


class GoalResponse(BaseModel):
    """Response for a savings goal including computed progress."""
    id: int
    name: str
    target_amount: float
    current_amount: float
    target_date: date | None
    progress: GoalProgressResponse

    model_config = {"from_attributes": True}
