"""Tests for DataIngestionAgent."""

import pytest
from datetime import date

from agents.data_ingestion import DataIngestionAgent, TransactionInput
from db.models import Transaction


class TestDataIngestion:
    def test_add_expense(self, db):
        agent = DataIngestionAgent(db)
        txn = agent.add_transaction(TransactionInput(
            date=date(2025, 1, 15), description="REWE Einkauf", amount=-50.00,
        ))
        assert txn.id is not None
        assert txn.transaction_type == "expense"
        assert txn.category == "Lebensmittel"

    def test_add_income(self, db):
        agent = DataIngestionAgent(db)
        txn = agent.add_transaction(TransactionInput(
            date=date(2025, 1, 1), description="Gehalt", amount=3200.00,
        ))
        assert txn.transaction_type == "income"
        assert txn.category == "Gehalt"

    def test_custom_category(self, db):
        agent = DataIngestionAgent(db)
        txn = agent.add_transaction(TransactionInput(
            date=date(2025, 1, 1), description="Something",
            amount=-20.00, category="Custom",
        ))
        assert txn.category == "Custom"

    def test_auto_categorize(self, db):
        agent = DataIngestionAgent(db)
        txn = agent.add_transaction(TransactionInput(
            date=date(2025, 1, 1), description="Netflix Abo", amount=-12.99,
        ))
        assert txn.category == "Unterhaltung"

    def test_get_transactions(self, db):
        agent = DataIngestionAgent(db)
        agent.add_transaction(TransactionInput(
            date=date(2025, 1, 1), description="Gehalt", amount=3000.00,
        ))
        agent.add_transaction(TransactionInput(
            date=date(2025, 1, 5), description="Miete", amount=-850.00,
        ))
        txns = agent.get_transactions()
        assert len(txns) == 2

    def test_filter_by_type(self, db):
        agent = DataIngestionAgent(db)
        agent.add_transaction(TransactionInput(
            date=date(2025, 1, 1), description="Gehalt", amount=3000.00,
        ))
        agent.add_transaction(TransactionInput(
            date=date(2025, 1, 5), description="Miete", amount=-850.00,
        ))
        income = agent.get_transactions(transaction_type="income")
        assert len(income) == 1
        assert income[0].amount > 0

    def test_filter_by_date(self, db):
        agent = DataIngestionAgent(db)
        agent.add_transaction(TransactionInput(
            date=date(2025, 1, 1), description="A", amount=-10.00,
        ))
        agent.add_transaction(TransactionInput(
            date=date(2025, 2, 1), description="B", amount=-20.00,
        ))
        txns = agent.get_transactions(start_date=date(2025, 1, 15))
        assert len(txns) == 1

    def test_delete_transaction(self, db):
        agent = DataIngestionAgent(db)
        txn = agent.add_transaction(TransactionInput(
            date=date(2025, 1, 1), description="Test", amount=-10.00,
        ))
        assert agent.delete_transaction(txn.id) is True
        assert agent.delete_transaction(999) is False

    def test_import_csv(self, db):
        csv = "date,description,amount\n2025-01-01,Gehalt,3000\n2025-01-05,Miete,-850\n"
        agent = DataIngestionAgent(db)
        result = agent.import_csv(csv)
        assert result.total_rows == 2
        assert result.imported == 2
        assert result.skipped == 0

    def test_import_csv_with_errors(self, db):
        csv = "date,description,amount\n2025-01-01,Test,abc\n"
        agent = DataIngestionAgent(db)
        result = agent.import_csv(csv)
        assert result.skipped == 1
        assert len(result.errors) == 1

    def test_import_missing_columns(self, db):
        csv = "date,amount\n2025-01-01,100\n"
        agent = DataIngestionAgent(db)
        result = agent.import_csv(csv)
        assert len(result.errors) > 0
        assert result.imported == 0

    def test_validation_empty_description(self):
        with pytest.raises(ValueError):
            TransactionInput(date=date(2025, 1, 1), description="  ", amount=-10)

    def test_validation_zero_amount(self):
        with pytest.raises(ValueError):
            TransactionInput(date=date(2025, 1, 1), description="Test", amount=0)
