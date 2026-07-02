"""
phase2.py — Interest Discovery (Card Swiping) Pipeline
--------------------------------------------------------
Handles Phase 2 of the flowchart:
Career Interest Cards → Swipe Right (Like) / Swipe Left (Dislike) → Preference Profile

What it does:
1. Takes the student’s swipe data (liked/disliked career cards)
2. Refines the RIASEC scores based on liked careers (on top of Phase 1)
3. Generates the first reading of Work Style scores
4. Returns the updated student profile
"""

from __future__ import annotations

# ─── Career Card → RIASEC + Work Style Mapping ───────────────────────────────

CAREER_CARD_PROFILES: dict[str, dict] = {
    "Software Engineer": {
        "interest": {
            "IT_Investigative": 0.85, "IT_Realistic": 0.75,
            "IT_Conventional": 0.50, "IT_Enterprising": 0.30,
            "IT_Artistic": 0.25, "IT_Social": 0.15,
        },
        "work_style": {
            "WS_Attention to Detail": 0.9, "WS_Intellectual Curiosity": 0.85,
            "WS_Perseverance": 0.8, "WS_Adaptability": 0.7,
            "WS_Cooperation": 0.6, "WS_Leadership Orientation": 0.4,
        },
    },
    "Doctor": {
        "interest": {
            "IT_Social": 0.9, "IT_Investigative": 0.85,
            "IT_Realistic": 0.5, "IT_Conventional": 0.45,
            "IT_Enterprising": 0.3, "IT_Artistic": 0.2,
        },
        "work_style": {
            "WS_Empathy": 0.95, "WS_Stress Tolerance": 0.9,
            "WS_Attention to Detail": 0.9, "WS_Dependability": 0.85,
            "WS_Integrity": 0.85, "WS_Self-Control": 0.8,
        },
    },
    "Entrepreneur": {
        "interest": {
            "IT_Enterprising": 0.95, "IT_Social": 0.65,
            "IT_Investigative": 0.55, "IT_Conventional": 0.4,
            "IT_Artistic": 0.35, "IT_Realistic": 0.3,
        },
        "work_style": {
            "WS_Initiative": 0.95, "WS_Achievement Orientation": 0.9,
            "WS_Tolerance for Ambiguity": 0.85, "WS_Innovation": 0.85,
            "WS_Self-Confidence": 0.85, "WS_Leadership Orientation": 0.9,
        },
    },
    "Graphic Designer": {
        "interest": {
            "IT_Artistic": 0.95, "IT_Investigative": 0.45,
            "IT_Enterprising": 0.4, "IT_Social": 0.4,
            "IT_Realistic": 0.3, "IT_Conventional": 0.3,
        },
        "work_style": {
            "WS_Innovation": 0.9, "WS_Attention to Detail": 0.8,
            "WS_Adaptability": 0.75, "WS_Intellectual Curiosity": 0.7,
            "WS_Achievement Orientation": 0.65, "WS_Cooperation": 0.55,
        },
    },
    "Data Scientist": {
        "interest": {
            "IT_Investigative": 0.9, "IT_Conventional": 0.65,
            "IT_Realistic": 0.6, "IT_Enterprising": 0.35,
            "IT_Artistic": 0.25, "IT_Social": 0.2,
        },
        "work_style": {
            "WS_Intellectual Curiosity": 0.9, "WS_Attention to Detail": 0.9,
            "WS_Perseverance": 0.8, "WS_Adaptability": 0.75,
            "WS_Innovation": 0.7, "WS_Achievement Orientation": 0.7,
        },
    },
    "Teacher": {
        "interest": {
            "IT_Social": 0.95, "IT_Conventional": 0.6,
            "IT_Artistic": 0.5, "IT_Enterprising": 0.45,
            "IT_Investigative": 0.55, "IT_Realistic": 0.2,
        },
        "work_style": {
            "WS_Empathy": 0.9, "WS_Cooperation": 0.9,
            "WS_Dependability": 0.85, "WS_Perseverance": 0.8,
            "WS_Self-Control": 0.75, "WS_Sincerity": 0.8,
        },
    },
    "Army Officer": {
        "interest": {
            "IT_Realistic": 0.9, "IT_Enterprising": 0.75,
            "IT_Social": 0.6, "IT_Conventional": 0.5,
            "IT_Investigative": 0.35, "IT_Artistic": 0.1,
        },
        "work_style": {
            "WS_Leadership Orientation": 0.95, "WS_Dependability": 0.9,
            "WS_Self-Control": 0.9, "WS_Stress Tolerance": 0.85,
            "WS_Perseverance": 0.9, "WS_Integrity": 0.9,
        },
    },
    "Chartered Accountant": {
        "interest": {
            "IT_Conventional": 0.95, "IT_Enterprising": 0.7,
            "IT_Investigative": 0.6, "IT_Social": 0.4,
            "IT_Realistic": 0.2, "IT_Artistic": 0.1,
        },
        "work_style": {
            "WS_Attention to Detail": 0.95, "WS_Dependability": 0.9,
            "WS_Integrity": 0.9, "WS_Cautiousness": 0.85,
            "WS_Achievement Orientation": 0.75, "WS_Perseverance": 0.8,
        },
    },
    "Journalist": {
        "interest": {
            "IT_Artistic": 0.8, "IT_Social": 0.75,
            "IT_Enterprising": 0.65, "IT_Investigative": 0.7,
            "IT_Conventional": 0.3, "IT_Realistic": 0.15,
        },
        "work_style": {
            "WS_Intellectual Curiosity": 0.9, "WS_Initiative": 0.85,
            "WS_Adaptability": 0.85, "WS_Stress Tolerance": 0.75,
            "WS_Achievement Orientation": 0.7, "WS_Innovation": 0.7,
        },
    },
    "Lawyer": {
        "interest": {
            "IT_Enterprising": 0.9, "IT_Social": 0.7,
            "IT_Investigative": 0.65, "IT_Conventional": 0.55,
            "IT_Artistic": 0.35, "IT_Realistic": 0.1,
        },
        "work_style": {
            "WS_Achievement Orientation": 0.9, "WS_Self-Confidence": 0.9,
            "WS_Intellectual Curiosity": 0.85, "WS_Stress Tolerance": 0.8,
            "WS_Perseverance": 0.85, "WS_Integrity": 0.8,
        },
    },
}


# ─── Phase 2 Main Function ────────────────────────────────────────────────────

def run_phase2(student_profile: dict, swipe_data: list[dict]) -> dict:
    liked_careers = [s["career"] for s in swipe_data if s.get("action") == "like"]
    disliked_careers = [s["career"] for s in swipe_data if s.get("action") == "dislike"]

    student_profile["phase2_liked_careers"] = liked_careers

    if not liked_careers:
        return student_profile

    # 1. Liked careers ke basis par RIASEC refine kia
    refined_interest = _average_scores_from_cards(liked_careers, "interest")
    
    # Phase 1 scores ke saath blend (60% Phase2, 40% Phase1)
    for key in refined_interest:
        old = student_profile["interest_scores"].get(key, 0.5)
        student_profile["interest_scores"][key] = round(
            0.6 * refined_interest[key] + 0.4 * old, 4
        )

    # 2. Work Style scores initialize from liked cards
    work_style_from_likes = _average_scores_from_cards(liked_careers, "work_style")
    student_profile["work_style_scores"].update(work_style_from_likes)

    # 3. Disliked careers ki work styles slightly penalized 
    if disliked_careers:
        disliked_ws = _average_scores_from_cards(disliked_careers, "work_style")
        for key, val in disliked_ws.items():
            current = student_profile["work_style_scores"].get(key, 0.5)
            penalty = round(min((val - 0.5) * 0.2, 0.1), 4)
            student_profile["work_style_scores"][key] = round(
                max(current - penalty, 0.0), 4
            )

    return student_profile

# ─── Helper Functions ─────────────────────────────────────────────────────────

def _average_scores_from_cards(career_names: list[str], score_type: str) -> dict:
    totals: dict[str, float] = {}
    counts: dict[str, int] = {}

    for career in career_names:
        card = CAREER_CARD_PROFILES.get(career)
        if not card:
            continue
        scores = card.get(score_type, {})
        for key, val in scores.items():
            totals[key] = totals.get(key, 0.0) + val
            counts[key] = counts.get(key, 0) + 1

    return {
        key: round(totals[key] / counts[key], 4)
        for key in totals
    }