"""
phase1.py — Student Information Collection Pipeline
-----------------------------------------------------
Mobile → Name → Grade → Course → Interests → Parents' Occupation → Income → Profile

What it does:
1. Validates the student's raw input
2. Converts interest selections into a RIASEC vector
3. Calculates the family background score
4. Returns a structured Student Profile dictionary used in subsequent phases
"""

from __future__ import annotations
from typing import Optional


# ─── RIASEC Interest Mapping ─────────────────────────────────────────────────
# RIASEC = Realistic, Investigative, Artistic, Social, Enterprising, Conventional

INTEREST_TO_RIASEC: dict[str, dict[str, float]] = {
    "AI": {
        "IT_Investigative": 0.9, "IT_Realistic": 0.6,
        "IT_Conventional": 0.4, "IT_Enterprising": 0.3,
        "IT_Artistic": 0.2, "IT_Social": 0.1,
    },
    "ML": {
        "IT_Investigative": 0.9, "IT_Realistic": 0.7,
        "IT_Conventional": 0.5, "IT_Enterprising": 0.3,
        "IT_Artistic": 0.1, "IT_Social": 0.1,
    },
    "Doctor": {
        "IT_Social": 0.9, "IT_Investigative": 0.8,
        "IT_Realistic": 0.5, "IT_Conventional": 0.4,
        "IT_Enterprising": 0.3, "IT_Artistic": 0.2,
    },
    "Navy": {
        "IT_Realistic": 0.9, "IT_Enterprising": 0.6,
        "IT_Social": 0.5, "IT_Conventional": 0.3,
        "IT_Investigative": 0.3, "IT_Artistic": 0.1,
    },
    "Business": {
        "IT_Enterprising": 0.9, "IT_Conventional": 0.7,
        "IT_Social": 0.5, "IT_Investigative": 0.4,
        "IT_Realistic": 0.2, "IT_Artistic": 0.2,
    },
    "Science": {
        "IT_Investigative": 0.9, "IT_Realistic": 0.7,
        "IT_Conventional": 0.5, "IT_Artistic": 0.3,
        "IT_Social": 0.2, "IT_Enterprising": 0.1,
    },
    "Arts": {
        "IT_Artistic": 0.9, "IT_Social": 0.6,
        "IT_Investigative": 0.4, "IT_Enterprising": 0.3,
        "IT_Realistic": 0.2, "IT_Conventional": 0.2,
    },
    "Commerce": {
        "IT_Conventional": 0.9, "IT_Enterprising": 0.8,
        "IT_Social": 0.5, "IT_Investigative": 0.3,
        "IT_Realistic": 0.2, "IT_Artistic": 0.1,
    },
    "Engineering": {
        "IT_Realistic": 0.9, "IT_Investigative": 0.8,
        "IT_Conventional": 0.5, "IT_Enterprising": 0.3,
        "IT_Artistic": 0.2, "IT_Social": 0.2,
    },
    "Law": {
        "IT_Enterprising": 0.9, "IT_Social": 0.7,
        "IT_Investigative": 0.6, "IT_Conventional": 0.5,
        "IT_Artistic": 0.3, "IT_Realistic": 0.1,
    },
}

# Family Income → Job Zone filter
# Job Zone 1-5: 1=low skill, 5=highest education required
INCOME_TO_JOB_ZONE_FILTER: dict[str, list[int]] = {
    "below_2lpa":   [1, 2],
    "2_5lpa":       [1, 2, 3],
    "5_10lpa":      [2, 3, 4],
    "10_20lpa":     [3, 4, 5],
    "above_20lpa":  [3, 4, 5],
}


# ─── Phase 1 Main Function ────────────────────────────────────────────────────

def run_phase1(raw_input: dict) -> dict:
    _validate_phase1_input(raw_input)

    # 1. RIASEC scores calculate (Average for multiple interests)
    riasec_scores = _compute_riasec_scores(raw_input["selected_interests"])

    # 2. Family background score (career accessibility)
    family_score = _compute_family_score(
        raw_input["mother_occupation"],
        raw_input["father_occupation"],
        raw_input["family_income"],
    )

    # 3. Job Zone filter (Based on income)
    allowed_job_zones = INCOME_TO_JOB_ZONE_FILTER.get(
        raw_input["family_income"], [1, 2, 3, 4, 5]
    )

    profile = {
        # Basic info
        "mobile": raw_input["mobile"],
        "name": raw_input["name"],
        "grade": raw_input["grade"],
        "current_course": raw_input["current_course"],
        "selected_interests": raw_input["selected_interests"],

        # Family context
        "mother_occupation": raw_input["mother_occupation"],
        "father_occupation": raw_input["father_occupation"],
        "family_income": raw_input["family_income"],
        "family_background_score": family_score,
        "allowed_job_zones": allowed_job_zones,

        # RIASEC vector (Phase 2, 3, 4 and Matcher will use it)
        "interest_scores": riasec_scores,

        # Ye phase 2, 3, 4 fill 
        "work_style_scores": {},
        "ability_scores": {},
        "phase2_liked_careers": [],
        "phase3_behavior_scores": {},
        "phase4_creativity_score": 0.0,
    }

    return profile


# ─── Helper Functions ─────────────────────────────────────────────────────────

def _validate_phase1_input(data: dict) -> None:
    required = ["mobile", "name", "grade", "current_course",
                "selected_interests", "mother_occupation",
                "father_occupation", "family_income"]
    for field in required:
        if field not in data or not data[field]:
            raise ValueError(f"Phase 1: Missing required field: '{field}'")

    if not isinstance(data["selected_interests"], list) or len(data["selected_interests"]) == 0:
        raise ValueError("Phase 1: 'selected_interests' must be a non-empty list")


def _compute_riasec_scores(selected_interests: list[str]) -> dict:
    riasec_keys = [
        "IT_Realistic", "IT_Investigative", "IT_Artistic",
        "IT_Social", "IT_Enterprising", "IT_Conventional",
    ]
    total = {k: 0.0 for k in riasec_keys}
    count = 0

    for interest in selected_interests:
        mapping = INTEREST_TO_RIASEC.get(interest)
        if mapping:
            for k in riasec_keys:
                total[k] += mapping.get(k, 0.5)
            count += 1

    if count == 0:
        # Koi match nahi mila toh neutral scores
        return {k: 0.5 for k in riasec_keys}

    return {k: round(total[k] / count, 4) for k in riasec_keys}


def _compute_family_score(
    mother_occ: str,
    father_occ: str,
    income: str
) -> float:
    income_score_map = {
        "below_2lpa":  0.1,
        "2_5lpa":      0.3,
        "5_10lpa":     0.5,
        "10_20lpa":    0.7,
        "above_20lpa": 0.9,
    }
    income_score = income_score_map.get(income, 0.5)

    # Professional parents → slightly higher score
    professional_keywords = [
        "doctor", "engineer", "lawyer", "professor", "teacher",
        "manager", "officer", "scientist", "architect",
    ]
    parent_bonus = 0.0
    for occ in [mother_occ.lower(), father_occ.lower()]:
        if any(kw in occ for kw in professional_keywords):
            parent_bonus += 0.05

    return round(min(income_score + parent_bonus, 1.0), 4)