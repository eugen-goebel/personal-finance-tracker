"""
DataIngestionAgent — Imports transactions from CSV files or manual input.

Reads CSV files (like bank statement exports), validates the data,
and stores transactions in the database.
"""

import io
import logging
from dataclasses import dataclass, field
from datetime import date

import pandas as pd
from pydantic import BaseModel, ValidationError, field_validator
from sqlalchemy.orm import Session

from agents.categorizer import CategorizerAgent
from agents.validation import require_finite
from db.models import Transaction

logger = logging.getLogger(__name__)


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
        require_finite(v, "Amount must be a finite number")
        if v == 0:
            raise ValueError("Amount must not be zero")
        return round(v, 2)


def _describe_validation_error(exc: ValidationError) -> str:
    """Summarise a validation error as "field: rule" without pydantic's wrapper.

    str(ValidationError) carries the model name, the rejected input value and a
    docs URL. Only the field name and the message are kept.
    """
    parts = []
    for err in exc.errors(include_url=False, include_context=False, include_input=False):
        field_name = ".".join(str(p) for p in err["loc"])
        message = err["msg"].removeprefix("Value error, ")
        parts.append(f"{field_name}: {message}" if field_name else message)
    return "; ".join(parts)


def _is_blank(value) -> bool:
    """True for an empty CSV cell, which pandas reads as NaN.

    A cell holding only spaces is a string and goes through the normal
    validation ("Description must not be empty").
    """
    return bool(pd.isna(value))


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
        try:
            self.db.add(txn)
            self.db.commit()
            self.db.refresh(txn)
        except Exception:
            # A failed flush leaves the session unusable until it is rolled
            # back. Callers import many rows with one session and carry on
            # after a failed row, so without this every later row would fail
            # with PendingRollbackError.
            self.db.rollback()
            raise
        return txn

    @staticmethod
    def _skip(result: ImportResult, message: str) -> None:
        result.skipped += 1
        result.errors.append(message)

    def import_csv(self, file_content: str | bytes) -> ImportResult:
        """Import transactions from CSV content.

        Expected columns: date, description, amount
        Optional column: category
        """
        result = ImportResult()

        if isinstance(file_content, bytes):
            file_content = file_content.decode("utf-8")

        try:
            # Only a truly empty cell counts as missing. pandas' default NA
            # tokens ("nan", "NA", "NULL", ...) stay text and go through the
            # normal checks, so a literal "nan" amount is reported as not finite
            # rather than as missing.
            df = pd.read_csv(io.StringIO(file_content), keep_default_na=False, na_values=[""])
        except Exception:
            # pandas' message can quote file content and parser internals, so it
            # goes to the server log only; the caller gets a fixed message.
            logger.exception("Failed to parse CSV")
            result.errors.append("Failed to parse CSV: the file could not be read as CSV")
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
            row_no = idx + 1

            # An empty cell reaches us as NaN: str(NaN) is "nan", a valid-looking
            # description, and pd.to_datetime(NaN) is NaT, which TransactionInput
            # rejects with a TypeError rather than a ValidationError.
            missing = [col for col in ("date", "description", "amount") if _is_blank(row[col])]
            if missing:
                self._skip(result, f"Row {row_no}: missing {', '.join(missing)}")
                continue

            # Messages written by this project (validation rules) are returned as
            # they are. Anything raised by pandas, pydantic's wrapper or the
            # database is logged and replaced by a fixed message.
            try:
                txn_date = pd.to_datetime(row["date"]).date()
            except Exception:
                logger.warning("CSV row %d: invalid date", row_no, exc_info=True)
                self._skip(result, f"Row {row_no}: invalid date")
                continue

            try:
                amount = float(str(row["amount"]).replace(",", "."))
            except Exception:
                logger.warning("CSV row %d: invalid amount", row_no, exc_info=True)
                self._skip(result, f"Row {row_no}: invalid amount")
                continue

            category = None
            if "category" in df.columns and pd.notna(row.get("category")):
                category = str(row["category"]).strip()

            try:
                txn_input = TransactionInput(
                    date=txn_date,
                    description=str(row["description"]),
                    amount=amount,
                    category=category if category else None,
                )
            except ValidationError as exc:
                logger.warning("CSV row %d failed validation", row_no, exc_info=True)
                self._skip(result, f"Row {row_no}: {_describe_validation_error(exc)}")
                continue

            try:
                self.add_transaction(txn_input)
            except Exception:
                logger.exception("Failed to save CSV row %d", row_no)
                self._skip(result, f"Row {row_no}: could not be saved")
                continue

            result.imported += 1

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
