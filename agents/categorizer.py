"""
CategorizerAgent — Automatically assigns categories to transactions.

Uses keyword matching to detect what a transaction is about.
No API key needed — pure Python logic.
"""

from dataclasses import dataclass

# Keyword-to-category mapping (German + English terms)
CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "Gehalt": [
        "gehalt", "lohn", "salary", "wage", "bonus", "praemie",
        "arbeitgeber", "employer",
    ],
    "Miete & Wohnen": [
        "miete", "rent", "wohnung", "strom", "electricity", "gas",
        "heizung", "heating", "nebenkosten", "hausverwaltung", "gez",
        "rundfunk", "internet", "telekom", "vodafone", "o2",
    ],
    "Lebensmittel": [
        "rewe", "edeka", "aldi", "lidl", "netto", "penny", "kaufland",
        "supermarkt", "grocery", "lebensmittel", "dm ", "rossmann",
        "drogerie", "bakery", "baecker",
    ],
    "Restaurant & Cafe": [
        "restaurant", "cafe", "kaffee", "coffee", "pizza", "burger",
        "lieferando", "lieferheld", "uber eats", "mcdonalds", "subway",
        "starbucks", "doener", "imbiss", "bar ",
    ],
    "Transport": [
        "db ", "deutsche bahn", "bahn", "bvg", "mvv", "hvv", "tank",
        "benzin", "fuel", "uber", "taxi", "bus", "parkhaus", "parking",
        "adac", "car2go", "sharenow", "flixbus", "auto",
    ],
    "Versicherung": [
        "versicherung", "insurance", "allianz", "aok", "tk ", "barmer",
        "huk", "ergo", "krankenkasse", "health insurance",
    ],
    "Gesundheit": [
        "apotheke", "pharmacy", "arzt", "doctor", "krankenhaus",
        "hospital", "zahnarzt", "dentist", "optiker", "fitness",
        "gym", "fitnessstudio",
    ],
    "Unterhaltung": [
        "netflix", "spotify", "amazon prime", "disney", "kino", "cinema",
        "theater", "konzert", "concert", "playstation", "steam", "gaming",
        "apple music", "youtube",
    ],
    "Shopping": [
        "amazon", "zalando", "h&m", "zara", "mediamarkt", "saturn",
        "ikea", "ebay", "otto", "kleidung", "clothing", "electronics",
    ],
    "Bildung": [
        "uni", "university", "hochschule", "semesterbeitrag", "buch",
        "book", "kurs", "course", "udemy", "coursera", "weiterbildung",
    ],
    "Sparen & Investieren": [
        "sparplan", "etf", "depot", "aktien", "stocks", "investment",
        "tagesgeld", "festgeld", "trade republic", "scalable",
    ],
}


@dataclass
class CategorizationResult:
    """Result of categorizing a transaction."""
    category: str
    confidence: str  # "high", "medium", "low"
    matched_keyword: str | None


class CategorizerAgent:
    """Assigns categories to transactions based on keyword matching."""

    def __init__(self, custom_rules: dict[str, list[str]] | None = None):
        self.rules = dict(CATEGORY_KEYWORDS)
        if custom_rules:
            for cat, keywords in custom_rules.items():
                self.rules.setdefault(cat, []).extend(keywords)

    def categorize(self, description: str) -> CategorizationResult:
        """Categorize a single transaction by its description."""
        desc_lower = description.lower().strip()

        # Try exact substring match
        for category, keywords in self.rules.items():
            for keyword in keywords:
                if keyword in desc_lower:
                    return CategorizationResult(
                        category=category,
                        confidence="high",
                        matched_keyword=keyword,
                    )

        # Fallback
        return CategorizationResult(
            category="Sonstiges",
            confidence="low",
            matched_keyword=None,
        )

    def categorize_batch(
        self, descriptions: list[str]
    ) -> list[CategorizationResult]:
        """Categorize multiple transactions at once."""
        return [self.categorize(desc) for desc in descriptions]

    @property
    def available_categories(self) -> list[str]:
        """Return all known categories."""
        return sorted(self.rules.keys()) + ["Sonstiges"]
