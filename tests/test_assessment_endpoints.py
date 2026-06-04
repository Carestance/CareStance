import sys
import os
import pytest
from fastapi.testclient import TestClient

# Add parent directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.main import app
from app.database import SessionLocal
from app import models

client = TestClient(app)

def setup_test_user(user_id: int, email: str):
    db = SessionLocal()
    # Clean up existing test user
    db.query(models.AssessmentResult).filter(models.AssessmentResult.user_id == user_id).delete()
    db.query(models.User).filter(models.User.id == user_id).delete()
    db.commit()
    
    # Create test user
    user = models.User(
        id=user_id,
        email=email,
        hashed_password="mockpassword",
        role="student",
        full_name="Test Student"
    )
    db.add(user)
    db.commit()
    db.close()

def teardown_test_user(user_id: int):
    db = SessionLocal()
    db.query(models.AssessmentResult).filter(models.AssessmentResult.user_id == user_id).delete()
    db.query(models.User).filter(models.User.id == user_id).delete()
    db.commit()
    db.close()

def test_grade_10_flow():
    user_id = 9999
    setup_test_user(user_id, "g10_test@carestance.com")
    
    # Set client cookie
    client.cookies.set("user_id", str(user_id))
    
    # Start assessment for Grade 10
    response = client.get("/assessment/start?class_level=10th", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers.get("location") == "/assessment"
    
    # Check state
    response = client.get("/assessment/api/state")
    assert response.status_code == 200
    state = response.json()
    assert state["status"] == "success"
    assert state["student_type"] == "10th"
    assert state["current_phase"] == 1
    
    # Get Phase 1 questions (Swipe Cards)
    response = client.get("/assessment/api/questions")
    assert response.status_code == 200
    p1_data = response.json()
    assert "cards" in p1_data
    cards = p1_data["cards"]
    assert len(cards) == 10
    
    # Submit Phase 1 (Swipe)
    swipes = [{"card_id": c["id"], "direction": "right", "reaction_ms": 500, "dwell_ms": 600, "hesitation_ms": 0} for c in cards]
    response = client.post("/assessment/api/swipe", json={"swipes": swipes})
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    
    # Verify phase transition to Phase 2 (Mentor Chat)
    response = client.get("/assessment/api/state")
    state = response.json()
    assert state["current_phase"] == 2
    
    # Phase 2 (Mentor Chat) E2E Simulation
    chat_completed = False
    for i in range(6):
        response = client.post("/assessment/api/chat", json={"message": f"Answer turn {i}"})
        assert response.status_code == 200
        res_data = response.json()
        assert res_data["status"] == "success"
        if res_data.get("phase_complete"):
            chat_completed = True
            break
            
    assert chat_completed, "Chat phase should successfully complete and transition to next phase"
    
    # Verify we are on Phase 3 (Proxies)
    response = client.get("/assessment/api/state")
    state = response.json()
    assert state["current_phase"] == 3
    
    # Get Phase 3 questions (Context/Proxies)
    response = client.get("/assessment/api/questions")
    p3_data = response.json()
    assert "proxy_questions" in p3_data
    proxies = p3_data["proxy_questions"]
    assert len(proxies) > 0
    
    # Submit Phase 3 answers
    proxy_answers = [{"question_id": pq["id"], "answer": pq["options"][0]["text"]} for pq in proxies]
    response = client.post("/assessment/api/proxy", json={"answers": proxy_answers})
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    
    # Verify Phase 4 transition
    response = client.get("/assessment/api/state")
    assert response.json()["current_phase"] == 4
    
    # Get Phase 4 questions (Scenarios)
    response = client.get("/assessment/api/questions")
    p4_data = response.json()
    assert "scenarios" in p4_data
    scenarios = p4_data["scenarios"]
    assert len(scenarios) > 0
    
    # Submit Phase 4 answers
    scenario_answers = [{"scenario_id": sc["id"], "selected_tag": sc["options"][0]["label"]} for sc in scenarios]
    response = client.post("/assessment/api/scenarios", json={"answers": scenario_answers})
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    
    # Verify Phase 5 (Compile) transition
    response = client.get("/assessment/api/state")
    assert response.json()["current_phase"] == 5
    
    # Compile final results
    response = client.post("/assessment/api/compile")
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["status"] == "success"
    assert res_data["redirect"] == "/assessment/result"
    
    # Clean up test user
    teardown_test_user(user_id)

def test_grade_12_flow():
    user_id = 9998
    setup_test_user(user_id, "g12_test@carestance.com")
    
    # Set client cookie
    client.cookies.set("user_id", str(user_id))
    
    # Start assessment for Grade 12
    response = client.get("/assessment/start?class_level=12th", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers.get("location") == "/assessment"
    
    # Check state - starts at Phase 0 (Intake Chat)
    response = client.get("/assessment/api/state")
    state = response.json()
    assert state["student_type"] == "12th"
    assert state["current_phase"] == 0
    
    # Submit Intake Phase 0 turns
    # Turn 1: Name
    response = client.post("/assessment/api/intake", json={"message": "John Doe"})
    assert response.status_code == 200
    assert response.json()["is_complete"] is False
    
    # Turn 2: Grade
    response = client.post("/assessment/api/intake", json={"message": "12"})
    assert response.status_code == 200
    assert response.json()["is_complete"] is False
    
    # Turn 3: Stream
    response = client.post("/assessment/api/intake", json={"message": "Science"})
    assert response.status_code == 200
    assert response.json()["is_complete"] is True
    
    # Verify transition to Phase 1 (Swipe)
    response = client.get("/assessment/api/state")
    assert response.json()["current_phase"] == 1
    
    # Get Phase 1 questions (Swipe Cards)
    response = client.get("/assessment/api/questions")
    cards = response.json()["cards"]
    assert len(cards) == 10
    
    # Submit Phase 1 (Swipe)
    swipes = [{"card_id": c["id"], "direction": "right", "reaction_ms": 500, "dwell_ms": 600, "hesitation_ms": 0} for c in cards]
    response = client.post("/assessment/api/swipe", json={"swipes": swipes})
    assert response.status_code == 200
    
    # Verify transition to Phase 2 (Mentor Chat)
    response = client.get("/assessment/api/state")
    assert response.json()["current_phase"] == 2
    
    # Chat E2E Simulation
    chat_completed = False
    for i in range(6):
        response = client.post("/assessment/api/chat", json={"message": f"Grade 12 response turn {i}"})
        assert response.status_code == 200
        res_data = response.json()
        assert res_data["status"] == "success"
        if res_data.get("phase_complete"):
            chat_completed = True
            break
            
    assert chat_completed, "Grade 12 chat phase should successfully transition"
    
    # Verify transition to Phase 3 (Context/Proxies)
    response = client.get("/assessment/api/state")
    assert response.json()["current_phase"] == 3
    
    # Get Phase 3 questions
    response = client.get("/assessment/api/questions")
    proxies = response.json()["proxy_questions"]
    assert len(proxies) > 0
    
    # Submit Phase 3 answers
    proxy_answers = [{"question_id": pq["id"], "answer": pq["options"][0]["text"]} for pq in proxies]
    response = client.post("/assessment/api/proxy", json={"answers": proxy_answers})
    assert response.status_code == 200
    
    # Verify transition to Phase 4 (Scenarios)
    response = client.get("/assessment/api/state")
    assert response.json()["current_phase"] == 4
    
    # Get Phase 4 questions
    response = client.get("/assessment/api/questions")
    scenarios = response.json()["scenarios"]
    assert len(scenarios) > 0
    
    # Submit Phase 4 answers
    scenario_answers = [{"scenario_id": sc["id"], "selected_tag": sc["options"][0]["label"]} for sc in scenarios]
    response = client.post("/assessment/api/scenarios", json={"answers": scenario_answers})
    assert response.status_code == 200
    
    # Verify transition to Phase 5 (Compile)
    response = client.get("/assessment/api/state")
    assert response.json()["current_phase"] == 5
    
    # Compile Grade 12 results
    response = client.post("/assessment/api/compile")
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["status"] == "success"
    assert res_data["redirect"] == "/assessment/result"
    
    # Clean up test user
    teardown_test_user(user_id)

if __name__ == "__main__":
    print("Running Grade 10 assessment flow test...")
    test_grade_10_flow()
    print("Grade 10 flow test completed successfully!")
    
    print("\nRunning Grade 12 assessment flow test...")
    test_grade_12_flow()
    print("Grade 12 flow test completed successfully!")
