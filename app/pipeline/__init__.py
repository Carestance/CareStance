"""
pipeline/__init__.py — 
==========================

Flow:
START → Student vector (all = 0.5)
  ↓
Phase 1 → Basic info + interests → Vector update
  ↓
Phase 2 → Card swipe → Vector update (multipliers se) → Archetype classify
  ↓
Phase 3 → Weak feature MCQs → Vector update
  ↓
Phase 4 → Archetype + class → Task → JSON nodes
  ↓
KNN/Cosine → Top 3 Career Options
"""

import json
import os

from .vector_utils import (
    init_student_vector,
    update_vector_from_phase1,
    update_vector_from_swipe,
    update_vector_from_mcq,
    classify_archetype,
    get_phase4_task,
    build_phase4_json,
    match_careers_from_vector,
    get_weak_features,
    load_json,
)

__all__ = [
    "run_full_pipeline",
    "run_phase1",
    "run_phase2",
    "run_phase3",
    "run_phase4",
    "match_careers",
    "get_strength_weakness_analysis",
]


def run_phase1(phase1_input: dict) -> dict:
    vector = init_student_vector()
    vector = update_vector_from_phase1(vector, phase1_input)
    return {
        "student_profile": {
            "name": phase1_input.get("name", "Student"),
            "grade": phase1_input.get("grade", "10th"),
            "current_course": phase1_input.get("current_course", ""),
            "selected_interests": phase1_input.get("selected_interests", []),
            "family_income": phase1_input.get("family_income", ""),
            "mother_occupation": phase1_input.get("mother_occupation", ""),
            "father_occupation": phase1_input.get("father_occupation", ""),
        },
        "vector": vector,
        "phase2_liked_careers": [],
        "work_style_scores": {},
        "ability_scores": {},
        "interest_scores": {},
        "phase4_creativity_score": 0.5,
        "personality_archetype": "",
        "allowed_job_zones": [1, 2, 3, 4, 5],
    }


def run_phase2(student_profile: dict, swipe_data: list) -> dict:
    vector = student_profile.get("vector", init_student_vector())
    student_type = student_profile.get("student_profile", {}).get("grade", "10th")
    if "12" in str(student_type):
        student_type = "12th"
    else:
        student_type = "10th"

    vector = update_vector_from_swipe(vector, swipe_data, student_type)

    archetype = classify_archetype(vector)
    student_profile["vector"] = vector
    student_profile["personality_archetype"] = archetype
    student_profile["phase2_liked_careers"] = [
        s.get("card_id") for s in swipe_data if s.get("direction") == "right"
    ]
    return student_profile


def run_phase3(student_profile: dict, mcq_answers: list) -> dict:
    vector = student_profile.get("vector", init_student_vector())
    vector = update_vector_from_mcq(vector, mcq_answers)
    student_profile["vector"] = vector
    return student_profile


def run_phase4(student_profile: dict, phase4_data: dict = None) -> dict:
    vector = student_profile.get("vector", init_student_vector())
    archetype = student_profile.get("personality_archetype", "DYNAMIC GENERALIST")
    student_type = student_profile.get("student_profile", {}).get("grade", "10th")

    task = get_phase4_task(archetype, student_type)
    phase4_json = build_phase4_json(task, vector)

    student_profile["phase4_task"] = task
    student_profile["phase4_json"] = phase4_json
    student_profile["phase4_creativity_score"] = 0.7  # Default
    return student_profile


def match_careers(student_profile: dict, top_n: int = 10) -> list:
    vector = student_profile.get("vector", init_student_vector())
    return match_careers_from_vector(vector, top_n=top_n)


def get_strength_weakness_analysis(student_profile: dict) -> dict:
    vector = student_profile.get("vector", {})
    archetype = student_profile.get("personality_archetype", "DYNAMIC GENERALIST")

    # Top features = strengths
    it_ws_features = {k: v for k, v in vector.items()
                      if k.startswith("IT_") or k.startswith("WS_")}

    sorted_features = sorted(it_ws_features.items(), key=lambda x: x[1], reverse=True)

    readable = {
        "IT_Investigative": "Research & Investigation",
        "IT_Social": "Social Intelligence",
        "IT_Artistic": "Creative Expression",
        "IT_Enterprising": "Entrepreneurial Spirit",
        "IT_Conventional": "Process & Systems",
        "IT_Realistic": "Hands-on Practical Skills",
        "WS_Leadership Orientation": "Leadership",
        "WS_Innovation": "Creative Thinking",
        "WS_Intellectual Curiosity": "Analytical Curiosity",
        "WS_Perseverance": "Perseverance",
        "WS_Attention to Detail": "Attention to Detail",
        "WS_Achievement Orientation": "Achievement Drive",
        "WS_Stress Tolerance": "Stress Management",
        "WS_Social Orientation": "People Skills",
    }

    strengths = [readable.get(f, f) for f, _ in sorted_features[:4] if f in readable]
    weaknesses = [readable.get(f, f) for f, _ in sorted_features[-3:] if f in readable]

    # Dominant RIASEC
    riasec = {k: v for k, v in vector.items() if k.startswith("IT_")}
    dominant = max(riasec, key=riasec.get) if riasec else "IT_Investigative"
    dominant_label = dominant.replace("IT_", "")

    return {
        "strengths": strengths,
        "weaknesses": weaknesses,
        "dominant_riasec": dominant_label,
        "personality_archetype": archetype,
        "creativity_score": student_profile.get("phase4_creativity_score", 0.5),
        "family_background_score": 0.5,
    }


def run_full_pipeline(
    phase1_input: dict,
    phase2_swipes: list,
    phase3_responses: list,
    phase4_data: dict = None,
    top_n: int = 3,
) -> dict:
    
    # Phase 1: Basic info → Vector initialize + update
    profile = run_phase1(phase1_input)

    # Phase 2: Card swipes → Vector update + Archetype
    profile = run_phase2(profile, phase2_swipes)

    # Phase 3: MCQ → Vector update
    profile = run_phase3(profile, phase3_responses)

    # Phase 4: Task assignment + JSON nodes
    profile = run_phase4(profile, phase4_data)

    # KNN/Cosine → Top 3 careers
    top_careers = match_careers(profile, top_n=top_n)

    # Dashboard analysis
    analysis = get_strength_weakness_analysis(profile)
    best_match = top_careers[0]["match_percent"] if top_careers else 0

    return {
        "student_profile": profile,
        "top_careers": top_careers,
        "phase4_json": profile.get("phase4_json", {}),
        "dashboard": {
            "career_match_score": best_match,
            **analysis,
        },
    }