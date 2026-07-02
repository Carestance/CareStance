"""
phase4.py — Creativity & Relationship Mapping Pipeline
--------------------------------------------------------
Handles Phase 4 of the flowchart:
10–12 Objects → Drag & Drop → Create Relationships → Schematic Diagram → Creativity Score

What it does:
1. Processes the student’s drag-and-drop relationship mapping data
2. Calculates the creativity score
3. Estimates spatial/visual thinking ability
4. Feeds these scores into the ability vector
"""

from __future__ import annotations
import math

# ─── Creativity Scoring Weights ───────────────────────────────────────────────

# Number of relationships created (more = more creative thinking)
RELATIONSHIP_COUNT_WEIGHT = 0.35

# Number of unique/diverse connections (cross-domain = more creative)
DIVERSITY_WEIGHT = 0.35

# Balance between speed and deliberateness
THOUGHTFULNESS_WEIGHT = 0.30


# ─── Object Category Groups ───────────────────────────────────────────────────

OBJECT_CATEGORIES = {
    "science": ["microscope", "telescope", "beaker", "circuit", "atom"],
    "arts": ["paintbrush", "musical_note", "camera", "pen", "palette"],
    "business": ["chart", "handshake", "briefcase", "coin", "building"],
    "nature": ["tree", "water", "sun", "mountain", "seed"],
    "technology": ["computer", "robot", "satellite", "phone", "gear"],
    "social": ["people", "heart", "globe", "school", "hospital"],
}

# Reverse lookup: object → category
OBJECT_TO_CATEGORY: dict[str, str] = {
    obj: cat
    for cat, objects in OBJECT_CATEGORIES.items()
    for obj in objects
}


# ─── Phase 4 Main Function ────────────────────────────────────────────────────

def run_phase4(student_profile: dict, phase4_data: dict) -> dict:
    relationships = phase4_data.get("relationships", [])
    objects_shown = phase4_data.get("objects_shown", [])
    time_taken = phase4_data.get("time_taken_seconds", 180)
    total_objects = phase4_data.get("total_objects", 12)

    if not relationships or not objects_shown:
        student_profile["phase4_creativity_score"] = 0.5
        return student_profile

    # 1. Relationship count score
    rel_count = len(relationships)
    max_possible_rels = total_objects * (total_objects - 1) / 2  # nC2
    count_score = min(rel_count / max(max_possible_rels * 0.4, 1), 1.0)
    # 40% of max connections = full score (we don't want to reward mindless connecting)

    # 2. Diversity score (cross-category connections)
    diversity_score = _calculate_diversity_score(relationships)

    # 3. Thoughtfulness score (not too fast, not too slow)
    thoughtfulness_score = _calculate_thoughtfulness_score(
        time_taken, rel_count, total_objects
    )

    # 4. Overall creativity score
    creativity_score = round(
        RELATIONSHIP_COUNT_WEIGHT * count_score
        + DIVERSITY_WEIGHT * diversity_score
        + THOUGHTFULNESS_WEIGHT * thoughtfulness_score,
        4,
    )

    student_profile["phase4_creativity_score"] = creativity_score

    # 5. Ability scores updated based on creativity
    _update_ability_scores(student_profile, creativity_score, diversity_score)

    # 6. RIASEC hint: high creativity → Artistic/Investigative boost
    if creativity_score > 0.7:
        it_artistic = student_profile["interest_scores"].get("IT_Artistic", 0.5)
        student_profile["interest_scores"]["IT_Artistic"] = round(
            min(it_artistic + 0.05, 1.0), 4
        )
        it_inv = student_profile["interest_scores"].get("IT_Investigative", 0.5)
        student_profile["interest_scores"]["IT_Investigative"] = round(
            min(it_inv + 0.03, 1.0), 4
        )

    return student_profile


# ─── Helper Functions ─────────────────────────────────────────────────────────

def _calculate_diversity_score(relationships: list[dict]) -> float:
    if not relationships:
        return 0.0

    cross_category = 0
    same_category = 0

    for rel in relationships:
        from_cat = OBJECT_TO_CATEGORY.get(rel.get("from", ""))
        to_cat = OBJECT_TO_CATEGORY.get(rel.get("to", ""))

        if from_cat and to_cat:
            if from_cat != to_cat:
                cross_category += 1
            else:
                same_category += 1

    total_categorized = cross_category + same_category
    if total_categorized == 0:
        return 0.5  # neutral if we can't categorize

    return round(cross_category / total_categorized, 4)


def _calculate_thoughtfulness_score(
    time_taken: float, rel_count: int, total_objects: int
) -> float:
    if rel_count == 0:
        return 0.0

    time_per_rel = time_taken / rel_count

    # Gaussian curve centered at 25 seconds
    optimal_time = 25.0
    std_dev = 20.0
    score = math.exp(-((time_per_rel - optimal_time) ** 2) / (2 * std_dev ** 2))

    return round(score, 4)


def _update_ability_scores(
    student_profile: dict, creativity_score: float, diversity_score: float
) -> None:
    ability_updates = {
        "AB_Originality": creativity_score,
        "AB_Fluency of Ideas": round((creativity_score + diversity_score) / 2, 4),
        "AB_Visualization": round(diversity_score * 0.8 + 0.1, 4),
        "AB_Flexibility of Closure": round(creativity_score * 0.7 + 0.2, 4),
        "AB_Category Flexibility": round(diversity_score * 0.9, 4),
        "AB_Inductive Reasoning": round((creativity_score * 0.6 + 0.3), 4),
    }

    for ability, score in ability_updates.items():
        existing = student_profile["ability_scores"].get(ability)
        if existing is not None:
            # Blend with existing
            student_profile["ability_scores"][ability] = round(
                0.6 * score + 0.4 * existing, 4
            )
        else:
            student_profile["ability_scores"][ability] = round(score, 4)