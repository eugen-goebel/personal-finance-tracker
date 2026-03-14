"""Tests for CategorizerAgent."""

from agents.categorizer import CategorizerAgent


class TestCategorizer:
    def test_detects_supermarket(self):
        agent = CategorizerAgent()
        result = agent.categorize("REWE Supermarkt Berlin")
        assert result.category == "Lebensmittel"
        assert result.confidence == "high"

    def test_detects_rent(self):
        agent = CategorizerAgent()
        result = agent.categorize("Miete Januar 2025")
        assert result.category == "Miete & Wohnen"

    def test_detects_salary(self):
        agent = CategorizerAgent()
        result = agent.categorize("Gehalt Arbeitgeber GmbH")
        assert result.category == "Gehalt"

    def test_detects_transport(self):
        agent = CategorizerAgent()
        result = agent.categorize("Deutsche Bahn Fernverkehr")
        assert result.category == "Transport"

    def test_detects_entertainment(self):
        agent = CategorizerAgent()
        result = agent.categorize("Netflix Monatsabo")
        assert result.category == "Unterhaltung"

    def test_detects_insurance(self):
        agent = CategorizerAgent()
        result = agent.categorize("Allianz Haftpflichtversicherung")
        assert result.category == "Versicherung"

    def test_unknown_returns_sonstiges(self):
        agent = CategorizerAgent()
        result = agent.categorize("XYZABC123 unknown")
        assert result.category == "Sonstiges"
        assert result.confidence == "low"

    def test_case_insensitive(self):
        agent = CategorizerAgent()
        result = agent.categorize("NETFLIX ABO")
        assert result.category == "Unterhaltung"

    def test_batch_categorize(self):
        agent = CategorizerAgent()
        results = agent.categorize_batch(["REWE", "Netflix", "Unknown thing"])
        assert len(results) == 3
        assert results[0].category == "Lebensmittel"
        assert results[1].category == "Unterhaltung"
        assert results[2].category == "Sonstiges"

    def test_custom_rules(self):
        agent = CategorizerAgent(custom_rules={"Haustier": ["fressnapf", "tierarzt"]})
        result = agent.categorize("Fressnapf Hundefutter")
        assert result.category == "Haustier"

    def test_available_categories(self):
        agent = CategorizerAgent()
        cats = agent.available_categories
        assert "Sonstiges" in cats
        assert "Gehalt" in cats
        assert len(cats) >= 10
