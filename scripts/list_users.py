import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.database import SessionLocal
from app.models import User

db = SessionLocal()
users = db.query(User).all()

print("Current Users in Database:")
for user in users:
    print(f"ID: {user.id}, Name: {user.full_name}, Email: {user.email}, Role: {user.role}")

db.close()
