"""Tests for FastAPI endpoints."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.main import app
from db.database import Base, get_db


@pytest.fixture
def client():
    """Create a test client with an in-memory database."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestSession = sessionmaker(bind=engine)

    def override_get_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


class TestAPI:
    def test_root(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert resp.json()["status"] == "running"

    def test_create_transaction(self, client):
        resp = client.post(
            "/api/transactions/",
            json={
                "date": "2025-01-15",
                "description": "REWE Einkauf",
                "amount": -50.00,
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["description"] == "REWE Einkauf"
        assert data["transaction_type"] == "expense"

    def test_create_income(self, client):
        resp = client.post(
            "/api/transactions/",
            json={
                "date": "2025-01-01",
                "description": "Gehalt",
                "amount": 3000.00,
            },
        )
        assert resp.status_code == 201
        assert resp.json()["transaction_type"] == "income"

    def test_list_transactions(self, client):
        client.post(
            "/api/transactions/",
            json={
                "date": "2025-01-01",
                "description": "A",
                "amount": -10.00,
            },
        )
        client.post(
            "/api/transactions/",
            json={
                "date": "2025-01-02",
                "description": "B",
                "amount": -20.00,
            },
        )
        resp = client.get("/api/transactions/")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_get_single_transaction(self, client):
        create = client.post(
            "/api/transactions/",
            json={
                "date": "2025-01-01",
                "description": "Test",
                "amount": -10.00,
            },
        )
        txn_id = create.json()["id"]
        resp = client.get(f"/api/transactions/{txn_id}")
        assert resp.status_code == 200
        assert resp.json()["description"] == "Test"

    def test_get_nonexistent_transaction(self, client):
        resp = client.get("/api/transactions/999")
        assert resp.status_code == 404

    def test_delete_transaction(self, client):
        create = client.post(
            "/api/transactions/",
            json={
                "date": "2025-01-01",
                "description": "Test",
                "amount": -10.00,
            },
        )
        txn_id = create.json()["id"]
        resp = client.delete(f"/api/transactions/{txn_id}")
        assert resp.status_code == 200

    def test_delete_nonexistent(self, client):
        resp = client.delete("/api/transactions/999")
        assert resp.status_code == 404

    def test_filter_by_type(self, client):
        client.post(
            "/api/transactions/",
            json={
                "date": "2025-01-01",
                "description": "Gehalt",
                "amount": 3000.00,
            },
        )
        client.post(
            "/api/transactions/",
            json={
                "date": "2025-01-05",
                "description": "Miete",
                "amount": -850.00,
            },
        )
        resp = client.get("/api/transactions/?transaction_type=income")
        assert len(resp.json()) == 1

    def test_analytics_summary(self, client):
        client.post(
            "/api/transactions/",
            json={
                "date": "2025-01-01",
                "description": "Gehalt",
                "amount": 3000.00,
            },
        )
        resp = client.get("/api/analytics/summary")
        assert resp.status_code == 200
        assert resp.json()["total_income"] == 3000.00

    def test_analytics_categories(self, client):
        client.post(
            "/api/transactions/",
            json={
                "date": "2025-01-01",
                "description": "REWE",
                "amount": -50.00,
            },
        )
        resp = client.get("/api/analytics/categories")
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_analytics_trends(self, client):
        client.post(
            "/api/transactions/",
            json={
                "date": "2025-01-01",
                "description": "Gehalt",
                "amount": 3000.00,
            },
        )
        resp = client.get("/api/analytics/trends")
        assert resp.status_code == 200

    def test_set_budget(self, client):
        resp = client.post(
            "/api/budgets/",
            json={
                "category": "Lebensmittel",
                "monthly_limit": 200.00,
            },
        )
        assert resp.status_code == 201
        assert resp.json()["monthly_limit"] == 200.00

    def test_list_budgets(self, client):
        client.post(
            "/api/budgets/",
            json={
                "category": "Lebensmittel",
                "monthly_limit": 200.00,
            },
        )
        resp = client.get("/api/budgets/")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_delete_budget(self, client):
        client.post(
            "/api/budgets/",
            json={
                "category": "Lebensmittel",
                "monthly_limit": 200.00,
            },
        )
        resp = client.delete("/api/budgets/Lebensmittel")
        assert resp.status_code == 200

    def test_budget_status(self, client):
        client.post(
            "/api/budgets/",
            json={
                "category": "Lebensmittel",
                "monthly_limit": 200.00,
            },
        )
        resp = client.get("/api/budgets/status?year=2025&month=1")
        assert resp.status_code == 200
        assert "budgets" in resp.json()

    def test_validation_empty_description(self, client):
        resp = client.post(
            "/api/transactions/",
            json={
                "date": "2025-01-01",
                "description": "  ",
                "amount": -10.00,
            },
        )
        assert resp.status_code == 422

    def test_validation_zero_amount(self, client):
        resp = client.post(
            "/api/transactions/",
            json={
                "date": "2025-01-01",
                "description": "Test",
                "amount": 0,
            },
        )
        assert resp.status_code == 422


class TestBudgetAlertsErrorHandling:
    """The alert endpoint must not leak SMTP exception details to the client."""

    SECRET = "smtp.internal.corp:587 login failed for svc-alerts (password hunter2)"

    def test_smtp_failure_is_not_exposed(self, client, monkeypatch, caplog):
        monkeypatch.setenv("SMTP_HOST", "smtp.internal.corp")
        monkeypatch.setenv("SMTP_USER", "svc-alerts")
        monkeypatch.setenv("SMTP_PASSWORD", "hunter2")
        monkeypatch.setenv("ALERT_RECIPIENT", "admin@example.com")

        def failing_smtp(*args, **kwargs):
            raise OSError(self.SECRET)

        monkeypatch.setattr("agents.alert_service.smtplib.SMTP", failing_smtp)

        client.post(
            "/api/transactions/",
            json={
                "date": "2025-01-15",
                "description": "REWE",
                "amount": -150.0,
                "category": "Lebensmittel",
            },
        )
        client.post("/api/budgets/", json={"category": "Lebensmittel", "monthly_limit": 100.0})

        with caplog.at_level("ERROR"):
            resp = client.post("/api/budgets/alerts?year=2025&month=1&dry_run=false")

        # Status code and result shape are unchanged ...
        assert resp.status_code == 200
        body = resp.json()
        assert body["alerts_triggered"] == 1
        assert body["email_sent"] is False
        # ... the client gets a generic message, not the exception text ...
        assert body["error"] == "Failed to send alert email"
        assert "hunter2" not in resp.text
        assert "smtp.internal.corp" not in resp.text
        # ... and the detail is logged server-side.
        assert self.SECRET in caplog.text
