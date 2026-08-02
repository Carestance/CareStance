"""
test_pipeline.py
-----------------
Tested pipeline with a single student data
Run: python test_pipeline.py

"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.pipeline import run_full_pipeline

# ─── Sample Student Data ──────────────────────────────────────────────────────

phase1_input = {
    "mobile": "9876543210",
    "name": "Rashi Aggarwal",
    "grade": "12th",
    "current_course": "Humanities",
    "selected_interests": ["Polity", "Science"],
    "mother_occupation": "Teacher",
    "father_occupation": "Engineer",
    "family_income": "5_10lpa",
}

phase2_swipes = [
    {"career": "Software Engineer", "action": "like"},
    {"career": "Data Scientist",    "action": "like"},
    {"career": "Graphic Designer",  "action": "like"},
    {"career": "Army Officer",      "action": "dislike"},
    {"career": "Chartered Accountant", "action": "dislike"},
]

phase3_responses = [
    {"scenario_id": "scenario_leadership", "selected_option": "A"},
    {"scenario_id": "scenario_stress",     "selected_option": "B"},
    {"scenario_id": "scenario_innovation", "selected_option": "A"},
    {"scenario_id": "scenario_integrity",  "selected_option": "A"},
    {"scenario_id": "scenario_perseverance", "selected_option": "B"},
]

phase4_data = {
    "objects_shown": ["microscope", "computer", "paintbrush", "chart",
                      "people", "tree", "robot", "heart", "satellite", "pen"],
    "relationships": [
        {"from": "microscope", "to": "computer",   "label": "research needs data"},
        {"from": "computer",   "to": "people",     "label": "tech serves humans"},
        {"from": "paintbrush", "to": "computer",   "label": "design needs tools"},
        {"from": "robot",      "to": "people",     "label": "AI helps society"},
        {"from": "satellite",  "to": "chart",      "label": "space data drives insights"},
        {"from": "tree",       "to": "heart",      "label": "nature heals"},
        {"from": "pen",        "to": "people",     "label": "writing connects"},
    ],
    "time_taken_seconds": 210,
    "total_objects": 10,
}

# ─── Run Pipeline ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("🚀 CARESTANCE PIPELINE TEST")
    print("=" * 60)

    result = run_full_pipeline(
        phase1_input=phase1_input,
        phase2_swipes=phase2_swipes,
        phase3_responses=phase3_responses,
        phase4_data=phase4_data,
        top_n=5,
    )

    # print(f"\n👤 Student: {result['student_profile']['name']}")
    print(f"\n👤 Student: {result['student_profile']['student_profile']['name']}")
    print(f"📊 Personality: {result['student_profile']['personality_archetype']}")
    print(f"🎨 Creativity Score: {result['student_profile']['phase4_creativity_score']:.2%}")

    print(f"\n📈 DASHBOARD")
    print(f"   Career Match Score: {result['dashboard']['career_match_score']}%")
    print(f"   Dominant RIASEC: {result['dashboard']['dominant_riasec']}")
    print(f"   Strengths: {', '.join(result['dashboard']['strengths'])}")
    print(f"   Growth Areas: {', '.join(result['dashboard']['weaknesses'])}")

    print(f"\n🏆 TOP CAREER MATCHES")
    for i, career in enumerate(result["top_careers"], 1):
        print(f"   {i}. {career['title']}")
        print(f"      Match: {career['match_percent']}% | Zone: {career['job_zone']} | Type: {career.get('riasec_type', 'N/A')}")
        if career.get('strength_areas'):
            print(f"      Strengths: {', '.join(career['strength_areas'])}")

    print("\n✅ Pipeline ran successfully!")