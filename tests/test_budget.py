"""Tests for BudgetAgent."""

from datetime import date

from agents.budget import BudgetAgent
from agents.data_ingestion import DataIngestionAgent, TransactionInput


def _add_expenses(db):
    """Add expenses for January 2025."""
    agent = DataIngestionAgent(db)
    expenses = [
        (date(2025, 1, 3), "REWE", -65.00, "Lebensmittel"),
        (date(2025, 1, 10), "Edeka", -45.00, "Lebensmittel"),
        (date(2025, 1, 5), "Miete", -850.00, "Miete & Wohnen"),
        (date(2025, 1, 12), "Netflix", -12.99, "Unterhaltung"),
    ]
    for d, desc, amt, cat in expenses:
        agent.add_transaction(TransactionInput(
            date=d, description=desc, amount=amt, category=cat,
        ))


class TestBudget:
    def test_set_budget(self, db):
        agent = BudgetAgent(db)
        budget = agent.set_budget("Lebensmittel", 200.00)
        assert budget.id is not None
        assert budget.monthly_limit == 200.00

    def test_update_budget(self, db):
        agent = BudgetAgent(db)
        agent.set_budget("Lebensmittel", 200.00)
        updated = agent.set_budget("Lebensmittel", 300.00)
        assert updated.monthly_limit == 300.00
        assert len(agent.get_budgets()) == 1

    def test_delete_budget(self, db):
        agent = BudgetAgent(db)
        agent.set_budget("Lebensmittel", 200.00)
        assert agent.delete_budget("Lebensmittel") is True
        assert agent.delete_budget("Nonexistent") is False
        assert len(agent.get_budgets()) == 0

    def test_status_ok(self, db):
        _add_expenses(db)
        agent = BudgetAgent(db)
        agent.set_budget("Lebensmittel", 200.00)
        overview = agent.get_status(2025, 1)
        lb = overview.budgets[0]
        assert lb.spent == 110.00
        assert lb.status == "ok"
        assert len(overview.warnings) == 0

    def test_status_warning(self, db):
        _add_expenses(db)
        agent = BudgetAgent(db)
        agent.set_budget("Lebensmittel", 120.00)  # 110/120 = 91.7%
        overview = agent.get_status(2025, 1)
        lb = overview.budgets[0]
        assert lb.status == "warning"
        assert len(overview.warnings) == 1

    def test_status_exceeded(self, db):
        _add_expenses(db)
        agent = BudgetAgent(db)
        agent.set_budget("Lebensmittel", 100.00)  # 110/100 = 110%
        overview = agent.get_status(2025, 1)
        lb = overview.budgets[0]
        assert lb.status == "exceeded"
        assert lb.percentage_used > 100

    def test_no_spending_shows_zero(self, db):
        agent = BudgetAgent(db)
        agent.set_budget("Shopping", 300.00)
        overview = agent.get_status(2025, 1)
        assert overview.budgets[0].spent == 0
        assert overview.budgets[0].status == "ok"

    def test_multiple_budgets(self, db):
        _add_expenses(db)
        agent = BudgetAgent(db)
        agent.set_budget("Lebensmittel", 200.00)
        agent.set_budget("Unterhaltung", 30.00)
        overview = agent.get_status(2025, 1)
        assert len(overview.budgets) == 2

    def test_total_budget(self, db):
        agent = BudgetAgent(db)
        agent.set_budget("Lebensmittel", 200.00)
        agent.set_budget("Transport", 100.00)
        overview = agent.get_status(2025, 1)
        assert overview.total_budget == 300.00
