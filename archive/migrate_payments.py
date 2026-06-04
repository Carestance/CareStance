"""
Migration Script: Add Payment & Transfer tables + Razorpay columns
===================================================================
Run this script to add the new tables and columns required for
the Razorpay split payment system.

Usage:
    python migrate_payments.py
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import text, inspect
from app.database import engine
from app import models  # noqa: F401 – ensures all models are registered


def run_payment_migrations():
    """Create new tables and add missing columns for split payments."""
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()

    print("=" * 60)
    print("CareStance — Payment System Migration")
    print("=" * 60)

    # ── Step 1: Create 'payments' and 'transfers' tables if they don't exist ──
    tables_to_create = []
    if "payments" not in existing_tables:
        tables_to_create.append("payments")
    if "transfers" not in existing_tables:
        tables_to_create.append("transfers")

    if tables_to_create:
        # Create only the missing tables
        models.Base.metadata.create_all(
            bind=engine,
            tables=[
                models.Base.metadata.tables[t]
                for t in tables_to_create
                if t in models.Base.metadata.tables
            ]
        )
        for t in tables_to_create:
            print(f"  ✅ Created table: {t}")
    else:
        print("  ℹ️  Tables 'payments' and 'transfers' already exist")

    # ── Step 2: Add new columns to counsellor_profiles ────────────────────────
    if "counsellor_profiles" in existing_tables:
        existing_cols = [col["name"] for col in inspector.get_columns("counsellor_profiles")]

        migrations = []
        if "razorpay_account_id" not in existing_cols:
            migrations.append(
                "ALTER TABLE counsellor_profiles ADD COLUMN razorpay_account_id VARCHAR"
            )
        if "onboarding_status" not in existing_cols:
            migrations.append(
                "ALTER TABLE counsellor_profiles ADD COLUMN onboarding_status VARCHAR DEFAULT 'not_started'"
            )

        if migrations:
            with engine.connect() as conn:
                for sql in migrations:
                    try:
                        conn.execute(text(sql))
                        print(f"  ✅ {sql}")
                    except Exception as e:
                        print(f"  ⚠️  Skipped (already exists?): {e}")
                conn.commit()
        else:
            print("  ℹ️  Columns 'razorpay_account_id' and 'onboarding_status' already exist")
    else:
        print("  ⚠️  Table 'counsellor_profiles' not found — skipping column migration")

    print()
    print("Migration complete! ✅")
    print("=" * 60)


if __name__ == "__main__":
    run_payment_migrations()
