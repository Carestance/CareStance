import sys
import os

# Add the project root to the python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import engine
from sqlalchemy import text

def migrate():
    print("Connecting to database and adding contact_number column...")
    with engine.connect() as conn:
        try:
            # Check if column exists first (optional but safer)
            conn.execute(text("ALTER TABLE users ADD COLUMN contact_number VARCHAR"))
            conn.commit()
            print("Successfully added contact_number column to users table.")
        except Exception as e:
            print(f"Error adding column (it might already exist): {e}")

if __name__ == "__main__":
    migrate()
