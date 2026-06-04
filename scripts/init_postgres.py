import sys
import os

# Add the project root to the python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import engine
from app.models import Base

def init_db():
    print("Connecting to PostgreSQL and creating tables...")
    try:
        # This will create all tables defined in models.py using SQLAlchemy
        Base.metadata.create_all(bind=engine)
        print("Success! PostgreSQL tables created.")
    except Exception as e:
        print(f"Error creating tables: {e}")

if __name__ == "__main__":
    init_db()
