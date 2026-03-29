"""
DataIngestionAgent — Imports transactions from CSV files or manual input.

Reads CSV files (like bank statement exports), validates the data,
and stores transactions in the database.
"""

import io
from datetime import date, datetime
from dataclasses import dataclass, field

import pandas as pd
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from db.models import Transaction
from agents.categorizer import CategorizerAgent


class TransactionInput(BaseModel):
    """Validated input for a single transaction."""
    date: date
    description: str
    amount: float
    category: str | None = None

    @field_validator("description")
    @classmethod
    def description_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Description must not be empty")
        return v.strip()

    @field_validator("amount")
    @classmethod
    def amount_not_zero(cls, v: float) -> float:
        if v == 0:
            raise ValueError("Amount must not be zero")
        return round(v, 2)


@dataclass
class ImportResult:
    """Summary of a CSV import operation."""
    total_rows: int = 0
    imported: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)


class DataIngestionAgent:
    """Handles importing and creating transactions."""

    def __init__(self, db: Session):
        self.db = db
        self.categorizer = CategorizerAgent()

    def add_transaction(self, txn_input: TransactionInput) -> Transaction:
        """Add a single transaction to the database."""
        # Auto-categorize if no category provided
        if not txn_input.category:
            result = self.categorizer.categorize(txn_input.description)
            category = result.category
        else:
            category = txn_input.category

        # Determine type from amount sign
        txn_type = "income" if txn_input.amount > 0 else "expense"

        txn = Transaction(
            date=txn_input.date,
            description=txn_input.description,
            amount=txn_input.amount,
            category=category,
            transaction_type=txn_type,
        )
        self.db.add(txn)
        self.db.commit()
        self.db.refresh(txn)
        return txn

    def import_csv(self, file_content: str | bytes) -> ImportResult:
        """Import transactions from CSV content.

        Expected columns: date, description, amount
        Optional column: category
        """
        result = ImportResult()

        if isinstance(file_content, bytes):
            file_content = file_content.decode("utf-8")

        try:
            df = pd.read_csv(io.StringIO(file_content))
        except Exception as e:
            result.errors.append(f"Failed to parse CSV: {e}")
            return result

        # Normalize column names
        df.columns = [c.strip().lower() for c in df.columns]

        # Check required columns
        required = {"date", "description", "amount"}
        if not required.issubset(set(df.columns)):
            missing = required - set(df.columns)
            result.errors.append(f"Missing columns: {', '.join(missing)}")
            return result

        result.total_rows = len(df)

        for idx, row in df.iterrows():
            try:
                # Parse date
                txn_date = pd.to_datetime(row["date"]).date()

                # Parse amount
                amount = float(str(row["amount"]).replace(",", "."))

                # Get category
                category = None
                if "category" in df.columns and pd.notna(row.get("category")):
                    category = str(row["category"]).strip()

                txn_input = TransactionInput(
                    date=txn_date,
                    description=str(row["description"]),
                    amount=amount,
                    category=category if category else None,
                )
                self.add_transaction(txn_input)
                result.imported += 1

            except Exception as e:
                result.skipped += 1
                result.errors.append(f"Row {idx + 1}: {e}")

        return result

    def get_transactions(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
        category: str | None = None,
        transaction_type: str | None = None,
    ) -> list[Transaction]:
        """Query transactions with optional filters."""
        query = self.db.query(Transaction)

        if start_date:
            query = query.filter(Transaction.date >= start_date)
        if end_date:
            query = query.filter(Transaction.date <= end_date)
        if category:
            query = query.filter(Transaction.category == category)
        if transaction_type:
            query = query.filter(Transaction.transaction_type == transaction_type)

        return query.order_by(Transaction.date.desc()).all()

    def delete_transaction(self, txn_id: int) -> bool:
        """Delete a transaction by ID. Returns True if found and deleted."""
        txn = self.db.query(Transaction).filter(Transaction.id == txn_id).first()
        if txn:
            self.db.delete(txn)
            self.db.commit()
            return True
        return False
