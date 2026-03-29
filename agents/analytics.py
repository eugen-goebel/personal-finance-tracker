"""
AnalyticsAgent — Calculates financial metrics and trends.

Computes monthly summaries, savings rates, spending breakdowns,
and trend analysis from transaction data.
"""

from datetime import date
from dataclasses import dataclass, field

from sqlalchemy import func
from sqlalchemy.orm import Session

from db.models import Transaction


@dataclass
class MonthlySummary:
    """Financial summary for a single month."""
    year: int
    month: int
    total_income: float
    total_expenses: float
    net: float
    savings_rate: float  # percentage
    transaction_count: int


@dataclass
class CategoryBreakdown:
    """Spending breakdown for a category."""
    category: str
    total: float
    percentage: float
    transaction_count: int


@dataclass
class Trend:
    """Monthly trend data point."""
    year: int
    month: int
    label: str  # "2025-01"
    income: float
    expenses: float
    net: float


@dataclass
class AnalyticsResult:
    """Complete analytics overview."""
    total_income: float
    total_expenses: float
    net_balance: float
    savings_rate: float
    monthly_summaries: list[MonthlySummary]
    category_breakdown: list[CategoryBreakdown]
    trends: list[Trend]
    top_expenses: list[dict]
    transaction_count: int


class AnalyticsAgent:
    """Computes financial analytics from transaction data."""

    def __init__(self, db: Session):
        self.db = db

    def get_summary(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> AnalyticsResult:
        """Calculate a full analytics summary."""
        query = self.db.query(Transaction)
        if start_date:
            query = query.filter(Transaction.date >= start_date)
        if end_date:
            query = query.filter(Transaction.date <= end_date)

        transactions = query.order_by(Transaction.date).all()

        if not transactions:
            return AnalyticsResult(
                total_income=0, total_expenses=0, net_balance=0,
                savings_rate=0, monthly_summaries=[], category_breakdown=[],
                trends=[], top_expenses=[], transaction_count=0,
            )

        total_income = sum(t.amount for t in transactions if t.amount > 0)
        total_expenses = sum(abs(t.amount) for t in transactions if t.amount < 0)
        net = total_income - total_expenses
        savings_rate = (net / total_income * 100) if total_income > 0 else 0

        return AnalyticsResult(
            total_income=round(total_income, 2),
            total_expenses=round(total_expenses, 2),
            net_balance=round(net, 2),
            savings_rate=round(savings_rate, 1),
            monthly_summaries=self._monthly_summaries(transactions),
            category_breakdown=self._category_breakdown(transactions),
            trends=self._trends(transactions),
            top_expenses=self._top_expenses(transactions),
            transaction_count=len(transactions),
        )

    def _monthly_summaries(self, transactions: list[Transaction]) -> list[MonthlySummary]:
        """Group transactions by month and calculate summaries."""
        months: dict[tuple[int, int], list[Transaction]] = {}
        for t in transactions:
            key = (t.date.year, t.date.month)
            months.setdefault(key, []).append(t)

        summaries = []
        for (year, month), txns in sorted(months.items()):
            income = sum(t.amount for t in txns if t.amount > 0)
            expenses = sum(abs(t.amount) for t in txns if t.amount < 0)
            net = income - expenses
            rate = (net / income * 100) if income > 0 else 0

            summaries.append(MonthlySummary(
                year=year, month=month,
                total_income=round(income, 2),
                total_expenses=round(expenses, 2),
                net=round(net, 2),
                savings_rate=round(rate, 1),
                transaction_count=len(txns),
            ))
        return summaries

    def _category_breakdown(self, transactions: list[Transaction]) -> list[CategoryBreakdown]:
        """Calculate spending per category (expenses only)."""
        expenses = [t for t in transactions if t.amount < 0]
        if not expenses:
            return []

        total = sum(abs(t.amount) for t in expenses)
        categories: dict[str, list[Transaction]] = {}
        for t in expenses:
            categories.setdefault(t.category, []).append(t)

        breakdown = []
        for cat, txns in categories.items():
            cat_total = sum(abs(t.amount) for t in txns)
            breakdown.append(CategoryBreakdown(
                category=cat,
                total=round(cat_total, 2),
                percentage=round(cat_total / total * 100, 1),
                transaction_count=len(txns),
            ))

        return sorted(breakdown, key=lambda x: x.total, reverse=True)

    def _trends(self, transactions: list[Transaction]) -> list[Trend]:
        """Calculate monthly income/expense trends."""
        months: dict[tuple[int, int], list[Transaction]] = {}
        for t in transactions:
            key = (t.date.year, t.date.month)
            months.setdefault(key, []).append(t)

        trends = []
        for (year, month), txns in sorted(months.items()):
            income = sum(t.amount for t in txns if t.amount > 0)
            expenses = sum(abs(t.amount) for t in txns if t.amount < 0)
            trends.append(Trend(
                year=year, month=month,
                label=f"{year}-{month:02d}",
                income=round(income, 2),
                expenses=round(expenses, 2),
                net=round(income - expenses, 2),
            ))
        return trends

    def _top_expenses(self, transactions: list[Transaction], limit: int = 10) -> list[dict]:
        """Return the largest single expenses."""
        expenses = [t for t in transactions if t.amount < 0]
        expenses.sort(key=lambda t: t.amount)  # most negative first

        return [
            {
                "date": str(t.date),
                "description": t.description,
                "amount": round(abs(t.amount), 2),
                "category": t.category,
            }
            for t in expenses[:limit]
        ]
