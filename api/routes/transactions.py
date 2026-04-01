"""Transaction API routes — CRUD operations for financial transactions."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from db.database import get_db
from api.schemas import TransactionCreate, TransactionResponse, ImportResponse, MessageResponse
from agents.data_ingestion import DataIngestionAgent, TransactionInput
from agents.bank_statement_parser import BankStatementParser, SUPPORTED_EXTENSIONS

router = APIRouter(prefix="/api/transactions", tags=["Transactions"])


@router.post("/", response_model=TransactionResponse, status_code=201)
def create_transaction(data: TransactionCreate, db: Session = Depends(get_db)):
    """Add a new transaction."""
    agent = DataIngestionAgent(db)
    txn_input = TransactionInput(
        date=data.date,
        description=data.description,
        amount=data.amount,
        category=data.category,
    )
    txn = agent.add_transaction(txn_input)
    return txn


@router.get("/", response_model=list[TransactionResponse])
def list_transactions(
    start_date: date | None = None,
    end_date: date | None = None,
    category: str | None = None,
    transaction_type: str | None = None,
    db: Session = Depends(get_db),
):
    """List transactions with optional filters."""
    agent = DataIngestionAgent(db)
    return agent.get_transactions(start_date, end_date, category, transaction_type)


@router.get("/{txn_id}", response_model=TransactionResponse)
def get_transaction(txn_id: int, db: Session = Depends(get_db)):
    """Get a single transaction by ID."""
    from db.models import Transaction
    txn = db.query(Transaction).filter(Transaction.id == txn_id).first()
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return txn


@router.delete("/{txn_id}", response_model=MessageResponse)
def delete_transaction(txn_id: int, db: Session = Depends(get_db)):
    """Delete a transaction."""
    agent = DataIngestionAgent(db)
    if not agent.delete_transaction(txn_id):
        raise HTTPException(status_code=404, detail="Transaction not found")
    return {"message": f"Transaction {txn_id} deleted"}


@router.post("/import", response_model=ImportResponse)
async def import_csv(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Import transactions from a CSV file."""
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are supported")

    content = await file.read()
    agent = DataIngestionAgent(db)
    result = agent.import_csv(content)

    return ImportResponse(
        total_rows=result.total_rows,
        imported=result.imported,
        skipped=result.skipped,
        errors=result.errors,
    )


@router.post("/import-statement", response_model=ImportResponse)
async def import_bank_statement(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Import transactions from a bank statement (MT940, OFX, QFX)."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    ext = file.filename[file.filename.rfind("."):].lower() if "." in file.filename else ""
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported format. Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}",
        )

    content = await file.read()
    parser = BankStatementParser()
    try:
        transactions = parser.parse(content, file.filename)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    agent = DataIngestionAgent(db)
    imported = 0
    errors = []

    for i, txn_input in enumerate(transactions, 1):
        try:
            agent.add_transaction(txn_input)
            imported += 1
        except Exception as exc:
            errors.append(f"Transaction {i}: {exc}")

    return ImportResponse(
        total_rows=len(transactions),
        imported=imported,
        skipped=len(transactions) - imported,
        errors=errors,
    )
