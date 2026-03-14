"""
SQLAlchemy ORM models — define the database tables as Python classes.

Each class = one table. Each attribute = one column.
SQLAlchemy translates these automatically into SQL CREATE TABLE statements.
"""

from datetime import date, datetime

from sqlalchemy import String, Float, Date, DateTime, Integer, func
from sqlalchemy.orm import Mapped, mapped_column

from db.database import Base


class Transaction(Base):
    """A single financial transaction (income or expense)."""

    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False, default="Sonstiges")
    transaction_type: Mapped[str] = mapped_column(String(20), nullable=False)  # "income" or "expense"
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    def __repr__(self) -> str:
        return f"<Transaction {self.date} {self.description} {self.amount:.2f}>"


class Budget(Base):
    """Monthly budget limit for a spending category."""

    __tablename__ = "budgets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    category: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    monthly_limit: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    def __repr__(self) -> str:
        return f"<Budget {self.category} limit={self.monthly_limit:.2f}>"
