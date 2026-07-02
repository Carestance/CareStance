"""
vector_utils.py 
===================================================
Flow:
1. The student vector starts (all features = 0.5)
2. Phase 1: Vector updated using basic info + interests
3. Phase 2: Vector updated using card swipes (using multipliers)
4. Phase 3: MCQs for weak features → vector update
5. Phase 4: Archetype + task → JSON nodes
6. Final: Top 3 careers using Cosine/KNN
"""

import numpy as np
import pandas as pd
import json
import os
from typing import Dict, List

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "assessment_data")
MATRIX_PATH = os.path.join(DATA_DIR, "occupation_feature_matrix_1.csv")

# ─── All feature columns (from occupation matrix) ────────────────────────────

IT_COLS = [
    "IT_Artistic", "IT_Conventional", "IT_Enterprising",
    "IT_Investigative", "IT_Realistic", "IT_Social",
]

WS_COLS = [
    "WS_Intellectual Curiosity", "WS_Initiative", "WS_Leadership Orientation",
    "WS_Perseverance", "WS_Attention to Detail", "WS_Adaptability",
    "WS_Innovation", "WS_Achievement Orientation", "WS_Cooperation",
    "WS_Social Orientation", "WS_Stress Tolerance", "WS_Self-Control",
    "WS_Self-Confidence", "WS_Cautiousness", "WS_Tolerance for Ambiguity"
]

AB_COLS = [
    "AB_Deductive Reasoning", "AB_Mathematical Reasoning", "AB_Problem Sensitivity",
    "AB_Information Ordering", "AB_Category Flexibility", "AB_Originality",
    "AB_Visualization", "AB_Memorization", "AB_Written Comprehension",
    "AB_Perceptual Speed", "AB_Selective Attention", "AB_Fluency of Ideas",
    "AB_Oral Expression", "AB_Inductive Reasoning", "AB_Number Facility",
    "AB_Oral Comprehension", "AB_Written Expression"
]

ALL_FEATURES = IT_COLS + WS_COLS + AB_COLS


# ─── Load Data Files ──────────────────────────────────────────────────────────

def load_json(filename: str) -> dict:
    path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_cards(student_type: str) -> List[dict]:
    filename = "cards_10th.json" if student_type == "10th" else "cards_12th.json"
    path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_occupation_matrix() -> pd.DataFrame:
    df = pd.read_csv(MATRIX_PATH)
    return df


# ─── Student Vector ───────────────────────────────────────────────────────────

def init_student_vector() -> Dict[str, float]:
    return {feature: 0.5 for feature in ALL_FEATURES}


def update_vector_from_phase1(vector: Dict, phase1_input: Dict) -> Dict:
    """
    Phase 1: Basic info + interests se vector updated.
    phase_1_inputs.json use karta hai.
    """
    phase1_data = load_json("phase1_inputs.json")
    if not phase1_data:
        return vector

    # Current course mapping
    course = phase1_input.get("current_course", "")
    course_map = phase1_data.get("current_course_mapping", {})
    for key, val in course_map.items():
        if key.lower() in course.lower():
            for feature, weight in val.items():
                if feature in vector:
                    vector[feature] = min(1.0, max(-1.0, vector[feature] + weight * 0.3))
            break

    # Interest selection mapping
    interests = phase1_input.get("selected_interests", [])
    interest_map = phase1_data.get("interest_selection_mapping", {})
    for interest in interests:
        mapping = interest_map.get(interest, {})
        for feature, weight in mapping.items():
            if feature in vector:
                vector[feature] = min(1.0, max(-1.0, vector[feature] + weight * 0.2))

    # Family income mapping
    income = phase1_input.get("family_income", "")
    income_map = phase1_data.get("family_income_mapping", {})
    for income_key, vals in income_map.items():
        if any(x in income for x in ["3L", "3l", "low", "Low"]) and "Low" in income_key:
            for feature, weight in vals.items():
                if feature in vector:
                    vector[feature] = min(1.0, max(-1.0, vector[feature] + weight * 0.1))
            break

    # Parent occupation mapping
    occupation_map = phase1_data.get("occupation_category_mapping", {})
    for parent_occ in [
        phase1_input.get("mother_occupation", ""),
        phase1_input.get("father_occupation", "")
    ]:
        for occ_key, vals in occupation_map.items():
            if any(word in parent_occ.lower() for word in occ_key.lower().split()[:2]):
                for feature, weight in vals.items():
                    if feature in vector:
                        vector[feature] = min(1.0, max(-1.0, vector[feature] + weight * 0.1))
                break

    return vector


def update_vector_from_swipe(vector: Dict, swipes: List[dict], student_type: str) -> Dict:
    cards = load_cards(student_type)
    card_map = {card["id"]: card for card in cards}

    for swipe in swipes:
        card_id = swipe.get("card_id")
        direction = swipe.get("direction", "left")
        dwell_ms = swipe.get("dwell_ms", 1000)
        reaction_ms = swipe.get("reaction_ms", 500)

        card = card_map.get(card_id)
        if not card:
            continue

        multipliers = card.get("multipliers", {})

        # Dwell time weight — jitna zyada socha, utna zyada impact
        time_weight = min(1.0, dwell_ms / 3000.0)

        # Like = positive multipliers use karo
        # Dislike = negative multipliers use karo (dampened by 0.5)
        direction_sign = 1.0 if direction == "right" else -0.5

        for feature, mult in multipliers.items():
            if feature in vector:
                delta = mult * direction_sign * time_weight * 0.15
                vector[feature] = min(1.0, max(-1.0, vector[feature] + delta))

    return vector


def get_weak_features(vector: Dict, top_n: int = 6) -> List[str]:
    # Features jo neutral (around 0.5) hain — inke baare mein most uncertain hain
    uncertainties = {f: abs(v - 0.5) for f, v in vector.items()
                     if f in IT_COLS + WS_COLS}
    # Sabse low certainty wale = most uncertain
    sorted_features = sorted(uncertainties.items(), key=lambda x: x[1])
    return [f for f, _ in sorted_features[:top_n]]


def select_top_questions(vector: Dict, all_questions: List[dict], limit: int = 8) -> List[dict]:
    """
    Selects questions where the proxy_target matches one of the student's weak features.
    """
    weak_features = get_weak_features(vector, top_n=15) # Get a broader pool
    
    # Priority: Questions matching weak features
    priority_qs = [q for q in all_questions if q.get("proxy_target") in weak_features]
    
    # If not enough, fill with random others
    if len(priority_qs) < limit:
        remaining = [q for q in all_questions if q not in priority_qs]
        import random
        random.shuffle(remaining)
        priority_qs.extend(remaining[:(limit - len(priority_qs))])
        
    import random
    random.shuffle(priority_qs)
    return priority_qs[:limit]


def update_vector_from_mcq(vector: Dict, mcq_answers: List[dict]) -> Dict:
    """
    Phase 3: MCQ answers se vector updated.
    Proxy questions mein proxy_target aur multiplier hota hai.
    """
    phase3_data = load_json("phase3_mcqs.json")
    if not phase3_data:
        return vector

    # phase3_mcqs.json is a list
    if isinstance(phase3_data, list):
        q_map = {q["id"]: q for q in phase3_data}
    else:
        q_map = {}

    for answer in mcq_answers:
        qid = answer.get("question_id") or answer.get("id")
        selected_text = answer.get("answer") or answer.get("selected_text", "")
        multiplier = answer.get("multiplier")

        q = q_map.get(qid)
        if not q:
            continue

        proxy_target = q.get("proxy_target", "")

        if multiplier is None:
            for opt in q.get("options", []):
                if opt.get("text") == selected_text:
                    multiplier = opt.get("multiplier", 0.5)
                    break

        if multiplier is None:
            multiplier = 0.5

        # Vector update: proxy_target feature ko multiplier se update kia
        if proxy_target and proxy_target in vector:
            # Normalize multiplier (0-1) to vector space (-1 to 1)
            normalized = (multiplier * 2) - 1  # 0→-1, 0.5→0, 1→+1
            delta = normalized * 0.25  # Moderate impact
            vector[proxy_target] = min(1.0, max(-1.0, vector[proxy_target] + delta))

    return vector

def classify_archetype(vector: Dict) -> str:
    archetypes_data = load_json("archetypes.json")
    if not archetypes_data:
        return "DYNAMIC GENERALIST"

    archetypes = archetypes_data.get("archetypes", [])

    best_archetype = "DYNAMIC GENERALIST"
    best_score = -1

    for archetype in archetypes:
        ranges = archetype.get("feature_vector_ranges", {})
        score = 0
        total = len(ranges)

        for feature, (low, high) in ranges.items():
            val = vector.get(feature, 0.5)
            if low <= val <= high:
                score += 1

        match_ratio = score / total if total > 0 else 0
        if match_ratio > best_score:
            best_score = match_ratio
            best_archetype = archetype.get("archetype_name", "DYNAMIC GENERALIST")

    return best_archetype


def get_phase4_task(archetype: str, student_type: str) -> dict:
    tasks_data = load_json("phase4_tasks.json")
    if not tasks_data:
        return {}

    # Find nature from Archetype
    archetype_to_nature = {
        "FOCUSED SPECIALIST": "Introvert",
        "QUIET EXPLORER": "Introvert",
        "STRATEGIC BUILDER": "Ambivert",
        "DYNAMIC GENERALIST": "Ambivert",
        "VISIONARY LEADER": "Extrovert",
        "ADAPTIVE EXPLORER": "Extrovert",
    }

    nature = archetype_to_nature.get(archetype, "Ambivert")
    grade = "10th" if student_type == "10th" else "12th"

    # Filter tasks by class and nature
    matching = [
        t for t in tasks_data
        if t.get("class") == grade and t.get("nature") == nature
    ]

    # Goal-directed tasks prefer karo
    goal_tasks = [t for t in matching if t.get("goal_status") == "Goal"]
    task = goal_tasks[0] if goal_tasks else (matching[0] if matching else {})

    return task


def build_phase4_json(task: dict, vector: Dict) -> dict:
    if not task:
        return {"nodes": [], "connections": []}

    tools = task.get("tools_required", [])
    task_name = task.get("task", "Career Exploration Task")

    nodes = []
    for i, tool in enumerate(tools):
        # Vector se relevant feature nikalo for this tool
        relevance = 0.5
        if "database" in tool.lower():
            relevance = vector.get("AB_Information Ordering", 0.5)
        elif "ai" in tool.lower():
            relevance = vector.get("IT_Investigative", 0.5)
        elif "communication" in tool.lower():
            relevance = vector.get("WS_Social Orientation", 0.5)
        elif "research" in tool.lower():
            relevance = vector.get("WS_Intellectual Curiosity", 0.5)
        elif "presentation" in tool.lower():
            relevance = vector.get("AB_Oral Expression", 0.5)

        nodes.append({
            "id": f"node_{i+1:02d}",
            "label": tool,
            "relevance_score": round(relevance, 3),
            "description": f"Required for: {task_name}"
        })

    # Connections: sequential
    connections = [
        {"from": f"node_{i+1:02d}", "to": f"node_{i+2:02d}"}
        for i in range(len(nodes) - 1)
    ]

    return {
        "task": task_name,
        "nature": task.get("nature", ""),
        "goal_status": task.get("goal_status", ""),
        "nodes": nodes,
        "connections": connections
    }


def select_phase4_task(student_type: str, archetype: str) -> dict:
    """
    Selects a task from phase4_tasks.json matching student type and archetype.
    """
    tasks = load_json("phase4_tasks.json")
    if not tasks: return {}
    
    # Filter by class (10th or 12th)
    class_tasks = [t for t in tasks if t.get("class") == student_type]
    if not class_tasks: class_tasks = tasks
    
    # Try to match nature/archetype
    # Archetype might be "The Founder", task nature might be "Founder"
    match_tasks = [t for t in class_tasks if t.get("nature", "").lower() in archetype.lower()]
    
    import random
    if match_tasks:
        return random.choice(match_tasks)
    return random.choice(class_tasks)


# ─── Cosine Similarity (KNN approach) ────────────────────────────────────────

def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


def match_careers_from_vector(vector: Dict, top_n: int = 3) -> List[dict]:
    df = load_occupation_matrix()
    available_cols = [c for c in ALL_FEATURES if c in df.columns]
    df_clean = df.dropna(subset=available_cols)

    # Student vector as numpy array
    student_vec = np.array([vector.get(col, 0.5) for col in available_cols])

    scores = []
    for _, row in df_clean.iterrows():
        occ_vec = np.array([row[col] for col in available_cols])
        sim = cosine_similarity(student_vec, occ_vec)
        scores.append({
            "title": row.get("Title", "Unknown"),
            "onet_code": row.get("O*NET-SOC Code", ""),
            "description": str(row.get("Description", ""))[:200],
            "match_score": round(sim, 4),
            "match_percent": int(round(sim * 100)),
            "job_zone": int(row.get("Job Zone", 0)) if pd.notna(row.get("Job Zone")) else 0,
        })

    scores.sort(key=lambda x: x["match_score"], reverse=True)
    return scores[:top_n]