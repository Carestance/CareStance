"""
Migration v7: Add Jitsi session tracking, counsellor ratings table, and rating stats.

This migration covers all schema changes from the Jitsi auto-completion
and counsellor rating features that were recently added.
"""
import sys
import os

# Add the project root to the python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import engine
from sqlalchemy import text


def migrate():
    print("=== Migration v7: Jitsi Tracking + Counsellor Ratings ===\n")

    with engine.connect() as conn:

        # ── 1. Appointment join-tracking columns ─────────────────────────────
        appointment_columns = {
            "counsellor_joined": "BOOLEAN DEFAULT 0",
            "joined_at": "DATETIME",
            "student_joined": "BOOLEAN DEFAULT 0",
            "student_joined_at": "DATETIME",
            "actual_overlap_minutes": "INTEGER DEFAULT 0",
        }
        for col, col_type in appointment_columns.items():
            try:
                conn.execute(text(f"ALTER TABLE appointments ADD COLUMN {col} {col_type}"))
                print(f"  ✅ Added appointments.{col}")
            except Exception as e:
                print(f"  ⏭️  Skipping appointments.{col} (already exists): {e}")

        # ── 2. CounsellorProfile rating stats ────────────────────────────────
        profile_columns = {
            "average_rating": "FLOAT DEFAULT 5.0",
            "rating_count": "INTEGER DEFAULT 0",
        }
        for col, col_type in profile_columns.items():
            try:
                conn.execute(text(f"ALTER TABLE counsellor_profiles ADD COLUMN {col} {col_type}"))
                print(f"  ✅ Added counsellor_profiles.{col}")
            except Exception as e:
                print(f"  ⏭️  Skipping counsellor_profiles.{col} (already exists): {e}")

        # ── 3. Create counsellor_ratings table ───────────────────────────────
        try:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS counsellor_ratings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    appointment_id INTEGER UNIQUE,
                    counsellor_id INTEGER,
                    student_id INTEGER,
                    rating INTEGER NOT NULL,
                    review TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (appointment_id) REFERENCES appointments(id),
                    FOREIGN KEY (counsellor_id) REFERENCES users(id),
                    FOREIGN KEY (student_id) REFERENCES users(id)
                )
            """))
            print("  ✅ Created counsellor_ratings table")
        except Exception as e:
            print(f"  ⏭️  Skipping counsellor_ratings table (already exists): {e}")

        # ── 4. Create indexes on counsellor_ratings ──────────────────────────
        indexes = [
            ("ix_counsellor_ratings_appointment_id", "counsellor_ratings", "appointment_id"),
            ("ix_counsellor_ratings_counsellor_id", "counsellor_ratings", "counsellor_id"),
            ("ix_counsellor_ratings_student_id", "counsellor_ratings", "student_id"),
        ]
        for idx_name, table, col in indexes:
            try:
                conn.execute(text(f"CREATE INDEX IF NOT EXISTS {idx_name} ON {table}({col})"))
                print(f"  ✅ Created index {idx_name}")
            except Exception as e:
                print(f"  ⏭️  Skipping index {idx_name}: {e}")

        conn.commit()
        print("\n=== Migration v7 complete! ===")


if __name__ == "__main__":
    migrate()
