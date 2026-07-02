import math
from typing import Dict, List, Tuple, Optional
import json
import os

# Base directory for data
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "assessment_data")

ARCHETYPES = [
    "ARC_001", "ARC_002", "ARC_003", 
    "ARC_004", "ARC_005", "ARC_006"
]

def load_json(filename: str) -> dict:
    try:
        with open(os.path.join(DATA_DIR, filename), 'r') as f:
            return json.load(f)
    except Exception:
        return {}

def get_archetype_label(arc_id: str) -> str:
    labels = {
        "ARC_001": "Focused Specialist",
        "ARC_002": "Quiet Explorer",
        "ARC_003": "Strategic Builder",
        "ARC_004": "Dynamic Generalist",
        "ARC_005": "Visionary Leader",
        "ARC_006": "Adaptive Explorer"
    }
    return labels.get(arc_id, arc_id)

def calculate_phase1_scores(
    selected_interests: List[str], 
    current_course: str, 
    salary_priority: str, 
    family_income: str, 
    parent_occupations: List[str]
) -> Dict[str, float]:
    """
    Phase 1: Information Collection
    Phase1Score(archetype) = 0.55 × InterestMatch + 0.20 × CourseMatch + 0.15 × SalaryMatch + 0.10 × ContextMatch
    Normalized to 0-100 scale.
    """
    scores = {arc: 0.0 for arc in ARCHETYPES}
    phase1_data = load_json("phase1_inputs.json")
    archetypes_data = load_json("archetypes.json")

    # For simplicity, if we don't have exact feature mapping in the new schema, 
    # we simulate the feature matches based on the requested formulas.
    
    # 1. InterestMatch (0-100)
    interest_scores = {arc: 0.0 for arc in ARCHETYPES}
    interest_map = phase1_data.get("interest_selection_mapping", {})
    arc_interest_weights = archetypes_data.get("archetype_interest_weights", {})
    
    for interest in selected_interests[:3]:
        # Simple heuristic: map interest features to archetype features
        features = interest_map.get(interest, {})
        for arc in ARCHETYPES:
            arc_features = arc_interest_weights.get(arc, {})
            # Sum up matching feature weights
            match_score = sum([features.get(f, 0) * arc_features.get(f, 0) for f in features])
            interest_scores[arc] += max(0, match_score) * 20 # Scale up

    # Normalize interest scores to 100
    max_int = max(interest_scores.values()) if interest_scores.values() else 1
    if max_int == 0: max_int = 1
    interest_scores = {arc: (val / max_int) * 100 for arc, val in interest_scores.items()}

    # 2. CourseMatch (0-100)
    course_scores = {arc: 0.0 for arc in ARCHETYPES}
    course_map = phase1_data.get("current_course_mapping", {})
    features = course_map.get(current_course, {})
    for arc in ARCHETYPES:
        arc_features = arc_interest_weights.get(arc, {})
        match_score = sum([features.get(f, 0) * arc_features.get(f, 0) for f in features])
        course_scores[arc] += max(0, match_score) * 20
    
    max_course = max(course_scores.values()) if course_scores.values() else 1
    if max_course == 0: max_course = 1
    course_scores = {arc: (val / max_course) * 100 for arc, val in course_scores.items()}

    # 3. SalaryMatch (0-100)
    salary_scores = {arc: 0.0 for arc in ARCHETYPES}
    salary_map = archetypes_data.get("salary_expectation_mapping", {})
    sal_weights = salary_map.get(salary_priority, {})
    for arc in ARCHETYPES:
        salary_scores[arc] = sal_weights.get(arc, 0) * 100 * 5 # scale

    # Normalize salary
    max_sal = max(salary_scores.values()) if salary_scores.values() else 1
    if max_sal == 0: max_sal = 1
    salary_scores = {arc: (val / max_sal) * 100 for arc, val in salary_scores.items()}

    # 4. ContextMatch (0-100) - Family income & Occupation
    context_scores = {arc: 50.0 for arc in ARCHETYPES} # baseline

    # Final Phase 1 Calculation
    for arc in ARCHETYPES:
        scores[arc] = (
            0.55 * interest_scores.get(arc, 0) +
            0.20 * course_scores.get(arc, 0) +
            0.15 * salary_scores.get(arc, 0) +
            0.10 * context_scores.get(arc, 50)
        )
    
    return scores

def calculate_phase2_scores(mcq_answers: List[dict]) -> Dict[str, float]:
    """
    Phase 2: Behavioral Archetype Assessment
    Phase2RawScore(archetype) = Number of questions where that archetype was selected
    Phase2Score(archetype) = (Archetype Raw Score ÷ Highest Raw Score Across Archetypes) × 100
    """
    raw_scores = {arc: 0 for arc in ARCHETYPES}
    
    for answer in mcq_answers:
        arc_id = answer.get("archetype_id")
        if arc_id in raw_scores:
            raw_scores[arc_id] += 1
            
    highest_raw = max(raw_scores.values()) if raw_scores.values() else 1
    if highest_raw == 0:
        highest_raw = 1
        
    scores = {arc: (raw_scores[arc] / highest_raw) * 100.0 for arc in ARCHETYPES}
    return scores

def calculate_effective_archetype(
    phase1_scores: Dict[str, float],
    phase2_scores: Dict[str, float],
    deep_dive_scores: Dict[str, float]
) -> Dict[str, float]:
    """
    EffectiveArchetypeScore = 0.20 × Phase1Score + 0.50 × Phase2Score + 0.30 × DeepDiveScore
    """
    effective_scores = {}
    for arc in ARCHETYPES:
        p1 = phase1_scores.get(arc, 0.0)
        p2 = phase2_scores.get(arc, 0.0)
        dd = deep_dive_scores.get(arc, 0.0)
        
        effective_scores[arc] = (0.20 * p1) + (0.50 * p2) + (0.30 * dd)
        
    return effective_scores

def classify_final_archetype(effective_scores: Dict[str, float]) -> Tuple[str, str, Optional[str]]:
    """
    Classification Rules:
    If the top archetype score is 70 or above and the difference between the top score and second-highest score is 8 or more:
        Assign a Primary Archetype.
    If the top archetype score is 70 or above but the difference from the second-highest score is less than 8:
        Assign a Hybrid Archetype using the top two archetypes.
    If the top archetype score is below 70:
        Assign an Exploratory Profile and avoid giving a fixed archetype label.
        
    Returns: (classification_type, primary_label, secondary_label)
    """
    sorted_scores = sorted(effective_scores.items(), key=lambda x: x[1], reverse=True)
    if not sorted_scores:
        return ("Exploratory Profile", "Exploratory Profile", None)
        
    top_arc, top_score = sorted_scores[0]
    second_arc, second_score = sorted_scores[1] if len(sorted_scores) > 1 else (None, 0)
    
    if top_score >= 70:
        if (top_score - second_score) >= 8:
            return ("Primary Archetype", get_archetype_label(top_arc), None)
        else:
            return ("Hybrid Archetype", f"{get_archetype_label(top_arc)} & {get_archetype_label(second_arc)}", None)
    else:
        return ("Exploratory Profile", "Exploratory Profile", None)

