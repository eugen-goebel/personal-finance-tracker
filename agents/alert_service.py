"""
AlertService — Sends monthly budget alert emails.

Checks all budgets for the current month and sends a summary
email when any budget exceeds its warning threshold (80%) or
is fully exceeded.

Supports SMTP configuration via environment variables:
  SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, ALERT_RECIPIENT
"""

import os
import smtplib
from dataclasses import dataclass, field
from datetime import date
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from sqlalchemy.orm import Session

from agents.budget import BudgetAgent, BudgetOverview


@dataclass
class AlertConfig:
    """SMTP configuration for sending alert emails."""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    sender: str = ""
    recipient: str = ""

    @classmethod
    def from_env(cls) -> "AlertConfig":
        """Load configuration from environment variables."""
        return cls(
            smtp_host=os.environ.get("SMTP_HOST", ""),
            smtp_port=int(os.environ.get("SMTP_PORT", "587")),
            smtp_user=os.environ.get("SMTP_USER", ""),
            smtp_password=os.environ.get("SMTP_PASSWORD", ""),
            sender=os.environ.get("SMTP_USER", ""),
            recipient=os.environ.get("ALERT_RECIPIENT", ""),
        )

    @property
    def is_configured(self) -> bool:
        return bool(self.smtp_host and self.smtp_user and self.recipient)


@dataclass
class AlertResult:
    """Result of an alert check and notification attempt."""
    year: int
    month: int
    alerts_triggered: int
    warnings: list[str] = field(default_factory=list)
    email_sent: bool = False
    error: str | None = None


MONTH_NAMES = [
    "", "Januar", "Februar", "Maerz", "April", "Mai", "Juni",
    "Juli", "August", "September", "Oktober", "November", "Dezember",
]


class AlertService:
    """Checks budgets and sends alert emails when thresholds are breached."""

    def __init__(self, db: Session, config: AlertConfig | None = None):
        self.db = db
        self.config = config or AlertConfig.from_env()
        self._budget_agent = BudgetAgent(db)

    def check_and_alert(
        self,
        year: int | None = None,
        month: int | None = None,
        dry_run: bool = False,
    ) -> AlertResult:
        """
        Check budgets for the given month and send an alert email if needed.

        Args:
            year:    Year to check (default: current year)
            month:   Month to check (default: current month)
            dry_run: If True, generate the alert but don't send the email

        Returns:
            AlertResult with details about triggered alerts
        """
        today = date.today()
        y = year or today.year
        m = month or today.month

        overview = self._budget_agent.get_status(y, m)

        if not overview.warnings:
            return AlertResult(year=y, month=m, alerts_triggered=0)

        result = AlertResult(
            year=y,
            month=m,
            alerts_triggered=len(overview.warnings),
            warnings=overview.warnings,
        )

        if dry_run or not self.config.is_configured:
            return result

        try:
            self._send_email(overview)
            result.email_sent = True
        except Exception as e:
            result.error = str(e)

        return result

    def build_email_body(self, overview: BudgetOverview) -> str:
        """Build the plain-text email body from a budget overview."""
        month_name = MONTH_NAMES[overview.month]
        lines = [
            f"Budget-Warnung fuer {month_name} {overview.year}",
            "=" * 50,
            "",
            f"Gesamtbudget: {overview.total_budget:.2f} EUR",
            f"Ausgaben:     {overview.total_spent:.2f} EUR",
            "",
            "Warnungen:",
            "-" * 40,
        ]

        for warning in overview.warnings:
            lines.append(f"  - {warning}")

        lines.append("")
        lines.append("Details:")
        lines.append("-" * 40)

        for b in overview.budgets:
            status_icon = {"ok": "[OK]", "warning": "[!]", "exceeded": "[X]"}[b.status]
            lines.append(
                f"  {status_icon} {b.category}: "
                f"{b.spent:.2f} / {b.monthly_limit:.2f} EUR "
                f"({b.percentage_used:.0f}%)"
            )

        return "\n".join(lines)

    def _send_email(self, overview: BudgetOverview) -> None:
        """Send the alert email via SMTP."""
        month_name = MONTH_NAMES[overview.month]
        subject = f"Budget-Warnung: {month_name} {overview.year}"
        body = self.build_email_body(overview)

        msg = MIMEMultipart()
        msg["From"] = self.config.sender
        msg["To"] = self.config.recipient
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain", "utf-8"))

        with smtplib.SMTP(self.config.smtp_host, self.config.smtp_port) as server:
            server.starttls()
            server.login(self.config.smtp_user, self.config.smtp_password)
            server.send_message(msg)
