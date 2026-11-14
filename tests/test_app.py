"""Tests for the Streamlit dashboard layer (app.py).

Covers the two things a visitor sees before anything else: money figures
carry their currency, and the budget panel reports a month that actually
holds transactions.
"""

import sys
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

REPO_DIR = Path(__file__).resolve().parent.parent
APP_PATH = str(REPO_DIR / "app.py")
SAMPLE_CSV = REPO_DIR / "data" / "sample_transactions.csv"


@pytest.fixture()
def app(tmp_path, monkeypatch):
    """Run the dashboard against a throwaway database seeded with the sample CSV.

    The real finance.db is never touched: DATABASE_URL points at tmp_path.
    """
    db_file = tmp_path / "test_finance.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_file}")

    # Seed the same sample data the "Import Data" page loads.
    sys.path.insert(0, str(REPO_DIR))
    from sqlalchemy.orm import sessionmaker

    from agents.budget import BudgetAgent
    from agents.data_ingestion import DataIngestionAgent
    from db.database import Base, get_engine

    engine = get_engine(f"sqlite:///{db_file}")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    try:
        DataIngestionAgent(session).import_csv(SAMPLE_CSV.read_text())
        # A budget on a category that actually has expenses in the sample data.
        BudgetAgent(session).set_budget("Lebensmittel", 300.0)
    finally:
        session.close()

    return AppTest.from_file(APP_PATH, default_timeout=120).run()


class TestMoneyFormatting:
    """Amounts must be distinguishable from counts.

    Regression: the dashboard rendered "10,550.00" next to "5,456.55" with
    no unit, while the savings goals page already used a euro sign. Same
    app, two conventions.
    """

    def test_money_helper_attaches_the_symbol(self):
        sys.path.insert(0, str(REPO_DIR))
        import app

        assert app.money(10550.0) == "10,550.00 €"
        assert app.money(-67.43, signed=True) == "-67.43 €"
        assert app.money(450.0, signed=True) == "+450.00 €"

    def test_dashboard_amounts_carry_a_currency(self, app):
        assert not app.exception

        by_label = {m.label: str(m.value) for m in app.metric}
        for label in ("Total Income", "Total Expenses", "Net Balance"):
            assert by_label[label].endswith("€"), f"{label} has no currency: {by_label[label]}"

        # A rate is not an amount and must stay a percentage.
        assert by_label["Savings Rate"].endswith("%")


class TestBudgetMonth:
    """The budget panel must report a month that holds transactions.

    Regression: it asked for date.today(), but the sample data ends in
    March 2025, so every budget showed 0.00 spent. That reads like broken
    tracking rather than an empty month.
    """

    def test_budget_status_uses_the_latest_month_with_data(self, app):
        assert not app.exception

        captions = [c.value for c in app.caption]
        assert any("2025-03" in c for c in captions), (
            f"budget panel does not name the month it reports on: {captions}"
        )

    def test_budget_shows_real_spending_not_zero(self, app):
        # Lebensmittel has expenses in March 2025. The old code asked for
        # date.today(), found nothing, and reported 0.00 spent.
        #
        # Asserting on the rendered string would be worthless here: the old
        # version formats without a currency, so any check written against the
        # new format passes vacuously. Read the number back instead.
        import re

        written = " ".join(str(m.value) for m in app.markdown)
        match = re.search(r"\*\*Lebensmittel\*\*:\s*([\d,.]+)", written)
        assert match, f"no Lebensmittel budget line rendered: {written[:300]}"

        spent = float(match.group(1).replace(",", ""))
        assert spent > 0, "budget reports zero spending for a category that has expenses"


class TestBudgetCategories:
    """A budget caps spending, so it must not be offered on income.

    Regression: the category picker listed every known category including
    "Gehalt", and a budget set there could only ever read 0.00 spent.
    """

    def test_income_categories_are_not_offered_for_budgets(self):
        sys.path.insert(0, str(REPO_DIR))
        from agents.categorizer import INCOME_CATEGORIES, CategorizerAgent

        offered = CategorizerAgent().expense_categories
        for income in INCOME_CATEGORIES:
            assert income not in offered, f"budget offered on income category: {income}"

    def test_expense_categories_still_cover_real_spending(self):
        sys.path.insert(0, str(REPO_DIR))
        from agents.categorizer import CategorizerAgent

        offered = CategorizerAgent().expense_categories
        # Categories the sample data actually spends money on.
        for category in ("Lebensmittel", "Miete & Wohnen", "Transport"):
            assert category in offered

    def test_existing_income_budget_is_explained(self, tmp_path, monkeypatch):
        # A budget stored by an older build must not silently show 0.00 with
        # no reason given. It stays (deleting user data would be worse) but
        # the dashboard has to say why it reads zero.
        db_file = tmp_path / "income_budget.db"
        monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_file}")
        sys.path.insert(0, str(REPO_DIR))
        from sqlalchemy.orm import sessionmaker

        from agents.budget import BudgetAgent
        from agents.data_ingestion import DataIngestionAgent
        from db.database import Base, get_engine

        engine = get_engine(f"sqlite:///{db_file}")
        Base.metadata.create_all(bind=engine)
        session = sessionmaker(bind=engine)()
        try:
            DataIngestionAgent(session).import_csv(SAMPLE_CSV.read_text())
            BudgetAgent(session).set_budget("Gehalt", 200.0)
        finally:
            session.close()

        at = AppTest.from_file(APP_PATH, default_timeout=120).run()
        assert not at.exception
        captions = " ".join(c.value for c in at.caption)
        assert "income category" in captions


class TestStatementUploadErrors:
    """The dashboard must not show parser/library exception text to the user."""

    SECRET = "secret-internal-marker /srv/app/lib/parser.py offset 4711"

    @staticmethod
    def _open_import_page(app):
        app.sidebar.radio[0].set_value("Import Data").run()
        # Two uploaders on this page: CSV first, bank statement second.
        return app.file_uploader[1]

    @staticmethod
    def _error_text(app):
        return " ".join(e.value for e in app.error)

    @pytest.mark.parametrize(
        ("filename", "target", "fmt"),
        [
            ("bad.mt940", "agents.bank_statement_parser.mt940.parse", "MT940"),
            ("bad.ofx", "agents.bank_statement_parser.ofxparse.OfxParser.parse", "OFX"),
        ],
    )
    def test_parser_error_is_not_shown(self, app, monkeypatch, caplog, filename, target, fmt):
        def failing_parse(*args, **kwargs):
            raise ValueError(self.SECRET)

        monkeypatch.setattr(target, failing_parse)
        uploader = self._open_import_page(app)
        uploader.set_value((filename, b"irrelevant", "application/octet-stream"))

        with caplog.at_level("ERROR"):
            app.run()

        assert not app.exception
        shown = self._error_text(app)
        assert f"Failed to parse {fmt} file" in shown
        assert "secret-internal-marker" not in shown
        assert "4711" not in shown
        assert self.SECRET in caplog.text


class TestCsvUploadErrors:
    """The dashboard must not show pandas/library exception text for CSV uploads."""

    SECRET = "secret-internal-marker /srv/app/lib/parser.py offset 4711"
    UNREADABLE = "Failed to parse CSV: the file could not be read as CSV"

    @staticmethod
    def _open_import_page(app):
        app.sidebar.radio[0].set_value("Import Data").run()
        # Two uploaders on this page: CSV first, bank statement second.
        return app.file_uploader[0]

    @staticmethod
    def _error_text(app):
        return " ".join(e.value for e in app.error)

    @staticmethod
    def _click_import(app):
        next(b for b in app.button if b.label == "Import").click().run()

    def test_csv_parser_error_is_not_shown(self, app, monkeypatch, caplog):
        def failing_read_csv(*args, **kwargs):
            raise ValueError(self.SECRET)

        monkeypatch.setattr("pandas.read_csv", failing_read_csv)
        uploader = self._open_import_page(app)
        uploader.set_value(("bad.csv", b"date,description,amount\n", "text/csv"))

        with caplog.at_level("ERROR"):
            app.run()
            # The preview must not crash the page ...
            assert not app.exception
            self._click_import(app)

        # ... and neither the preview nor the import shows the library text.
        assert not app.exception
        shown = self._error_text(app)
        assert self.UNREADABLE in shown
        assert "secret-internal-marker" not in shown
        assert "4711" not in shown
        assert self.SECRET in caplog.text

    def test_unreadable_csv_shows_fixed_message(self, app):
        uploader = self._open_import_page(app)
        uploader.set_value(("empty.csv", b"", "text/csv"))
        app.run()
        assert not app.exception
        self._click_import(app)
        assert not app.exception
        shown = self._error_text(app)
        assert self.UNREADABLE in shown
        assert "No columns to parse" not in shown

    def test_non_utf8_csv_does_not_crash_the_page(self, app, caplog):
        uploader = self._open_import_page(app)
        uploader.set_value(
            ("latin1.csv", b"date,description,amount\n2025-01-01,Caf\xe9,5\n", "text/csv")
        )

        with caplog.at_level("ERROR"):
            app.run()

        assert not app.exception
        shown = self._error_text(app)
        assert "Failed to read CSV: the file is not valid UTF-8 text" in shown
        assert "codec" not in shown
        assert "0xe9" not in shown

    def test_row_errors_are_shown_without_library_text(self, app):
        uploader = self._open_import_page(app)
        content = b"date,description,amount\nnot-a-date,A,5\n2025-01-02,B,abc\n2025-01-03,C,0\n"
        uploader.set_value(("rows.csv", content, "text/csv"))
        app.run()
        self._click_import(app)

        assert not app.exception
        shown = self._error_text(app)
        assert "Row 1: invalid date" in shown
        assert "Row 2: invalid amount" in shown
        # The project's own validation rule is named by field and constraint.
        assert "Row 3: amount: Amount must not be zero" in shown
        for fragment in (
            "Unknown datetime",
            "could not convert",
            "validation error for",
            "pydantic",
        ):
            assert fragment not in shown

    def test_missing_columns_message_is_unchanged(self, app):
        uploader = self._open_import_page(app)
        uploader.set_value(("nocols.csv", b"date,amount\n2025-01-01,5\n", "text/csv"))
        app.run()
        self._click_import(app)

        assert not app.exception
        assert "Missing columns: description" in self._error_text(app)
