# Personal Finance Tracker

A full-stack personal finance application with a REST API, interactive dashboard, and intelligent transaction categorization. Manage transactions, set budgets, and analyze spending trends — all running locally without any API key.

## Features

- **REST API** (FastAPI) with auto-generated Swagger documentation at `/docs`
- **SQLite Database** with SQLAlchemy ORM — no database server needed
- **Smart Categorization** — auto-detects categories from transaction descriptions (German & English)
- **Budget Monitoring** — set monthly limits per category, get warnings at 80% usage
- **Financial Analytics** — monthly summaries, savings rate, spending trends, category breakdowns
- **CSV Import** — upload bank statement exports
- **Streamlit Dashboard** — interactive charts and budget tracking
- **No API Key Required** — everything runs locally

## Architecture

Multi-agent architecture where each agent handles a specific domain:

```
┌──────────────────────────────────────────────────┐
│                  FastAPI Backend                  │
│                   /docs (Swagger)                 │
├──────────────────────────────────────────────────┤
│  DataIngestionAgent  → CSV import, CRUD          │
│  CategorizerAgent    → Auto-categorize by keyword│
│  AnalyticsAgent      → Summaries, trends, metrics│
│  BudgetAgent         → Limits, warnings, status  │
│  ReportAgent         → Formatted text reports    │
├──────────────────────────────────────────────────┤
│              SQLite + SQLAlchemy ORM              │
└──────────────────────────────────────────────────┘
```

## Quick Start

### Installation

```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### REST API

```bash
uvicorn api.main:app --reload
```

Open **http://localhost:8000/docs** for the interactive Swagger documentation.

#### Example API calls

```bash
# Add a transaction
curl -X POST http://localhost:8000/api/transactions/ \
  -H "Content-Type: application/json" \
  -d '{"date": "2025-01-15", "description": "REWE Einkauf", "amount": -67.43}'

# Get all transactions
curl http://localhost:8000/api/transactions/

# Get financial summary
curl http://localhost:8000/api/analytics/summary

# Set a budget
curl -X POST http://localhost:8000/api/budgets/ \
  -H "Content-Type: application/json" \
  -d '{"category": "Lebensmittel", "monthly_limit": 200}'

# Check budget status
curl http://localhost:8000/api/budgets/status?year=2025&month=1
```

### Dashboard

```bash
streamlit run app.py
```

The dashboard provides:
- Financial overview with key metrics (income, expenses, savings rate)
- Monthly trends chart
- Spending by category breakdown
- Budget progress bars with warnings
- Transaction management (add, filter, view)
- CSV import with preview

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/transactions/` | Add a transaction |
| `GET` | `/api/transactions/` | List transactions (with filters) |
| `GET` | `/api/transactions/{id}` | Get single transaction |
| `DELETE` | `/api/transactions/{id}` | Delete a transaction |
| `POST` | `/api/transactions/import` | Import CSV file |
| `GET` | `/api/analytics/summary` | Financial summary |
| `GET` | `/api/analytics/categories` | Spending by category |
| `GET` | `/api/analytics/trends` | Monthly trends |
| `POST` | `/api/budgets/` | Set/update a budget |
| `GET` | `/api/budgets/` | List all budgets |
| `DELETE` | `/api/budgets/{category}` | Delete a budget |
| `GET` | `/api/budgets/status` | Check budget status |

## Sample Data

Includes 3 months of realistic transaction data (`data/sample_transactions.csv`) with German descriptions — salary, rent, groceries, subscriptions, insurance, and more.

## Testing

```bash
pytest tests/ -v
```

65 tests covering all agents, the REST API, and edge cases.

## Project Structure

```
personal-finance-tracker/
├── agents/
│   ├── categorizer.py       # Keyword-based auto-categorization
│   ├── data_ingestion.py    # CSV import & transaction CRUD
│   ├── analytics.py         # Financial metrics & trends
│   ├── budget.py            # Budget limits & warnings
│   └── report.py            # Text report generation
├── api/
│   ├── main.py              # FastAPI application
│   ├── schemas.py           # Pydantic request/response models
│   └── routes/
│       ├── transactions.py  # Transaction endpoints
│       ├── analytics.py     # Analytics endpoints
│       └── budgets.py       # Budget endpoints
├── db/
│   ├── database.py          # SQLAlchemy engine & session setup
│   └── models.py            # ORM models (Transaction, Budget)
├── tests/
│   ├── conftest.py          # Shared fixtures (in-memory DB)
│   ├── test_categorizer.py
│   ├── test_ingestion.py
│   ├── test_analytics.py
│   ├── test_budget.py
│   ├── test_report.py
│   └── test_api.py
├── data/
│   └── sample_transactions.csv
├── app.py                   # Streamlit dashboard
└── requirements.txt
```

## Tech Stack

- **FastAPI** — REST API with automatic OpenAPI docs
- **SQLAlchemy** — ORM for database access
- **SQLite** — Embedded database (no server needed)
- **Streamlit** — Interactive web dashboard
- **pandas** — Data manipulation & CSV parsing
- **Pydantic** — Request/response validation

## License

MIT
