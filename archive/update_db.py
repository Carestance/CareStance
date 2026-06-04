import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), "learnloop.db")

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

try:
    cursor.execute("ALTER TABLE users ADD COLUMN role VARCHAR DEFAULT 'student'")
    print("Added role column to users.")
except sqlite3.OperationalError as e:
    print(f"Role column may already exist: {e}")

conn.commit()
conn.close()

from app.database import engine
from app.models import Base
Base.metadata.create_all(bind=engine)
print("Updated database schemas with new tables.")
