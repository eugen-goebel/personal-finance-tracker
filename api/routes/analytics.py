"""Analytics API routes — financial summaries and trends."""

from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from db.database import get_db
from agents.analytics import AnalyticsAgent

router = APIRouter(prefix="/api/analytics", tags=["Analytics"])


@router.get("/summary")
def get_summary(
    start_date: date | None = None,
    end_date: date | None = None,
    db: Session = Depends(get_db),
):
    """Get a complete financial summary with metrics and trends."""
    agent = AnalyticsAgent(db)
    result = agent.get_summary(start_date, end_date)

    return {
        "total_income": result.total_income,
        "total_expenses": result.total_expenses,
        "net_balance": result.net_balance,
        "savings_rate": result.savings_rate,
        "transaction_count": result.transaction_count,
    }


@router.get("/categories")
def get_categories(
    start_date: date | None = None,
    end_date: date | None = None,
    db: Session = Depends(get_db),
):
    """Get spending breakdown by category."""
    agent = AnalyticsAgent(db)
    result = agent.get_summary(start_date, end_date)

    return [
        {
            "category": c.category,
            "total": c.total,
            "percentage": c.percentage,
            "transaction_count": c.transaction_count,
        }
        for c in result.category_breakdown
    ]


@router.get("/trends")
def get_trends(
    start_date: date | None = None,
    end_date: date | None = None,
    db: Session = Depends(get_db),
):
    """Get monthly income/expense trends."""
    agent = AnalyticsAgent(db)
    result = agent.get_summary(start_date, end_date)

    return [
        {
            "label": t.label,
            "income": t.income,
            "expenses": t.expenses,
            "net": t.net,
        }
        for t in result.trends
    ]
