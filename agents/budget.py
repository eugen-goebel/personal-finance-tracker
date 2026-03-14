"""
BudgetAgent — Manages spending budgets and generates warnings.

Allows setting monthly limits per category and checks
current spending against those limits.
"""

from datetime import date
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from db.models import Budget, Transaction


@dataclass
class BudgetStatus:
    """Status of a single budget category."""
    category: str
    monthly_limit: float
    spent: float
    remaining: float
    percentage_used: float
    status: str  # "ok", "warning", "exceeded"


@dataclass
class BudgetOverview:
    """Overview of all budgets for a given month."""
    year: int
    month: int
    budgets: list[BudgetStatus]
    warnings: list[str]
    total_budget: float
    total_spent: float


class BudgetAgent:
    """Manages budgets and monitors spending limits."""

    WARNING_THRESHOLD = 80  # warn at 80% usage

    def __init__(self, db: Session):
        self.db = db

    def set_budget(self, category: str, monthly_limit: float) -> Budget:
        """Set or update a monthly budget for a category."""
        existing = (
            self.db.query(Budget)
            .filter(Budget.category == category)
            .first()
        )

        if existing:
            existing.monthly_limit = monthly_limit
            self.db.commit()
            self.db.refresh(existing)
            return existing

        budget = Budget(category=category, monthly_limit=monthly_limit)
        self.db.add(budget)
        self.db.commit()
        self.db.refresh(budget)
        return budget

    def get_budgets(self) -> list[Budget]:
        """Return all configured budgets."""
        return self.db.query(Budget).order_by(Budget.category).all()

    def delete_budget(self, category: str) -> bool:
        """Delete a budget by category name."""
        budget = (
            self.db.query(Budget)
            .filter(Budget.category == category)
            .first()
        )
        if budget:
            self.db.delete(budget)
            self.db.commit()
            return True
        return False

    def get_status(self, year: int, month: int) -> BudgetOverview:
        """Check spending against budgets for a specific month."""
        budgets = self.get_budgets()

        # Get expenses for the given month
        expenses = (
            self.db.query(Transaction)
            .filter(
                Transaction.amount < 0,
                Transaction.date >= date(year, month, 1),
                Transaction.date < self._next_month(year, month),
            )
            .all()
        )

        # Sum spending per category
        spending: dict[str, float] = {}
        for t in expenses:
            spending[t.category] = spending.get(t.category, 0) + abs(t.amount)

        statuses = []
        warnings = []
        total_budget = 0
        total_spent = 0

        for budget in budgets:
            spent = round(spending.get(budget.category, 0), 2)
            remaining = round(budget.monthly_limit - spent, 2)
            pct = round(spent / budget.monthly_limit * 100, 1) if budget.monthly_limit > 0 else 0

            if pct >= 100:
                status = "exceeded"
                warnings.append(
                    f"{budget.category}: Budget exceeded! "
                    f"{spent:.2f} / {budget.monthly_limit:.2f} ({pct:.0f}%)"
                )
            elif pct >= self.WARNING_THRESHOLD:
                status = "warning"
                warnings.append(
                    f"{budget.category}: Approaching limit — "
                    f"{spent:.2f} / {budget.monthly_limit:.2f} ({pct:.0f}%)"
                )
            else:
                status = "ok"

            statuses.append(BudgetStatus(
                category=budget.category,
                monthly_limit=budget.monthly_limit,
                spent=spent,
                remaining=remaining,
                percentage_used=pct,
                status=status,
            ))

            total_budget += budget.monthly_limit
            total_spent += spent

        return BudgetOverview(
            year=year, month=month,
            budgets=statuses,
            warnings=warnings,
            total_budget=round(total_budget, 2),
            total_spent=round(total_spent, 2),
        )

    @staticmethod
    def _next_month(year: int, month: int) -> date:
        """Return the first day of the next month."""
        if month == 12:
            return date(year + 1, 1, 1)
        return date(year, month + 1, 1)
