import sys
import os

# Add the project root to sys.path to allow imports from app
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import models
from app.database import SessionLocal, engine

def verify():
    # Ensure tables are created
    models.Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    try:
        # 1. Create a test user if none exists
        user = db.query(models.User).first()
        if not user:
            print("No users found in database. Creating a test user...")
            from app.main import get_password_hash
            user = models.User(email="test@example.com", hashed_password=get_password_hash("testpass"), full_name="Test User")
            db.add(user)
            db.commit()
            db.refresh(user)
        
        # 2. Add a test feedback
        print(f"Adding feedback for user: {user.full_name}")
        feedback = models.Feedback(
            user_id=user.id,
            content="Verification test feedback",
            rating=5
        )
        db.add(feedback)
        db.commit()
        db.refresh(feedback)
        
        # 3. Verify feedback retrieval
        retrieved = db.query(models.Feedback).filter(models.Feedback.id == feedback.id).first()
        if retrieved and retrieved.content == "Verification test feedback":
            print("SUCCESS: Feedback correctly saved and retrieved.")
        else:
            print("FAILURE: Feedback not found or content mismatch.")
            return False
            
        # 4. Verify relationship
        if len(user.feedbacks) > 0:
            print(f"SUCCESS: User relationship works. User has {len(user.feedbacks)} feedback(s).")
        else:
            print("FAILURE: User relationship not working.")
            return False
            
        # 5. Cleanup
        db.delete(retrieved)
        db.commit()
        print("Cleanup complete.")
        return True

    except Exception as e:
        print(f"ERROR during verification: {e}")
        return False
    finally:
        db.close()

if __name__ == "__main__":
    success = verify()
    sys.exit(0 if success else 1)
