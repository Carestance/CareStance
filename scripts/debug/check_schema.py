import sys
import os

# Add the project root to the python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import engine
from sqlalchemy import text

def check_schema():
    print("Checking users table schema...")
    with engine.connect() as conn:
        try:
            # For PostgreSQL/Supabase
            result = conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'users'"))
            columns = [row[0] for row in result]
            print(f"Columns in 'users' table: {columns}")
            if 'contact_number' in columns:
                print("SUCCESS: 'contact_number' column found.")
            else:
                print("FAILURE: 'contact_number' column NOT found.")
        except Exception as e:
            # Fallback for SQLite
            try:
                result = conn.execute(text("PRAGMA table_info(users)"))
                columns = [row[1] for row in result]
                print(f"Columns in 'users' table (SQLite): {columns}")
                if 'contact_number' in columns:
                    print("SUCCESS: 'contact_number' column found.")
                else:
                    print("FAILURE: 'contact_number' column NOT found.")
            except Exception as e2:
                print(f"Error checking schema: {e} / {e2}")

if __name__ == "__main__":
    check_schema()
