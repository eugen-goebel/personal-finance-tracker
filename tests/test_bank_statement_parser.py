"""Tests for the bank statement parser (MT940 and OFX formats)."""

import pytest

from agents.bank_statement_parser import (
    BankStatementParser,
    _get_extension,
    _build_mt940_description,
    _build_ofx_description,
    SUPPORTED_EXTENSIONS,
)
from agents.data_ingestion import TransactionInput


@pytest.fixture
def parser():
    return BankStatementParser()


# ---------------------------------------------------------------------------
# MT940 format
# ---------------------------------------------------------------------------

SAMPLE_MT940 = b"""\
{1:F01BANKDEFFXXXX0000000000}{2:O9400000000000000000000000000000000000000N}{4:
:20:STARTUMS
:25:10020030/1234567890
:28C:0
:60F:C250101EUR1000,00
:61:2501020102D50,00NMSC
REWE Supermarkt
:86:005?00Kartenzahlung?20REWE Einkauf?32REWE Markt Berlin
:61:2501050105C3200,00NMSC
Gehalt
:86:051?00Gehaltseingang?20Lohn Januar 2025?32Arbeitgeber GmbH
:62F:C250105EUR4150,00
-}
"""

SAMPLE_MT940_EMPTY = b"""\
{1:F01BANKDEFFXXXX0000000000}{2:O9400000000000000000000000000000000000000N}{4:
:20:STARTUMS
:25:10020030/1234567890
:28C:0
:60F:C250101EUR1000,00
:62F:C250101EUR1000,00
-}
"""


class TestMT940Parsing:

    def test_parse_returns_transactions(self, parser):
        result = parser.parse(SAMPLE_MT940, "statement.mt940")
        assert isinstance(result, list)
        assert len(result) > 0

    def test_all_items_are_transaction_input(self, parser):
        result = parser.parse(SAMPLE_MT940, "statement.sta")
        for txn in result:
            assert isinstance(txn, TransactionInput)

    def test_amounts_are_nonzero(self, parser):
        result = parser.parse(SAMPLE_MT940, "statement.mt940")
        for txn in result:
            assert txn.amount != 0

    def test_descriptions_not_empty(self, parser):
        result = parser.parse(SAMPLE_MT940, "statement.mt940")
        for txn in result:
            assert len(txn.description.strip()) > 0

    def test_empty_statement_returns_empty_list(self, parser):
        result = parser.parse(SAMPLE_MT940_EMPTY, "empty.mt940")
        assert result == []

    def test_sta_extension_works(self, parser):
        result = parser.parse(SAMPLE_MT940, "export.sta")
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# OFX format
# ---------------------------------------------------------------------------

SAMPLE_OFX = b"""\
OFXHEADER:100
DATA:OFXSGML
VERSION:102
SECURITY:NONE
ENCODING:USASCII
CHARSET:1252
COMPRESSION:NONE
OLDFILEUID:NONE
NEWFILEUID:NONE

<OFX>
<SIGNONMSGSRSV1>
<SONRS>
<STATUS>
<CODE>0
<SEVERITY>INFO
</STATUS>
<DTSERVER>20250130120000
<LANGUAGE>DEU
</SONRS>
</SIGNONMSGSRSV1>
<BANKMSGSRSV1>
<STMTTRNRS>
<TRNUID>0
<STATUS>
<CODE>0
<SEVERITY>INFO
</STATUS>
<STMTRS>
<CURDEF>EUR
<BANKACCTFROM>
<BANKID>10020030
<ACCTID>1234567890
<ACCTTYPE>CHECKING
</BANKACCTFROM>
<BANKTRANLIST>
<DTSTART>20250101
<DTEND>20250131
<STMTTRN>
<TRNTYPE>DEBIT
<DTPOSTED>20250102
<TRNAMT>-67.43
<FITID>202501020001
<NAME>REWE Supermarkt
<MEMO>Kartenzahlung Berlin
</STMTTRN>
<STMTTRN>
<TRNTYPE>CREDIT
<DTPOSTED>20250105
<TRNAMT>3200.00
<FITID>202501050001
<NAME>Arbeitgeber GmbH
<MEMO>Gehalt Januar
</STMTTRN>
</BANKTRANLIST>
<LEDGERBAL>
<BALAMT>4132.57
<DTASOF>20250131
</LEDGERBAL>
</STMTRS>
</STMTTRNRS>
</BANKMSGSRSV1>
</OFX>
"""


class TestOFXParsing:

    def test_parse_returns_transactions(self, parser):
        result = parser.parse(SAMPLE_OFX, "statement.ofx")
        assert isinstance(result, list)
        assert len(result) == 2

    def test_all_items_are_transaction_input(self, parser):
        result = parser.parse(SAMPLE_OFX, "statement.ofx")
        for txn in result:
            assert isinstance(txn, TransactionInput)

    def test_debit_is_negative(self, parser):
        result = parser.parse(SAMPLE_OFX, "statement.ofx")
        debits = [t for t in result if t.amount < 0]
        assert len(debits) >= 1

    def test_credit_is_positive(self, parser):
        result = parser.parse(SAMPLE_OFX, "statement.ofx")
        credits = [t for t in result if t.amount > 0]
        assert len(credits) >= 1

    def test_qfx_extension_works(self, parser):
        result = parser.parse(SAMPLE_OFX, "statement.qfx")
        assert isinstance(result, list)
        assert len(result) == 2

    def test_descriptions_contain_payee(self, parser):
        result = parser.parse(SAMPLE_OFX, "statement.ofx")
        descriptions = [t.description for t in result]
        assert any("REWE" in d for d in descriptions)
        assert any("Arbeitgeber" in d for d in descriptions)


# ---------------------------------------------------------------------------
# Format detection and error handling
# ---------------------------------------------------------------------------

class TestFormatDetection:

    def test_unsupported_format_raises(self, parser):
        with pytest.raises(ValueError, match="Unsupported file format"):
            parser.parse(b"some data", "report.pdf")

    def test_supported_extensions_constant(self):
        assert ".sta" in SUPPORTED_EXTENSIONS
        assert ".mt940" in SUPPORTED_EXTENSIONS
        assert ".ofx" in SUPPORTED_EXTENSIONS
        assert ".qfx" in SUPPORTED_EXTENSIONS

    def test_get_extension(self):
        assert _get_extension("bank.mt940") == ".mt940"
        assert _get_extension("EXPORT.OFX") == ".ofx"
        assert _get_extension("noext") == ""

    def test_invalid_mt940_returns_empty(self, parser):
        result = parser.parse(b"not valid mt940 data", "bad.mt940")
        assert result == []

    def test_invalid_ofx_raises(self, parser):
        with pytest.raises(ValueError, match="Failed to parse OFX"):
            parser.parse(b"not valid ofx data", "bad.ofx")


# ---------------------------------------------------------------------------
# Description builders
# ---------------------------------------------------------------------------

class TestDescriptionBuilders:

    def test_mt940_with_purpose_and_applicant(self):
        data = {"purpose": "Miete", "applicant_name": "Vermieter GmbH"}
        assert _build_mt940_description(data) == "Miete - Vermieter GmbH"

    def test_mt940_fallback_to_id(self):
        data = {"id": "NMSC"}
        assert _build_mt940_description(data) == "Transaction NMSC"

    def test_mt940_empty_data(self):
        assert "Transaction" in _build_mt940_description({})

    def test_ofx_with_payee_and_memo(self):
        class MockTxn:
            payee = "REWE"
            memo = "Kartenzahlung"
            type = "debit"
        assert _build_ofx_description(MockTxn()) == "REWE - Kartenzahlung"

    def test_ofx_fallback(self):
        class MockTxn:
            payee = None
            memo = None
            type = "credit"
        assert _build_ofx_description(MockTxn()) == "credit"
