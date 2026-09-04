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
