"""
matcher.py — Career Recommendation Engine
-------------------------------------------
Ye file ek student profile leti hai (Phase 1-4 ka combined output)
aur occupation matrix se TOP career matches dhundti hai.

Vector Matching kaise kaam karta hai:
1. Student ka ek feature vector banao (interests + work styles + abilities)
2. Occupation matrix ki har row bhi ek vector hai
3. Cosine similarity se har occupation ka score nikalo
4. Top N results return karo with match percentage
"""

from __future__ import annotations

import pandas as pd
import numpy as np

from .vector_utils import (
    load_occupation_matrix,
    build_student_vector,
    weighted_similarity,
    ABILITY_COLS,
    WORK_STYLE_COLS,
    INTEREST_COLS,
    ALL_FEATURE_COLS,
)


# ─── Configuration ────────────────────────────────────────────────────────────

TOP_N_RESULTS = 10       
MIN_MATCH_THRESHOLD = 0.45  


# ─── Main Matching Function ───────────────────────────────────────────────────

def match_careers(student_profile: dict, top_n: int = TOP_N_RESULTS) -> list[dict]:
    """
    Student profile leke top career matches return karta hai.

    Args:
        student_profile: Combined output of Phase 1, 2, 3, 4.
            Must have: interest_scores, work_style_scores, ability_scores,
                       allowed_job_zones, phase2_liked_careers,
                       phase4_creativity_score, family_background_score

        top_n: Kitne top results chahiye

    Returns:
        List of dicts, sorted by match_score descending:
        [
            {
                "title": "Software Developer",
                "onet_code": "15-1252.00",
                "description": "...",
                "match_score": 0.87,       # 0-1
                "match_percent": 87,        # for UI display
                "job_zone": 4,
                "strength_areas": ["Analytical", "Technical"],
                "riasec_type": "Investigative-Realistic",
            },
            ...
        ]
    """
    df = load_occupation_matrix()

    # 1. Job Zone filter (family income ke basis par)
    allowed_zones = student_profile.get("allowed_job_zones", [1, 2, 3, 4, 5])
    if allowed_zones and "Job Zone" in df.columns:
        df = df[df["Job Zone"].isin(allowed_zones)].copy()

    if df.empty:
        return []

    # 2. Student ke scores ko ek dict mein combine kia
    all_student_scores = {
        **student_profile.get("interest_scores", {}),
        **student_profile.get("work_style_scores", {}),
        **student_profile.get("ability_scores", {}),
    }

    # 3. Har occupation ke liye similarity calculate ki
    scores = []
    for _, row in df.iterrows():
        sim = weighted_similarity(all_student_scores, row)

        # Boost: agar student ne Phase 2 mein ye career like kiya tha
        liked = student_profile.get("phase2_liked_careers", [])
        if row.get("Title", "") in liked:
            sim = min(sim + 0.05, 1.0)

        # Creativity boost: high creativity → more weight to Artistic/Investigative careers
        creativity_score = student_profile.get("phase4_creativity_score", 0.5)
        if creativity_score > 0.7:
            artistic_val = row.get("IT_Artistic", 0)
            investigative_val = row.get("IT_Investigative", 0)
            if artistic_val > 0.6 or investigative_val > 0.7:
                sim = min(sim + creativity_score * 0.03, 1.0)

        scores.append({
            "title": row.get("Title", "Unknown"),
            "onet_code": row.get("O*NET-SOC Code", ""),
            "description": row.get("Description", ""),
            "match_score": round(sim, 4),
            "job_zone": int(row.get("Job Zone", 0)) if pd.notna(row.get("Job Zone")) else 0,
            "it_realistic": row.get("IT_Realistic", 0),
            "it_investigative": row.get("IT_Investigative", 0),
            "it_artistic": row.get("IT_Artistic", 0),
            "it_social": row.get("IT_Social", 0),
            "it_enterprising": row.get("IT_Enterprising", 0),
            "it_conventional": row.get("IT_Conventional", 0),
        })

    # 4. Sort by match score
    scores.sort(key=lambda x: x["match_score"], reverse=True)

    # 5. Filter minimum threshold
    scores = [s for s in scores if s["match_score"] >= MIN_MATCH_THRESHOLD]

    # 6. Top N leke format karo
    results = []
    for s in scores[:top_n]:
        results.append({
            "title": s["title"],
            "onet_code": s["onet_code"],
            "description": s["description"][:300] + "..." if len(s.get("description", "")) > 300 else s.get("description", ""),
            "match_score": s["match_score"],
            "match_percent": int(round(s["match_score"] * 100)),
            "job_zone": s["job_zone"],
            "riasec_type": _get_riasec_label(s),
            "strength_areas": _get_strength_areas(student_profile, s),
        })

    return results


# ─── Analysis Functions ───────────────────────────────────────────────────────

def get_strength_weakness_analysis(student_profile: dict) -> dict:
    """
    Dashboard ke liye student ki strengths aur weaknesses nikalo.
    
    Returns:
        {
            "strengths": ["Strong Leadership", "High Creativity", ...],
            "weaknesses": ["Physical Stamina", "Manual Dexterity", ...],
            "dominant_riasec": "Investigative",
            "personality_archetype": "The Analyst",
        }
    """
    ws = student_profile.get("work_style_scores", {})
    ab = student_profile.get("ability_scores", {})
    interests = student_profile.get("interest_scores", {})

    all_scores = {**ws, **ab, **interests}

    # Top 3 strengths (highest scoring traits with readable names)
    readable = {
        "WS_Leadership Orientation": "Leadership",
        "WS_Innovation": "Creative Thinking",
        "WS_Empathy": "Empathy & People Skills",
        "WS_Intellectual Curiosity": "Analytical Curiosity",
        "WS_Perseverance": "Perseverance",
        "WS_Attention to Detail": "Attention to Detail",
        "WS_Stress Tolerance": "Stress Management",
        "WS_Achievement Orientation": "Achievement Drive",
        "AB_Mathematical Reasoning": "Mathematical Aptitude",
        "AB_Originality": "Original Thinking",
        "AB_Written Expression": "Communication Skills",
        "AB_Oral Expression": "Verbal Communication",
        "IT_Social": "Social Intelligence",
        "IT_Artistic": "Creative Expression",
        "IT_Investigative": "Research & Investigation",
        "IT_Enterprising": "Entrepreneurial Spirit",
        "IT_Conventional": "Process & Systems",
        "IT_Realistic": "Hands-on Practical Skills",
    }

    scored_traits = [
        (readable[k], v)
        for k, v in all_scores.items()
        if k in readable
    ]
    scored_traits.sort(key=lambda x: x[1], reverse=True)

    strengths = [name for name, _ in scored_traits[:4]]
    weaknesses = [name for name, _ in scored_traits[-3:]]

    # Dominant RIASEC
    riasec_scores = {
        "Realistic": interests.get("IT_Realistic", 0),
        "Investigative": interests.get("IT_Investigative", 0),
        "Artistic": interests.get("IT_Artistic", 0),
        "Social": interests.get("IT_Social", 0),
        "Enterprising": interests.get("IT_Enterprising", 0),
        "Conventional": interests.get("IT_Conventional", 0),
    }
    dominant_riasec = max(riasec_scores, key=riasec_scores.get)

    return {
        "strengths": strengths,
        "weaknesses": weaknesses,
        "dominant_riasec": dominant_riasec,
        "personality_archetype": student_profile.get("personality_archetype", "Unknown"),
        "creativity_score": student_profile.get("phase4_creativity_score", 0.5),
        "family_background_score": student_profile.get("family_background_score", 0.5),
    }


# ─── Helper Functions ─────────────────────────────────────────────────────────

def _get_riasec_label(occupation_row: dict) -> str:
    """Occupation ke top 2 RIASEC types nikalo."""
    riasec = {
        "Realistic": occupation_row.get("it_realistic", 0),
        "Investigative": occupation_row.get("it_investigative", 0),
        "Artistic": occupation_row.get("it_artistic", 0),
        "Social": occupation_row.get("it_social", 0),
        "Enterprising": occupation_row.get("it_enterprising", 0),
        "Conventional": occupation_row.get("it_conventional", 0),
    }
    sorted_riasec = sorted(riasec, key=riasec.get, reverse=True)
    return f"{sorted_riasec[0]}-{sorted_riasec[1]}"


def _get_strength_areas(student_profile: dict, occupation_row: dict) -> list[str]:
    """
    Student kahan strong hai is specific career ke liye.
    """
    areas = []
    interests = student_profile.get("interest_scores", {})

    if occupation_row.get("it_investigative", 0) > 0.6 and interests.get("IT_Investigative", 0) > 0.6:
        areas.append("Research & Analysis")
    if occupation_row.get("it_social", 0) > 0.6 and interests.get("IT_Social", 0) > 0.6:
        areas.append("People & Communication")
    if occupation_row.get("it_artistic", 0) > 0.6 and interests.get("IT_Artistic", 0) > 0.6:
        areas.append("Creative & Artistic")
    if occupation_row.get("it_enterprising", 0) > 0.6 and interests.get("IT_Enterprising", 0) > 0.6:
        areas.append("Leadership & Business")
    if occupation_row.get("it_conventional", 0) > 0.6 and interests.get("IT_Conventional", 0) > 0.6:
        areas.append("Process & Systems")
    if occupation_row.get("it_realistic", 0) > 0.6 and interests.get("IT_Realistic", 0) > 0.6:
        areas.append("Technical & Hands-on")

    return areas if areas else ["General Aptitude"]