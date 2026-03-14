"""Tests for ReportAgent."""

from datetime import date

from agents.analytics import AnalyticsAgent
from agents.report import ReportAgent
from agents.data_ingestion import DataIngestionAgent, TransactionInput


def _seed(db):
    agent = DataIngestionAgent(db)
    data = [
        (date(2025, 1, 1), "Gehalt", 3000.00),
        (date(2025, 1, 5), "Miete", -850.00),
        (date(2025, 1, 10), "REWE", -65.00),
        (date(2025, 2, 1), "Gehalt", 3000.00),
        (date(2025, 2, 5), "Miete", -850.00),
    ]
    for d, desc, amt in data:
        agent.add_transaction(TransactionInput(date=d, description=desc, amount=amt))


class TestReport:
    def test_generates_report(self, db):
        _seed(db)
        analytics = AnalyticsAgent(db).get_summary()
        report = ReportAgent().generate(analytics)
        assert report.title == "Financial Report"
        assert len(report.sections) >= 3

    def test_has_overview_section(self, db):
        _seed(db)
        analytics = AnalyticsAgent(db).get_summary()
        report = ReportAgent().generate(analytics)
        headings = [s["heading"] for s in report.sections]
        assert "Overview" in headings

    def test_has_insights(self, db):
        _seed(db)
        analytics = AnalyticsAgent(db).get_summary()
        report = ReportAgent().generate(analytics)
        headings = [s["heading"] for s in report.sections]
        assert "Insights" in headings

    def test_custom_title(self, db):
        _seed(db)
        analytics = AnalyticsAgent(db).get_summary()
        report = ReportAgent().generate(analytics, title="Q1 Report")
        assert report.title == "Q1 Report"

    def test_raw_data_attached(self, db):
        _seed(db)
        analytics = AnalyticsAgent(db).get_summary()
        report = ReportAgent().generate(analytics)
        assert report.raw_data.total_income == 6000.00
