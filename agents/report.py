"""
ReportAgent — Generates text-based financial summaries.

Creates formatted reports from analytics data that can be
displayed in the terminal or in the Streamlit dashboard.
"""

from dataclasses import dataclass

from agents.analytics import AnalyticsResult


@dataclass
class FinancialReport:
    """A formatted financial report."""
    title: str
    sections: list[dict]  # {"heading": str, "content": str}
    raw_data: AnalyticsResult


class ReportAgent:
    """Generates readable financial reports from analytics data."""

    def generate(self, analytics: AnalyticsResult, title: str = "Financial Report") -> FinancialReport:
        """Generate a complete financial report."""
        sections = []

        # Overview
        sections.append({
            "heading": "Overview",
            "content": self._overview_section(analytics),
        })

        # Monthly breakdown
        if analytics.monthly_summaries:
            sections.append({
                "heading": "Monthly Breakdown",
                "content": self._monthly_section(analytics),
            })

        # Category breakdown
        if analytics.category_breakdown:
            sections.append({
                "heading": "Spending by Category",
                "content": self._category_section(analytics),
            })

        # Top expenses
        if analytics.top_expenses:
            sections.append({
                "heading": "Top Expenses",
                "content": self._top_expenses_section(analytics),
            })

        # Insights
        sections.append({
            "heading": "Insights",
            "content": self._insights_section(analytics),
        })

        return FinancialReport(
            title=title,
            sections=sections,
            raw_data=analytics,
        )

    def _overview_section(self, data: AnalyticsResult) -> str:
        lines = [
            f"Total Income:    {data.total_income:>10,.2f}",
            f"Total Expenses:  {data.total_expenses:>10,.2f}",
            f"Net Balance:     {data.net_balance:>10,.2f}",
            f"Savings Rate:    {data.savings_rate:>9.1f}%",
            f"Transactions:    {data.transaction_count:>10}",
        ]
        return "\n".join(lines)

    def _monthly_section(self, data: AnalyticsResult) -> str:
        lines = []
        for m in data.monthly_summaries:
            lines.append(
                f"{m.year}-{m.month:02d}  "
                f"Income: {m.total_income:>9,.2f}  "
                f"Expenses: {m.total_expenses:>9,.2f}  "
                f"Net: {m.net:>9,.2f}  "
                f"Savings: {m.savings_rate:.1f}%"
            )
        return "\n".join(lines)

    def _category_section(self, data: AnalyticsResult) -> str:
        lines = []
        for c in data.category_breakdown:
            bar = "█" * int(c.percentage / 5)
            lines.append(
                f"{c.category:<20s} {c.total:>9,.2f}  "
                f"({c.percentage:>5.1f}%) {bar}"
            )
        return "\n".join(lines)

    def _top_expenses_section(self, data: AnalyticsResult) -> str:
        lines = []
        for i, exp in enumerate(data.top_expenses[:5], 1):
            lines.append(
                f"{i}. {exp['date']}  {exp['description']:<30s}  "
                f"{exp['amount']:>9,.2f}  [{exp['category']}]"
            )
        return "\n".join(lines)

    def _insights_section(self, data: AnalyticsResult) -> str:
        insights = []

        # Savings rate assessment
        if data.savings_rate >= 20:
            insights.append(f"Savings rate of {data.savings_rate:.1f}% is excellent (target: 20%+).")
        elif data.savings_rate >= 10:
            insights.append(f"Savings rate of {data.savings_rate:.1f}% is good, but could be improved.")
        elif data.savings_rate > 0:
            insights.append(f"Savings rate of {data.savings_rate:.1f}% is low. Consider reducing expenses.")
        else:
            insights.append("Spending exceeds income. Review expenses urgently.")

        # Top category
        if data.category_breakdown:
            top = data.category_breakdown[0]
            insights.append(
                f"Largest expense category: {top.category} "
                f"({top.percentage:.1f}% of all spending)."
            )

        # Trend analysis
        if len(data.trends) >= 2:
            last = data.trends[-1]
            prev = data.trends[-2]
            if last.expenses > prev.expenses:
                diff = last.expenses - prev.expenses
                insights.append(
                    f"Spending increased by {diff:,.2f} compared to previous month."
                )
            else:
                diff = prev.expenses - last.expenses
                insights.append(
                    f"Spending decreased by {diff:,.2f} compared to previous month."
                )

        return "\n".join(f"• {i}" for i in insights)
