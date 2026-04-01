"""
BankStatementParser — Parses MT940 and OFX bank statement files.

Converts bank statements from common export formats into TransactionInput
objects ready for import via the DataIngestionAgent.
"""

import io
from datetime import date

import mt940
import ofxparse

from agents.data_ingestion import TransactionInput


SUPPORTED_EXTENSIONS = {".sta", ".mt940", ".ofx", ".qfx"}


class BankStatementParser:
    """Parses MT940 and OFX bank statement files into transaction inputs."""

    def parse(self, content: bytes, filename: str) -> list[TransactionInput]:
        """Parse bank statement content based on file extension.

        Args:
            content:  Raw file bytes
            filename: Original filename (used to detect format)

        Returns:
            List of TransactionInput objects

        Raises:
            ValueError: If the file format is not supported or parsing fails
        """
        ext = _get_extension(filename)

        if ext in (".sta", ".mt940"):
            return self._parse_mt940(content)
        elif ext in (".ofx", ".qfx"):
            return self._parse_ofx(content)
        else:
            raise ValueError(
                f"Unsupported file format: {ext}. "
                f"Supported formats: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
            )

    def _parse_mt940(self, content: bytes) -> list[TransactionInput]:
        """Parse MT940 (SWIFT) bank statement format."""
        try:
            text = content.decode("utf-8", errors="replace")
            transactions_out = []
            statements = mt940.parse(io.StringIO(text))

            for statement in statements:
                for txn in statement.transactions:
                    txn_date = txn.data.get("date")
                    if isinstance(txn_date, date):
                        txn_date_val = txn_date
                    else:
                        continue

                    raw_amount = txn.data.get("amount")
                    if raw_amount is None:
                        continue
                    amount = float(raw_amount.amount if hasattr(raw_amount, "amount") else raw_amount)
                    if amount == 0:
                        continue

                    description = _build_mt940_description(txn.data)

                    transactions_out.append(TransactionInput(
                        date=txn_date_val,
                        description=description,
                        amount=round(amount, 2),
                    ))

            return transactions_out
        except Exception as exc:
            raise ValueError(f"Failed to parse MT940 file: {exc}") from exc

    def _parse_ofx(self, content: bytes) -> list[TransactionInput]:
        """Parse OFX/QFX bank statement format."""
        try:
            ofx = ofxparse.OfxParser.parse(io.BytesIO(content))
            transactions_out = []

            for account in ofx.accounts:
                stmt = account.statement
                if stmt is None:
                    continue

                for txn in stmt.transactions:
                    txn_date = txn.date.date() if hasattr(txn.date, "date") else txn.date
                    amount = float(txn.amount)
                    if amount == 0:
                        continue

                    description = _build_ofx_description(txn)

                    transactions_out.append(TransactionInput(
                        date=txn_date,
                        description=description,
                        amount=round(amount, 2),
                    ))

            return transactions_out
        except Exception as exc:
            raise ValueError(f"Failed to parse OFX file: {exc}") from exc


def _get_extension(filename: str) -> str:
    """Extract lowercase file extension."""
    dot_idx = filename.rfind(".")
    if dot_idx == -1:
        return ""
    return filename[dot_idx:].lower()


def _build_mt940_description(data: dict) -> str:
    """Build a readable description from MT940 transaction data fields."""
    parts = []

    purpose = data.get("purpose")
    if purpose:
        parts.append(str(purpose).strip())

    applicant = data.get("applicant_name")
    if applicant:
        parts.append(str(applicant).strip())

    extra = data.get("extra_details")
    if extra and not parts:
        parts.append(str(extra).strip())

    customer_ref = data.get("customer_reference")
    if customer_ref and not parts:
        parts.append(str(customer_ref).strip())

    if not parts:
        id_code = data.get("id", "")
        parts.append(f"Transaction {id_code}".strip())

    return " - ".join(parts)


def _build_ofx_description(txn) -> str:
    """Build a readable description from OFX transaction fields."""
    parts = []

    if getattr(txn, "payee", None):
        parts.append(str(txn.payee).strip())

    if getattr(txn, "memo", None):
        memo = str(txn.memo).strip()
        if memo and memo not in parts:
            parts.append(memo)

    if not parts:
        if getattr(txn, "type", None):
            parts.append(str(txn.type))
        else:
            parts.append("Bank transaction")

    return " - ".join(parts)
