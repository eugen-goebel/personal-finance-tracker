"""Tests for AlertService — budget email alerts."""

from datetime import date

from agents.alert_service import AlertService, AlertConfig, AlertResult
from agents.budget import BudgetAgent
from agents.data_ingestion import DataIngestionAgent, TransactionInput


def _setup_budgets_and_expenses(db):
    """Create budgets and expenses for January 2025."""
    ingestion = DataIngestionAgent(db)
    expenses = [
        (date(2025, 1, 3), "REWE", -65.00, "Lebensmittel"),
        (date(2025, 1, 10), "Edeka", -45.00, "Lebensmittel"),
        (date(2025, 1, 5), "Miete", -850.00, "Miete & Wohnen"),
        (date(2025, 1, 12), "Netflix", -12.99, "Unterhaltung"),
    ]
    for d, desc, amt, cat in expenses:
        ingestion.add_transaction(TransactionInput(
            date=d, description=desc, amount=amt, category=cat,
        ))

    agent = BudgetAgent(db)
    agent.set_budget("Lebensmittel", 100.00)  # exceeded: 110/100
    agent.set_budget("Miete & Wohnen", 900.00)  # warning: 850/900 = 94%
    agent.set_budget("Unterhaltung", 50.00)  # ok: 12.99/50


class TestAlertService:
    def test_check_triggers_alerts(self, db):
        _setup_budgets_and_expenses(db)
        service = AlertService(db)
        result = service.check_and_alert(2025, 1, dry_run=True)
        assert isinstance(result, AlertResult)
        assert result.alerts_triggered == 2  # Lebensmittel exceeded, Miete warning

    def test_no_alerts_when_under_budget(self, db):
        BudgetAgent(db).set_budget("Shopping", 500.00)
        service = AlertService(db)
        result = service.check_and_alert(2025, 1, dry_run=True)
        assert result.alerts_triggered == 0
        assert result.warnings == []

    def test_dry_run_does_not_send_email(self, db):
        _setup_budgets_and_expenses(db)
        service = AlertService(db)
        result = service.check_and_alert(2025, 1, dry_run=True)
        assert result.email_sent is False

    def test_no_email_without_config(self, db):
        _setup_budgets_and_expenses(db)
        config = AlertConfig()  # empty config
        service = AlertService(db, config=config)
        result = service.check_and_alert(2025, 1, dry_run=False)
        # No email sent because config is not complete
        assert result.email_sent is False

    def test_warnings_contain_category_names(self, db):
        _setup_budgets_and_expenses(db)
        service = AlertService(db)
        result = service.check_and_alert(2025, 1, dry_run=True)
        warning_text = " ".join(result.warnings)
        assert "Lebensmittel" in warning_text
        assert "Miete" in warning_text

    def test_defaults_to_current_month(self, db):
        BudgetAgent(db).set_budget("Test", 100.00)
        service = AlertService(db)
        result = service.check_and_alert(dry_run=True)
        today = date.today()
        assert result.year == today.year
        assert result.month == today.month

    def test_email_body_format(self, db):
        _setup_budgets_and_expenses(db)
        service = AlertService(db)
        overview = BudgetAgent(db).get_status(2025, 1)
        body = service.build_email_body(overview)
        assert "Budget-Warnung" in body
        assert "Januar 2025" in body
        assert "Lebensmittel" in body
        assert "EUR" in body

    def test_email_body_contains_all_categories(self, db):
        _setup_budgets_and_expenses(db)
        service = AlertService(db)
        overview = BudgetAgent(db).get_status(2025, 1)
        body = service.build_email_body(overview)
        assert "[X]" in body  # exceeded
        assert "[!]" in body  # warning
        assert "[OK]" in body  # ok


class TestAlertConfig:
    def test_empty_config_not_configured(self):
        config = AlertConfig()
        assert config.is_configured is False

    def test_full_config_is_configured(self):
        config = AlertConfig(
            smtp_host="smtp.example.com",
            smtp_user="user@example.com",
            smtp_password="secret",
            recipient="admin@example.com",
        )
        assert config.is_configured is True

    def test_partial_config_not_configured(self):
        config = AlertConfig(smtp_host="smtp.example.com")
        assert config.is_configured is False
