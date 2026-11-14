"""Tests for FastAPI endpoints."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.main import app
from db.database import Base, get_db


@pytest.fixture
def engine():
    """An in-memory database shared by every connection of one test."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return engine


@pytest.fixture
def client(engine):
    """Create a test client with an in-memory database."""
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


class TestStatementImportErrorHandling:
    """The statement upload must not leak parser/library exception text."""

    SECRET = "secret-internal-marker /srv/app/lib/parser.py offset 4711 IBAN DE00123456789"

    @staticmethod
    def _upload(client, name, content=b"irrelevant"):
        return client.post(
            "/api/transactions/import-statement",
            files={"file": (name, content, "application/octet-stream")},
        )

    def test_mt940_library_error_is_not_exposed(self, client, monkeypatch, caplog):
        def failing_parse(*args, **kwargs):
            raise ValueError(self.SECRET)

        monkeypatch.setattr("agents.bank_statement_parser.mt940.parse", failing_parse)

        with caplog.at_level("ERROR"):
            resp = self._upload(client, "bad.mt940")

        # Status code unchanged, client sees a fixed message naming the format ...
        assert resp.status_code == 400
        assert resp.json()["detail"].startswith("Failed to parse MT940 file")
        # ... without the library text ...
        assert "secret-internal-marker" not in resp.text
        assert "4711" not in resp.text
        # ... which is logged server-side instead.
        assert self.SECRET in caplog.text

    def test_ofx_library_error_is_not_exposed(self, client, monkeypatch, caplog):
        def failing_parse(*args, **kwargs):
            raise ValueError(self.SECRET)

        monkeypatch.setattr("agents.bank_statement_parser.ofxparse.OfxParser.parse", failing_parse)

        with caplog.at_level("ERROR"):
            resp = self._upload(client, "bad.ofx")

        assert resp.status_code == 400
        assert resp.json()["detail"].startswith("Failed to parse OFX file")
        assert "secret-internal-marker" not in resp.text
        assert "4711" not in resp.text
        assert self.SECRET in caplog.text

    def test_genuinely_malformed_ofx_gets_fixed_message(self, client):
        resp = self._upload(client, "garbage.ofx", b"not valid ofx data")
        assert resp.status_code == 400
        assert resp.json()["detail"].startswith("Failed to parse OFX file")

    def test_unsupported_format_message_is_unchanged(self, client):
        resp = self._upload(client, "report.pdf")
        assert resp.status_code == 400
        assert resp.json()["detail"] == "Unsupported format. Supported: .mt940, .ofx, .qfx, .sta"

    def test_per_transaction_failure_is_not_exposed(self, client, monkeypatch, caplog):
        def failing_add(self_, txn_input):
            raise RuntimeError(self.SECRET)

        monkeypatch.setattr("agents.data_ingestion.DataIngestionAgent.add_transaction", failing_add)
        ofx = (
            b"OFXHEADER:100\nDATA:OFXSGML\nVERSION:102\nSECURITY:NONE\nENCODING:USASCII\n"
            b"CHARSET:1252\nCOMPRESSION:NONE\nOLDFILEUID:NONE\nNEWFILEUID:NONE\n\n"
            b"<OFX><BANKMSGSRSV1><STMTTRNRS><STMTRS><CURDEF>EUR"
            b"<BANKACCTFROM><BANKID>1<ACCTID>1<ACCTTYPE>CHECKING</BANKACCTFROM>"
            b"<BANKTRANLIST><STMTTRN><TRNTYPE>DEBIT<DTPOSTED>20250115"
            b"<TRNAMT>-10.00<FITID>1<NAME>REWE</STMTTRN></BANKTRANLIST>"
            b"</STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>"
        )

        with caplog.at_level("ERROR"):
            resp = self._upload(client, "ok.ofx", ofx)

        assert resp.status_code == 200
        body = resp.json()
        assert body["total_rows"] == 1
        assert body["imported"] == 0
        assert len(body["errors"]) == 1
        assert body["errors"][0].startswith("Transaction 1:")
        assert "secret-internal-marker" not in resp.text
        assert self.SECRET in caplog.text


class TestCsvImportErrorHandling:
    """The CSV import must not leak pandas/pydantic/SQLAlchemy exception text."""

    SECRET = "secret-internal-marker /srv/app/lib/parser.py offset 4711 IBAN DE00123456789"
    HEADER = "date,description,amount\n"
    # What the endpoint answered before the fix would contain at least one of these.
    LIBRARY_TEXT = (
        "No columns to parse",
        "could not convert string to float",
        "Unknown datetime",
        "validation error for",
        "errors.pydantic.dev",
        "input_value",
    )

    @staticmethod
    def _upload(client, content, name="transactions.csv"):
        return client.post(
            "/api/transactions/import",
            files={"file": (name, content, "text/csv")},
        )

    def _assert_no_library_text(self, resp):
        assert "secret-internal-marker" not in resp.text
        assert "4711" not in resp.text
        for fragment in self.LIBRARY_TEXT:
            assert fragment not in resp.text

    def test_csv_parser_error_is_not_exposed(self, client, monkeypatch, caplog):
        def failing_read_csv(*args, **kwargs):
            raise ValueError(self.SECRET)

        monkeypatch.setattr("agents.data_ingestion.pd.read_csv", failing_read_csv)

        with caplog.at_level("ERROR"):
            resp = self._upload(client, self.HEADER + "2025-01-01,Gehalt,3000\n")

        # Status code and response shape are unchanged ...
        assert resp.status_code == 200
        assert resp.json() == {
            "total_rows": 0,
            "imported": 0,
            "skipped": 0,
            "errors": ["Failed to parse CSV: the file could not be read as CSV"],
        }
        # ... without the library text ...
        self._assert_no_library_text(resp)
        # ... which is logged server-side instead.
        assert self.SECRET in caplog.text

    def test_genuinely_unreadable_csv_gets_fixed_message(self, client):
        resp = self._upload(client, b"")
        assert resp.status_code == 200
        assert resp.json()["errors"] == ["Failed to parse CSV: the file could not be read as CSV"]
        self._assert_no_library_text(resp)

    def test_missing_columns_message_is_unchanged(self, client):
        resp = self._upload(client, "date,amount\n2025-01-01,100\n")
        assert resp.status_code == 200
        assert resp.json()["errors"] == ["Missing columns: description"]
        assert resp.json()["imported"] == 0

    def test_row_save_failure_is_not_exposed(self, client, monkeypatch, caplog):
        def failing_add(self_, txn_input):
            raise RuntimeError(self.SECRET)

        monkeypatch.setattr("agents.data_ingestion.DataIngestionAgent.add_transaction", failing_add)

        with caplog.at_level("ERROR"):
            resp = self._upload(client, self.HEADER + "2025-01-01,Gehalt,3000\n")

        assert resp.status_code == 200
        body = resp.json()
        assert body["total_rows"] == 1
        assert body["imported"] == 0
        assert body["skipped"] == 1
        assert body["errors"] == ["Row 1: could not be saved"]
        self._assert_no_library_text(resp)
        assert self.SECRET in caplog.text

    def test_invalid_date_and_amount_are_reported_without_library_text(self, client):
        content = self.HEADER + "not-a-date,Gehalt,3000\n2025-01-02,Miete,abc\n2025-01-03,REWE,-5\n"
        resp = self._upload(client, content)

        assert resp.status_code == 200
        body = resp.json()
        assert body["total_rows"] == 3
        assert body["imported"] == 1
        assert body["skipped"] == 2
        assert body["errors"] == ["Row 1: invalid date", "Row 2: invalid amount"]
        self._assert_no_library_text(resp)

    def test_validation_messages_still_reach_the_client(self, client):
        content = self.HEADER + '2025-01-01,"  ",5\n2025-01-02,Gehalt,0\n'
        resp = self._upload(client, content)

        assert resp.status_code == 200
        body = resp.json()
        assert body["imported"] == 0
        assert body["skipped"] == 2
        # The project's own rules are named by field and constraint ...
        assert body["errors"] == [
            "Row 1: description: Description must not be empty",
            "Row 2: amount: Amount must not be zero",
        ]
        # ... without pydantic's wrapper (model name, input value, docs URL).
        self._assert_no_library_text(resp)

    def test_valid_csv_still_imports(self, client):
        resp = self._upload(client, self.HEADER + "2025-01-01,Gehalt,3000\n2025-01-05,Miete,-850\n")
        assert resp.status_code == 200
        assert resp.json() == {"total_rows": 2, "imported": 2, "skipped": 0, "errors": []}


class TestNonFiniteAmounts:
    """NaN and infinity must be answered with 422, never stored or a 500.

    json.loads (which FastAPI uses) accepts the non-standard literals NaN,
    Infinity and -Infinity, so a client can send them even though they are not
    valid JSON. httpx refuses to encode them, hence the raw request bodies.
    """

    LITERALS = ["NaN", "Infinity", "-Infinity"]

    @staticmethod
    def _post(client, path, body):
        return client.post(path, content=body, headers={"content-type": "application/json"})

    @staticmethod
    def _detail_messages(resp):
        return [item["msg"] for item in resp.json()["detail"]]

    @pytest.mark.parametrize("literal", LITERALS)
    def test_transaction_amount_is_rejected(self, client, literal):
        resp = self._post(
            client,
            "/api/transactions/",
            f'{{"date": "2025-01-15", "description": "Test", "amount": {literal}}}',
        )
        assert resp.status_code == 422
        assert self._detail_messages(resp) == ["Value error, Amount must be a finite number"]
        assert client.get("/api/transactions/").json() == []

    def test_other_validation_errors_still_echo_the_input(self, client):
        # Only a non-finite input is left out of the 422 body.
        resp = self._post(
            client,
            "/api/transactions/",
            '{"date": "2025-01-15", "description": "Test", "amount": "abc"}',
        )
        assert resp.status_code == 422
        assert resp.json()["detail"][0]["input"] == "abc"

    def test_transaction_amount_beyond_float_range_is_rejected(self, client):
        # 1e999 is valid JSON, but Python reads it as infinity.
        resp = self._post(
            client,
            "/api/transactions/",
            '{"date": "2025-01-15", "description": "Test", "amount": 1e999}',
        )
        assert resp.status_code == 422
        assert client.get("/api/transactions/").json() == []

    @pytest.mark.parametrize("literal", LITERALS)
    def test_budget_limit_is_rejected(self, client, literal):
        resp = self._post(
            client, "/api/budgets/", f'{{"category": "Lebensmittel", "monthly_limit": {literal}}}'
        )
        assert resp.status_code == 422
        assert self._detail_messages(resp) == ["Value error, Monthly limit must be a finite number"]
        assert client.get("/api/budgets/").json() == []

    def test_csv_import_reports_non_finite_rows(self, client):
        content = (
            "date,description,amount\n"
            "2025-01-01,First,-1\n"
            "2025-01-02,Not a number,nan\n"
            "2025-01-03,Plus infinity,inf\n"
            "2025-01-04,Last,-4\n"
        )
        resp = client.post(
            "/api/transactions/import",
            files={"file": ("t.csv", content.encode(), "text/csv")},
        )
        assert resp.status_code == 200
        assert resp.json() == {
            "total_rows": 4,
            "imported": 2,
            "skipped": 2,
            "errors": [
                "Row 2: amount: Amount must be a finite number",
                "Row 3: amount: Amount must be a finite number",
            ],
        }
        assert len(client.get("/api/transactions/").json()) == 2

    @pytest.mark.parametrize("literal", ["NaN", "Infinity", "1e999"])
    def test_statement_with_a_non_finite_amount_is_refused(self, client, literal):
        # ofxparse reads these amounts without complaint. The statement is
        # refused as a whole, with the fixed parse message and nothing stored.
        content = (
            b"OFXHEADER:100\nDATA:OFXSGML\nVERSION:102\nSECURITY:NONE\nENCODING:USASCII\n"
            b"CHARSET:1252\nCOMPRESSION:NONE\nOLDFILEUID:NONE\nNEWFILEUID:NONE\n\n"
            b"<OFX><BANKMSGSRSV1><STMTTRNRS><STMTRS><CURDEF>EUR"
            b"<BANKACCTFROM><BANKID>1<ACCTID>1<ACCTTYPE>CHECKING</BANKACCTFROM>"
            b"<BANKTRANLIST><STMTTRN><TRNTYPE>DEBIT<DTPOSTED>20250115"
            b"<TRNAMT>" + literal.encode() + b"<FITID>1<NAME>REWE</STMTTRN></BANKTRANLIST>"
            b"</STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>"
        )
        resp = client.post(
            "/api/transactions/import-statement",
            files={"file": ("s.ofx", content, "application/octet-stream")},
        )
        assert resp.status_code == 400
        assert resp.json()["detail"].startswith("Failed to parse OFX file")
        assert client.get("/api/transactions/").json() == []


class TestFailedSaveDoesNotPoisonTheRequest:
    """A row the database refuses must not make the rest of the upload fail.

    A SQLite trigger aborts the insert of the row described as "Broken", so the
    commit fails inside the database engine (a real IntegrityError, not a mock)
    while the row passes validation first. Every other row is accepted.
    """

    @staticmethod
    def _inputs():
        from datetime import date

        from agents.data_ingestion import TransactionInput

        return [
            TransactionInput(date=date(2025, 1, 1), description="First", amount=-1),
            TransactionInput(date=date(2025, 1, 2), description="Broken", amount=-2),
            TransactionInput(date=date(2025, 1, 3), description="Third", amount=-3),
            TransactionInput(date=date(2025, 1, 4), description="Fourth", amount=-4),
        ]

    def test_statement_import_continues_after_a_failed_transaction(
        self, client, engine, refuse_rows_described_as, monkeypatch, caplog
    ):
        refuse_rows_described_as(engine, "Broken")
        monkeypatch.setattr(
            "agents.bank_statement_parser.BankStatementParser.parse",
            lambda self_, content, filename: self._inputs(),
        )
        with caplog.at_level("ERROR"):
            resp = client.post(
                "/api/transactions/import-statement",
                files={"file": ("s.ofx", b"x", "application/octet-stream")},
            )

        assert resp.status_code == 200
        assert resp.json() == {
            "total_rows": 4,
            "imported": 3,
            "skipped": 1,
            "errors": ["Transaction 2: could not be saved"],
        }
        assert "PendingRollbackError" not in caplog.text
        assert len(client.get("/api/transactions/").json()) == 3

    def test_csv_import_continues_after_a_failed_row(
        self, client, engine, refuse_rows_described_as, caplog
    ):
        refuse_rows_described_as(engine, "Broken")
        content = (
            "date,description,amount\n"
            "2025-01-01,First,-1\n"
            "2025-01-02,Broken,-2\n"
            "2025-01-03,Third,-3\n"
            "2025-01-04,Fourth,-4\n"
        )
        with caplog.at_level("ERROR"):
            resp = client.post(
                "/api/transactions/import",
                files={"file": ("t.csv", content.encode(), "text/csv")},
            )

        assert resp.status_code == 200
        assert resp.json() == {
            "total_rows": 4,
            "imported": 3,
            "skipped": 1,
            "errors": ["Row 2: could not be saved"],
        }
        assert "PendingRollbackError" not in caplog.text
