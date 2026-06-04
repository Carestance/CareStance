"""
Migration v8: Add cancelled tracking columns for appointments.
This migration adds cancelled_by and cancelled_by_role columns.
"""
import sys
import os
from sqlalchemy import text, create_engine
from dotenv import load_dotenv

load_dotenv()

# Add the project root to the python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import engine

def migrate_engine(db_engine, name):
    print(f"=== Running Migration v8 on: {name} ===")
    try:
        with db_engine.connect() as conn:
            appointment_columns = {
                "cancelled_by": "VARCHAR(255)",
                "cancelled_by_role": "VARCHAR(50)",
            }
            for col, col_type in appointment_columns.items():
                try:
                    conn.execute(text(f"ALTER TABLE appointments ADD COLUMN {col} {col_type}"))
                    print(f"  ✅ Added appointments.{col}")
                except Exception as e:
                    print(f"  ⏭️  Skipping appointments.{col} (already exists or error): {e}")

            if hasattr(conn, "commit"):
                conn.commit()

            # Create explicit indexes for all remaining columns to speed up queries
            index_columns = [
                "student_id", "counsellor_id", "appointment_time", "status",
                "payment_status", "meeting_link", "razorpay_order_id", "razorpay_payment_id",
                "counsellor_joined", "joined_at", "student_joined", "student_joined_at",
                "actual_overlap_minutes", "cancelled_by", "cancelled_by_role"
            ]
            for col in index_columns:
                idx_name = f"ix_appointments_{col}"
                try:
                    conn.execute(text(f"CREATE INDEX IF NOT EXISTS {idx_name} ON appointments ({col})"))
                    print(f"  ✅ Created index {idx_name} on appointments({col})")
                except Exception as e:
                    print(f"  ⏭️  Skipping index {idx_name} (error or exists): {e}")

            if hasattr(conn, "commit"):
                conn.commit()
            print(f"=== Migration v8 complete for: {name} ===\n")
    except Exception as e:
        print(f"Error connecting to database {name}: {e}")

def migrate_all():
    # 1. Migrate default database engine
    migrate_engine(engine, "Default DB (SQLite or configured DB)")

    # 2. Check if there's any separate Supabase / Postgres URL in the environment
    postgres_url = os.getenv("DATABASE_URL")
    if postgres_url and "sqlite" not in postgres_url:
        if postgres_url.startswith("postgres://"):
            postgres_url = postgres_url.replace("postgres://", "postgresql://", 1)
        try:
            pg_engine = create_engine(postgres_url)
            migrate_engine(pg_engine, "Production/Supabase Postgres DB")
        except Exception as e:
            print(f"Error initializing Postgres engine: {e}")

if __name__ == "__main__":
    migrate_all()
