from app import models
from app.database import SessionLocal
import sys

def promote_user(email):
    db = SessionLocal()
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user:
        print(f"Error: User with email {email} not found.")
        db.close()
        return

    user.role = "admin"
    db.commit()
    print(f"Success: User {email} has been promoted to admin.")
    db.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python promote_admin.py <email>")
    else:
        promote_user(sys.argv[1])
