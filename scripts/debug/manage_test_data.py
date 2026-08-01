import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.database import SessionLocal
from app import models
from app.main import get_password_hash

db = SessionLocal()

def get_or_create_user(email):
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user:
        user = models.User(
            email=email,
            hashed_password=get_password_hash("testpass"),
            full_name="Test User"
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        print(f"Created user: {email}")
    return user

def clear_assessment(user):
    existing = db.query(models.AssessmentResult).filter(models.AssessmentResult.user_id == user.id).first()
    if existing:
        db.delete(existing)
        db.commit()
    print(f"Cleared assessment for {user.email}")

def seed_phase2(user, category="Focused Specialist"):
    clear_assessment(user)
    result = models.AssessmentResult(
        user_id=user.id,
        phase_2_category=category,
        personality="Ambivert",
        goal_status="Goal Aware",
        confidence=0.9,
        raw_answers={"mock": "data"}
    )
    db.add(result)
    db.commit()
    print(f"Seeded Phase 2 ({category}) for {user.email}")

def seed_phase3(user, category="Focused Specialist"):
    seed_phase2(user, category)
    result = db.query(models.AssessmentResult).filter(models.AssessmentResult.user_id == user.id).first()
    result.phase3_answers = {"mock": "p3_data"}
    result.phase3_analysis = "Phase 3 Mock Analysis"
    db.commit()
    print(f"Seeded Phase 3 (Completed) for {user.email}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 manage_test_data.py <email> <action> [category]")
        print("Actions: clear, phase2, phase3")
        sys.exit(1)

    email = sys.argv[1]
    action = sys.argv[2]
    category = sys.argv[3] if len(sys.argv) > 3 else "Focused Specialist"

    user = get_or_create_user(email)

    if action == "clear":
        clear_assessment(user)
    elif action == "phase2":
        seed_phase2(user, category)
    elif action == "phase3":
        seed_phase3(user, category)
    else:
        print("Unknown action")

    db.close()
