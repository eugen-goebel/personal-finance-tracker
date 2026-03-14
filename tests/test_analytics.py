"""Tests for AnalyticsAgent."""

from datetime import date

from agents.analytics import AnalyticsAgent
from agents.data_ingestion import DataIngestionAgent, TransactionInput


def _seed(db):
    """Add sample transactions for testing."""
    agent = DataIngestionAgent(db)
    data = [
        (date(2025, 1, 1), "Gehalt", 3000.00),
        (date(2025, 1, 5), "Miete", -850.00),
        (date(2025, 1, 10), "REWE", -65.00),
        (date(2025, 1, 15), "Netflix", -12.99),
        (date(2025, 2, 1), "Gehalt", 3000.00),
        (date(2025, 2, 5), "Miete", -850.00),
        (date(2025, 2, 10), "Edeka", -45.00),
    ]
    for d, desc, amt in data:
        agent.add_transaction(TransactionInput(date=d, description=desc, amount=amt))


class TestAnalytics:
    def test_empty_summary(self, db):
        result = AnalyticsAgent(db).get_summary()
        assert result.transaction_count == 0
        assert result.total_income == 0

    def test_totals(self, db):
        _seed(db)
        result = AnalyticsAgent(db).get_summary()
        assert result.total_income == 6000.00
        assert result.total_expenses > 0
        assert result.net_balance > 0

    def test_savings_rate(self, db):
        _seed(db)
        result = AnalyticsAgent(db).get_summary()
        assert 0 < result.savings_rate < 100

    def test_monthly_summaries(self, db):
        _seed(db)
        result = AnalyticsAgent(db).get_summary()
        assert len(result.monthly_summaries) == 2
        jan = result.monthly_summaries[0]
        assert jan.month == 1
        assert jan.total_income == 3000.00

    def test_category_breakdown(self, db):
        _seed(db)
        result = AnalyticsAgent(db).get_summary()
        assert len(result.category_breakdown) > 0
        categories = [c.category for c in result.category_breakdown]
        assert "Miete & Wohnen" in categories

    def test_category_percentages_sum_to_100(self, db):
        _seed(db)
        result = AnalyticsAgent(db).get_summary()
        total_pct = sum(c.percentage for c in result.category_breakdown)
        assert abs(total_pct - 100.0) < 0.5

    def test_trends(self, db):
        _seed(db)
        result = AnalyticsAgent(db).get_summary()
        assert len(result.trends) == 2
        assert result.trends[0].label == "2025-01"

    def test_top_expenses(self, db):
        _seed(db)
        result = AnalyticsAgent(db).get_summary()
        assert len(result.top_expenses) > 0
        # Largest expense should be rent
        assert result.top_expenses[0]["amount"] == 850.00

    def test_date_filter(self, db):
        _seed(db)
        result = AnalyticsAgent(db).get_summary(start_date=date(2025, 2, 1))
        assert result.total_income == 3000.00
        assert len(result.monthly_summaries) == 1
