import sys
import os

# Add the project root to the python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import engine
from app.models import Base

def init_db():
    print("Connecting to database and creating tables...")
    try:
        Base.metadata.create_all(bind=engine)
        print("Success! Tables created in Supabase.")
    except Exception as e:
        print(f"Error creating tables: {e}")

if __name__ == "__main__":
    init_db()
