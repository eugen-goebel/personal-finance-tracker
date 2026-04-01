"""
Personal Finance Tracker — Streamlit Dashboard.

Interactive web interface for managing transactions, viewing analytics,
and monitoring budgets. No API key required.

To run:
    streamlit run app.py
"""

import io
import os
from datetime import date, datetime

import streamlit as st
import pandas as pd

from db.database import Base, get_engine
from db.models import Transaction, Budget
from sqlalchemy.orm import sessionmaker
from agents.data_ingestion import DataIngestionAgent
from agents.analytics import AnalyticsAgent
from agents.budget import BudgetAgent
from agents.report import ReportAgent
from agents.categorizer import CategorizerAgent
from agents.bank_statement_parser import BankStatementParser


# ---------------------------------------------------------------------------
# Database setup
# ---------------------------------------------------------------------------

DB_PATH = os.path.join(os.path.dirname(__file__), "finance.db")
DB_URL = f"sqlite:///{DB_PATH}"
engine = get_engine(DB_URL)
Base.metadata.create_all(bind=engine)
Session = sessionmaker(bind=engine)


def get_session():
    return Session()


# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Personal Finance Tracker",
    page_icon="💰",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Sidebar navigation
# ---------------------------------------------------------------------------

with st.sidebar:
    st.title("💰 Finance Tracker")
    st.info("Manage your finances locally — no API key needed.")
    st.divider()
    page = st.radio(
        "Navigation",
        ["Dashboard", "Transactions", "Budgets", "Import Data"],
        label_visibility="collapsed",
    )

# ---------------------------------------------------------------------------
# Dashboard page
# ---------------------------------------------------------------------------

if page == "Dashboard":
    st.title("Financial Dashboard")

    db = get_session()
    try:
        analytics = AnalyticsAgent(db)
        result = analytics.get_summary()

        if result.transaction_count == 0:
            st.warning("No transactions yet. Go to **Import Data** to load sample data or upload a CSV.")
            st.stop()

        # Key metrics
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Income", f"{result.total_income:,.2f}")
        col2.metric("Total Expenses", f"{result.total_expenses:,.2f}")
        col3.metric("Net Balance", f"{result.net_balance:,.2f}")
        col4.metric("Savings Rate", f"{result.savings_rate:.1f}%")

        st.divider()

        # Trends chart
        if result.trends:
            st.subheader("Monthly Trends")
            trend_df = pd.DataFrame([
                {"Month": t.label, "Income": t.income, "Expenses": t.expenses}
                for t in result.trends
            ])
            trend_df = trend_df.set_index("Month")
            st.bar_chart(trend_df)

        # Two columns: category breakdown + budget status
        col_left, col_right = st.columns(2)

        with col_left:
            if result.category_breakdown:
                st.subheader("Spending by Category")
                cat_df = pd.DataFrame([
                    {"Category": c.category, "Amount": c.total, "Percent": f"{c.percentage:.1f}%"}
                    for c in result.category_breakdown
                ])
                st.dataframe(cat_df, use_container_width=True, hide_index=True)

        with col_right:
            budget_agent = BudgetAgent(db)
            today = date.today()
            overview = budget_agent.get_status(today.year, today.month)
            if overview.budgets:
                st.subheader("Budget Status")
                for b in overview.budgets:
                    color = "🔴" if b.status == "exceeded" else "🟡" if b.status == "warning" else "🟢"
                    st.write(f"{color} **{b.category}**: {b.spent:.2f} / {b.monthly_limit:.2f}")
                    st.progress(min(b.percentage_used / 100, 1.0))

                if overview.warnings:
                    for w in overview.warnings:
                        st.warning(w)

        # Top expenses
        if result.top_expenses:
            st.subheader("Top Expenses")
            top_df = pd.DataFrame(result.top_expenses)
            st.dataframe(top_df, use_container_width=True, hide_index=True)

        # Report
        with st.expander("Full Report"):
            report_agent = ReportAgent()
            report = report_agent.generate(result)
            for section in report.sections:
                st.markdown(f"**{section['heading']}**")
                st.code(section["content"])

    finally:
        db.close()


# ---------------------------------------------------------------------------
# Transactions page
# ---------------------------------------------------------------------------

elif page == "Transactions":
    st.title("Transactions")

    # Add transaction form
    with st.expander("Add Transaction", expanded=False):
        with st.form("add_txn"):
            col1, col2 = st.columns(2)
            with col1:
                txn_date = st.date_input("Date", value=date.today())
                description = st.text_input("Description", placeholder="e.g., REWE Einkauf")
            with col2:
                amount = st.number_input("Amount", step=0.01, help="Negative = expense, positive = income")
                categorizer = CategorizerAgent()
                categories = categorizer.available_categories
                category = st.selectbox("Category (optional)", ["Auto-detect"] + categories)

            submitted = st.form_submit_button("Add Transaction")
            if submitted and description and amount != 0:
                db = get_session()
                try:
                    agent = DataIngestionAgent(db)
                    from agents.data_ingestion import TransactionInput
                    cat = None if category == "Auto-detect" else category
                    txn_input = TransactionInput(
                        date=txn_date, description=description,
                        amount=amount, category=cat,
                    )
                    txn = agent.add_transaction(txn_input)
                    st.success(f"Added: {txn.description} ({txn.amount:+.2f}) → {txn.category}")
                finally:
                    db.close()

    # Filters
    col1, col2, col3 = st.columns(3)
    with col1:
        filter_type = st.selectbox("Type", ["All", "income", "expense"])
    with col2:
        filter_cat = st.text_input("Category filter", placeholder="e.g., Lebensmittel")
    with col3:
        filter_date = st.date_input("From date", value=None)

    # Transaction list
    db = get_session()
    try:
        agent = DataIngestionAgent(db)
        txns = agent.get_transactions(
            start_date=filter_date if filter_date else None,
            category=filter_cat if filter_cat else None,
            transaction_type=filter_type if filter_type != "All" else None,
        )

        if txns:
            df = pd.DataFrame([
                {
                    "ID": t.id,
                    "Date": str(t.date),
                    "Description": t.description,
                    "Amount": f"{t.amount:+,.2f}",
                    "Category": t.category,
                    "Type": t.transaction_type,
                }
                for t in txns
            ])
            st.dataframe(df, use_container_width=True, hide_index=True)
            st.caption(f"{len(txns)} transactions")
        else:
            st.info("No transactions found.")
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Budgets page
# ---------------------------------------------------------------------------

elif page == "Budgets":
    st.title("Budget Management")

    # Add budget
    with st.form("add_budget"):
        col1, col2 = st.columns(2)
        with col1:
            categorizer = CategorizerAgent()
            budget_cat = st.selectbox("Category", categorizer.available_categories)
        with col2:
            limit = st.number_input("Monthly Limit", min_value=1.0, step=10.0, value=200.0)

        if st.form_submit_button("Set Budget"):
            db = get_session()
            try:
                agent = BudgetAgent(db)
                agent.set_budget(budget_cat, limit)
                st.success(f"Budget set: {budget_cat} = {limit:.2f}/month")
            finally:
                db.close()

    st.divider()

    # Budget status
    db = get_session()
    try:
        agent = BudgetAgent(db)
        today = date.today()

        col1, col2 = st.columns(2)
        with col1:
            year = st.number_input("Year", value=today.year, min_value=2020)
        with col2:
            month = st.number_input("Month", value=today.month, min_value=1, max_value=12)

        overview = agent.get_status(int(year), int(month))

        if overview.budgets:
            for b in overview.budgets:
                col1, col2, col3 = st.columns([3, 1, 1])
                with col1:
                    color = "🔴" if b.status == "exceeded" else "🟡" if b.status == "warning" else "🟢"
                    st.write(f"{color} **{b.category}**")
                    st.progress(min(b.percentage_used / 100, 1.0))
                with col2:
                    st.metric("Spent", f"{b.spent:.2f}")
                with col3:
                    st.metric("Limit", f"{b.monthly_limit:.2f}")

            if overview.warnings:
                st.divider()
                for w in overview.warnings:
                    st.warning(w)
        else:
            st.info("No budgets configured yet. Set one above.")
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Import page
# ---------------------------------------------------------------------------

elif page == "Import Data":
    st.title("Import Transactions")

    # Sample data button
    sample_path = os.path.join(os.path.dirname(__file__), "data", "sample_transactions.csv")
    if os.path.exists(sample_path):
        if st.button("Load Sample Data (3 months of transactions)"):
            db = get_session()
            try:
                agent = DataIngestionAgent(db)
                with open(sample_path, "r") as f:
                    result = agent.import_csv(f.read())
                st.success(f"Imported {result.imported} of {result.total_rows} transactions")
                if result.errors:
                    with st.expander("Errors"):
                        for e in result.errors:
                            st.write(e)
            finally:
                db.close()

    st.divider()

    # CSV upload
    st.subheader("Upload CSV")
    st.caption("Expected columns: `date`, `description`, `amount` (optional: `category`)")

    uploaded = st.file_uploader("Choose CSV file", type=["csv"])
    if uploaded:
        db = get_session()
        try:
            agent = DataIngestionAgent(db)
            content = uploaded.read().decode("utf-8")

            # Preview
            with st.expander("Preview"):
                preview_df = pd.read_csv(io.StringIO(content))
                st.dataframe(preview_df.head(10), use_container_width=True)

            if st.button("Import"):
                result = agent.import_csv(content)
                st.success(f"Imported {result.imported} of {result.total_rows} transactions")
                if result.errors:
                    for e in result.errors:
                        st.error(e)
        finally:
            db.close()

    st.divider()

    # Bank statement upload (MT940 / OFX)
    st.subheader("Upload Bank Statement")
    st.caption("Supported formats: MT940 (.sta, .mt940), OFX (.ofx, .qfx)")

    statement_file = st.file_uploader(
        "Choose bank statement file",
        type=["sta", "mt940", "ofx", "qfx"],
        key="bank_statement",
    )
    if statement_file:
        db = get_session()
        try:
            parser = BankStatementParser()
            raw = statement_file.read()
            transactions = parser.parse(raw, statement_file.name)

            st.info(f"Found {len(transactions)} transactions in statement")

            if transactions:
                preview_data = [
                    {"Date": t.date, "Description": t.description, "Amount": t.amount}
                    for t in transactions[:10]
                ]
                with st.expander("Preview (first 10)"):
                    st.dataframe(pd.DataFrame(preview_data), use_container_width=True)

                if st.button("Import Statement", key="import_statement"):
                    agent = DataIngestionAgent(db)
                    imported = 0
                    errors = []
                    for i, txn_input in enumerate(transactions, 1):
                        try:
                            agent.add_transaction(txn_input)
                            imported += 1
                        except Exception as exc:
                            errors.append(f"Transaction {i}: {exc}")

                    st.success(f"Imported {imported} of {len(transactions)} transactions")
                    if errors:
                        for e in errors:
                            st.error(e)
        except ValueError as exc:
            st.error(f"Failed to parse statement: {exc}")
        finally:
            db.close()
