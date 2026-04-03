"""Budget API routes — manage spending limits and check status."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from db.database import get_db
from api.schemas import BudgetCreate, BudgetResponse, MessageResponse
from agents.budget import BudgetAgent
from agents.alert_service import AlertService

router = APIRouter(prefix="/api/budgets", tags=["Budgets"])


@router.post("/", response_model=BudgetResponse, status_code=201)
def set_budget(data: BudgetCreate, db: Session = Depends(get_db)):
    """Set or update a monthly budget for a category."""
    agent = BudgetAgent(db)
    budget = agent.set_budget(data.category, data.monthly_limit)
    return budget


@router.get("/", response_model=list[BudgetResponse])
def list_budgets(db: Session = Depends(get_db)):
    """List all configured budgets."""
    agent = BudgetAgent(db)
    return agent.get_budgets()


@router.delete("/{category}", response_model=MessageResponse)
def delete_budget(category: str, db: Session = Depends(get_db)):
    """Delete a budget by category."""
    agent = BudgetAgent(db)
    if not agent.delete_budget(category):
        raise HTTPException(status_code=404, detail="Budget not found")
    return {"message": f"Budget for '{category}' deleted"}


@router.get("/status")
def budget_status(
    year: int | None = None,
    month: int | None = None,
    db: Session = Depends(get_db),
):
    """Check spending against budgets for a given month (defaults to current)."""
    today = date.today()
    y = year or today.year
    m = month or today.month

    agent = BudgetAgent(db)
    overview = agent.get_status(y, m)

    return {
        "year": overview.year,
        "month": overview.month,
        "total_budget": overview.total_budget,
        "total_spent": overview.total_spent,
        "warnings": overview.warnings,
        "budgets": [
            {
                "category": b.category,
                "monthly_limit": b.monthly_limit,
                "spent": b.spent,
                "remaining": b.remaining,
                "percentage_used": b.percentage_used,
                "status": b.status,
            }
            for b in overview.budgets
        ],
    }


@router.post("/alerts")
def send_budget_alerts(
    year: int | None = None,
    month: int | None = None,
    dry_run: bool = True,
    db: Session = Depends(get_db),
):
    """Check budgets and send alert emails for exceeded/warning thresholds."""
    service = AlertService(db)
    result = service.check_and_alert(year=year, month=month, dry_run=dry_run)

    return {
        "year": result.year,
        "month": result.month,
        "alerts_triggered": result.alerts_triggered,
        "warnings": result.warnings,
        "email_sent": result.email_sent,
        "error": result.error,
    }
