"""Tests for DataIngestionAgent."""

from datetime import date

import pytest

from agents.data_ingestion import DataIngestionAgent, TransactionInput
from db.models import Transaction


class TestDataIngestion:
    def test_add_expense(self, db):
        agent = DataIngestionAgent(db)
        txn = agent.add_transaction(
            TransactionInput(
                date=date(2025, 1, 15),
                description="REWE Einkauf",
                amount=-50.00,
            )
        )
        assert txn.id is not None
        assert txn.transaction_type == "expense"
        assert txn.category == "Lebensmittel"

    def test_add_income(self, db):
        agent = DataIngestionAgent(db)
        txn = agent.add_transaction(
            TransactionInput(
                date=date(2025, 1, 1),
                description="Gehalt",
                amount=3200.00,
            )
        )
        assert txn.transaction_type == "income"
        assert txn.category == "Gehalt"

    def test_custom_category(self, db):
        agent = DataIngestionAgent(db)
        txn = agent.add_transaction(
            TransactionInput(
                date=date(2025, 1, 1),
                description="Something",
                amount=-20.00,
                category="Custom",
            )
        )
        assert txn.category == "Custom"

    def test_auto_categorize(self, db):
        agent = DataIngestionAgent(db)
        txn = agent.add_transaction(
            TransactionInput(
                date=date(2025, 1, 1),
                description="Netflix Abo",
                amount=-12.99,
            )
        )
        assert txn.category == "Unterhaltung"

    def test_get_transactions(self, db):
        agent = DataIngestionAgent(db)
        agent.add_transaction(
            TransactionInput(
                date=date(2025, 1, 1),
                description="Gehalt",
                amount=3000.00,
            )
        )
        agent.add_transaction(
            TransactionInput(
                date=date(2025, 1, 5),
                description="Miete",
                amount=-850.00,
            )
        )
        txns = agent.get_transactions()
        assert len(txns) == 2

    def test_filter_by_type(self, db):
        agent = DataIngestionAgent(db)
        agent.add_transaction(
            TransactionInput(
                date=date(2025, 1, 1),
                description="Gehalt",
                amount=3000.00,
            )
        )
        agent.add_transaction(
            TransactionInput(
                date=date(2025, 1, 5),
                description="Miete",
                amount=-850.00,
            )
        )
        income = agent.get_transactions(transaction_type="income")
        assert len(income) == 1
        assert income[0].amount > 0

    def test_filter_by_date(self, db):
        agent = DataIngestionAgent(db)
        agent.add_transaction(
            TransactionInput(
                date=date(2025, 1, 1),
                description="A",
                amount=-10.00,
            )
        )
        agent.add_transaction(
            TransactionInput(
                date=date(2025, 2, 1),
                description="B",
                amount=-20.00,
            )
        )
        txns = agent.get_transactions(start_date=date(2025, 1, 15))
        assert len(txns) == 1

    def test_delete_transaction(self, db):
        agent = DataIngestionAgent(db)
        txn = agent.add_transaction(
            TransactionInput(
                date=date(2025, 1, 1),
                description="Test",
                amount=-10.00,
            )
        )
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


class TestImportCsvErrorText:
    """import_csv reports what failed, never the underlying library text."""

    def test_unreadable_csv_message_is_fixed(self, db, monkeypatch, caplog):
        def failing_read_csv(*args, **kwargs):
            raise RuntimeError("secret-internal-marker offset 4711")

        monkeypatch.setattr("agents.data_ingestion.pd.read_csv", failing_read_csv)
        with caplog.at_level("ERROR"):
            result = DataIngestionAgent(db).import_csv("date,description,amount\n")

        assert result.errors == ["Failed to parse CSV: the file could not be read as CSV"]
        assert result.total_rows == 0
        assert "secret-internal-marker offset 4711" in caplog.text

    def test_row_errors_name_the_row_and_the_problem(self, db, caplog):
        csv = (
            "date,description,amount\n"
            "bad,A,1\n"
            "2025-01-02,B,abc\n"
            '2025-01-03,"  ",5\n'
            "2025-01-04,D,0\n"
            "2025-01-05,E,10\n"
        )
        with caplog.at_level("WARNING"):
            result = DataIngestionAgent(db).import_csv(csv)

        assert result.imported == 1
        assert result.skipped == 4
        assert result.errors == [
            "Row 1: invalid date",
            "Row 2: invalid amount",
            "Row 3: description: Description must not be empty",
            "Row 4: amount: Amount must not be zero",
        ]
        # The original exception is still available to operators.
        assert "Unknown datetime" in caplog.text
        assert "could not convert string to float" in caplog.text

    def test_row_save_failure_is_logged_not_returned(self, db, monkeypatch, caplog):
        def failing_add(self_, txn_input):
            raise RuntimeError("INSERT INTO transactions ... secret-internal-marker")

        monkeypatch.setattr(DataIngestionAgent, "add_transaction", failing_add)
        with caplog.at_level("ERROR"):
            result = DataIngestionAgent(db).import_csv("date,description,amount\n2025-01-01,A,1\n")

        assert result.errors == ["Row 1: could not be saved"]
        assert "secret-internal-marker" in caplog.text


class TestFailedSaveDoesNotPoisonTheSession:
    """One row the database refuses must not make every later row fail.

    SQLite stores NaN as NULL, so a NaN amount trips the NOT NULL constraint on
    transactions.amount at commit time. That is a real failed flush, not a mock.
    pydantic accepts NaN for a float field, so the row passes validation first.
    """

    @staticmethod
    def _nan_input():
        return TransactionInput(date=date(2025, 1, 2), description="NaN row", amount=float("nan"))

    def test_add_transaction_rolls_back_and_reraises(self, db):
        from sqlalchemy.exc import IntegrityError

        agent = DataIngestionAgent(db)
        with pytest.raises(IntegrityError):
            agent.add_transaction(self._nan_input())

        # The session is usable again, and the next transaction is saved.
        txn = agent.add_transaction(
            TransactionInput(date=date(2025, 1, 3), description="After", amount=-5)
        )
        assert txn.id is not None
        assert len(agent.get_transactions()) == 1

    def test_import_csv_keeps_importing_after_a_failed_row(self, db, caplog):
        csv = (
            "date,description,amount\n"
            "2025-01-01,First,-1\n"
            "2025-01-02,Broken,nan\n"
            "2025-01-03,Third,-3\n"
            "2025-01-04,Fourth,-4\n"
        )
        with caplog.at_level("ERROR"):
            result = DataIngestionAgent(db).import_csv(csv)

        assert result.total_rows == 4
        assert result.imported == 3
        assert result.skipped == 1
        # Only the refused row is reported, with the unchanged fixed message.
        assert result.errors == ["Row 2: could not be saved"]
        assert "PendingRollbackError" not in caplog.text
        assert db.query(Transaction).count() == 3
