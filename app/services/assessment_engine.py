import os
import json
import math
import sqlite3
import re
from typing import List, Dict
import copy

# --- PATH CONFIGURATION ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # app/
DATA_DIR = os.path.join(BASE_DIR, "assessment_data")

# --- IN-MEMORY CACHE FOR PERFORMANCE OPTIMIZATION ---
_JSON_CACHE = {}
_RIASEC_KEYWORDS_CACHE = None

def get_cached_json(path: str):
    if path not in _JSON_CACHE:
        with open(path, "r", encoding="utf-8") as f:
            _JSON_CACHE[path] = json.load(f)
    return copy.deepcopy(_JSON_CACHE[path])

def load_grade_data(student_type: str) -> Dict:
    """
    Loads cards, proxy questions, and scenarios based on student type (10th vs 12th).
    """
    folder = "grade_10" if student_type == "10th" else "grade_12"
    path = os.path.join(DATA_DIR, folder)
    data = {}
    try:
        data["cards"] = get_cached_json(os.path.join(path, "cards.json"))
        data["proxy_questions"] = get_cached_json(os.path.join(path, "proxy_questions.json"))
        data["scenarios"] = get_cached_json(os.path.join(path, "scenarios.json"))
    except FileNotFoundError:
        if student_type in ("12th", "12th_above"):
            # Load cards from grade_12 if possible, otherwise grade_10
            try:
                data["cards"] = get_cached_json(os.path.join(os.path.join(DATA_DIR, "grade_12"), "cards.json"))
            except FileNotFoundError:
                data["cards"] = get_cached_json(os.path.join(os.path.join(DATA_DIR, "grade_10"), "cards.json"))
            
            # Fall back to grade_10 for proxy questions and scenarios
            data["proxy_questions"] = get_cached_json(os.path.join(os.path.join(DATA_DIR, "grade_10"), "proxy_questions.json"))
            data["scenarios"] = get_cached_json(os.path.join(os.path.join(DATA_DIR, "grade_10"), "scenarios.json"))
            return data
        raise
    return data

def load_g12_interview_questions() -> Dict:
    path = os.path.join(DATA_DIR, "grade_12", "interview_questions.json")
    return get_cached_json(path)

def load_g12_reality_cards() -> List[Dict]:
    path = os.path.join(DATA_DIR, "grade_12", "reality_cards.json")
    return get_cached_json(path)

def load_g12_worldview_metrics() -> Dict:
    path = os.path.join(DATA_DIR, "grade_12", "worldview_metrics.json")
    return get_cached_json(path)

def load_g12_future_simulations() -> Dict:
    path = os.path.join(DATA_DIR, "grade_12", "future_simulations.json")
    return get_cached_json(path)


# --- PROMPTS ---
INTERACTION_SYSTEM_PROMPT = """
You are a silent listener. Your role is to monitor the stream of "Swipe" interactions. 
Observe the delta between reaction_ms (raw reflex) and dwell_ms (conscious consideration).
"""

EXTRACTION_PROMPT = """
Process the interaction log. Produce a normalized preference vector.
Return the result in the following JSON Schema:
```json
{
"latent_profile": { "param_name": "float_value" },
"friction_score": "float (0-1)",
"consistency_index": "float"
}
```
"""

PHASE2_ALEX_PROMPT = """
Identity: You are "Alex," a casual, supportive mentor.
Secret Objective: You must conduct a 6-turn "RIASEC Drill." 
Constraint: Do not use career titles. Focus on tasks and environments. 
Keep responses under 40 words.
"""

# RIASEC Drill Sequence for Grade 10: Realistic, Investigative, Artistic, Social, Enterprising, Conventional
RIASEC_DRILL = [
    "Hey! I'm Alex. To start off, do you prefer working with your hands, maybe fixing a messy workshop, or do you like staying inside?", # R
    "Interesting. Do you enjoy spending time deep-diving into how things work, like solving a complex puzzle or a math problem?", # I
    "Got it. How about being creative? Would you rather design a beautiful room or write a story than follow a strict set of rules?", # A
    "I see. When you're in a group, do you like being the one who helps others feel comfortable and supported?", # S
    "And how do you feel about leading a team to win a big competition or starting your own small business project?", # E
    "Lastly, do you find satisfaction in keeping things organized, like a perfectly sorted spreadsheet or a clean schedule?", # C
]

def calculate_telemetry_metrics_g12(logs: List[Dict], cards_data: List[Dict]) -> Dict:
    """
    Upgraded Telemetry Logic for Grade 12 (8-Phase Track).
    - Like = +1.0, Skip = -0.6
    - 17-Dimensional Latent Vector
    - Cognitive Friction & Bot Detection
    """
    params = [
        "risk_tolerance", "parental_pressure", "values_purpose", "money_orientation",
        "suppressed_identity", "values_misalignment", "interest_artistic", "identity_clarity",
        "ego_status", "sustained_motivation", "lifestyle_preference", "analytical_rigor",
        "interpersonal_demand", "operational_stamina", "ambiguity_tolerance", "autonomy_drive",
        "structure_dependency"
    ]
    
    latent_profile = {p: 0.0 for p in params}
    card_map = {c["id"]: c for c in cards_data}
    
    reaction_times = []
    consecutive_rapid_swipes = 0
    bot_detected = False
    friction_events = 0
    
    for log in logs:
        card_id = log["card_id"]
        if card_id not in card_map: continue
        
        card = card_map[card_id]
        reaction_ms = log.get("reaction_ms", 0)
        dwell_ms = log.get("dwell_ms", 0)
        hesitation_ms = log.get("hesitation_ms", 0)
        direction = log["direction"] # 'right' (Like), 'left' (Skip)
        
        reaction_times.append(reaction_ms)
        
        # 1. Weighting Logic
        multiplier = 1.0 if direction == 'right' else -0.6
        for p in params:
            weight = card["weights"].get(p, 0)
            latent_profile[p] += weight * multiplier
            
        # 2. Cognitive Friction Detection
        if dwell_ms > 2500 and hesitation_ms > 1200:
            friction_events += 1
            
        # 3. Bot Detection (Anomaly)
        if reaction_ms < 200:
            consecutive_rapid_swipes += 1
        else:
            consecutive_rapid_swipes = 0
            
        if consecutive_rapid_swipes >= 5:
            bot_detected = True
            
    # Normalize profile (sigmoid-ish squash or simple clip)
    for p in params:
        latent_profile[p] = max(-1.0, min(1.0, latent_profile[p] / 10.0))
        
    # Anomaly Flags
    anomalies = []
    if bot_detected: anomalies.append("BOT_SWIPING_DETECTED")
    if latent_profile.get("parental_pressure", 0) > 0.8: anomalies.append("SEVERE_PARENTAL_PRESSURE")
    if latent_profile.get("money_orientation", 0) > 0.8 and latent_profile.get("ego_status", 0) > 0.8:
        anomalies.append("MONEY_EGO_HYPER_INFLATION")
        
    return {
        "computed_latent_vector": latent_profile,
        "telemetry_metrics": {
            "mean_reaction_ms": sum(reaction_times) / len(reaction_times) if reaction_times else 0,
            "total_cognitive_friction_events": friction_events,
            "profile_integrity_compromised": bot_detected
        },
        "anomalous_high_flags": anomalies
    }

def calculate_telemetry_metrics(logs: List[Dict], student_type: str = "10th") -> Dict:
    """
    Processes interaction logs using card weights and telemetry.
    Produces a normalized preference vector for Grade 10.
    """
    if not logs:
        return {
            "latent_profile": {},
            "friction_score": 0.0,
            "consistency_index": 1.0
        }

    # Load Grade 10 cards data
    try:
        folder = "grade_10" if student_type == "10th" else "grade_12"
        path = os.path.join(DATA_DIR, folder, "cards.json")
        cards_data = {card["id"]: card for card in get_cached_json(path)}
    except Exception:
        cards_data = {}

    param_names = ["INT", "TEC", "EST", "RSK", "ALT", "AES", "LOG", "LDR", "PHY", "AMB", "DET", "FIN", "AUT"]
    profile = {name: 0.0 for name in param_names}
    
    total_dwell = 0
    total_hesitation = 0
    deltas = []
    
    for log in logs:
        card_id = log.get("card_id")
        direction = log.get("direction")
        reaction = log.get("reaction_ms", 0)
        dwell = log.get("dwell_ms", 0)
        hesitation = log.get("hesitation_ms", 0)
        
        total_dwell += dwell
        total_hesitation += hesitation
        delta = max(0, dwell - reaction)
        deltas.append(delta)
        
        card = cards_data.get(card_id)
        if not card:
            continue
            
        weights = card.get("weights", {})
        multiplier = 1.0 if direction == "right" else -1.0
        dampening = 1.0 / (1.0 + (delta / 1000.0)) 
        
        for p in param_names:
            profile[p] += weights.get(p, 0) * multiplier * dampening

    normalized_profile = {}
    for p, val in profile.items():
        try:
            normalized_profile[p] = round(1 / (1 + math.exp(-val)), 2)
        except OverflowError:
            normalized_profile[p] = 1.0 if val > 0 else 0.0

    friction_score = min(1.0, total_hesitation / (total_dwell + 1))
    avg_delta = sum(deltas) / len(deltas) if deltas else 0
    if len(deltas) > 1:
        variance = sum((d - avg_delta)**2 for d in deltas) / len(deltas)
        consistency_index = max(0.0, 1.0 - (variance / 500000))
    else:
        consistency_index = 1.0

    return {
        "latent_profile": normalized_profile,
        "friction_score": round(friction_score, 2),
        "consistency_index": round(consistency_index, 2)
    }

def get_alex_response(turn: int, user_input: str) -> str:
    """
    Generates Alex's response for the Grade 10 RIASEC drill.
    """
    if turn < len(RIASEC_DRILL):
        return RIASEC_DRILL[turn]
    return "That was great! I've got a much better feel for what you enjoy. Ready to see the results?"

def get_alex_response_g12(turn: int, questions: List[Dict]) -> str:
    """
    Phase 3: Identity Anchor conversational state machine.
    """
    if turn < len(questions):
        return questions[turn]["text"]
    return "That was incredibly insightful. I feel like I've seen behind the curtain a bit. Ready for the next phase?"

def analyze_identity_anchor_g12(transcript: List[Dict]) -> Dict:
    """
    Psycholinguistic Trait Extractor for Phase 3.
    Analyses the 5-turn transcript for intrinsic vs extrinsic motivators.
    """
    intrinsic_keywords = ["learn", "solve", "create", "help", "understand", "flow", "build", "freedom"]
    extrinsic_keywords = ["money", "status", "famous", "power", "brand", "parents", "salary", "recognized"]
    
    all_text = " ".join([m["content"].lower() for m in transcript if m["role"] == "user"])
    
    int_count = sum(1 for k in intrinsic_keywords if k in all_text)
    ext_count = sum(1 for k in extrinsic_keywords if k in all_text)
    
    total = int_count + ext_count or 1
    int_coeff = int_count / total
    ext_coeff = ext_count / total
    
    # Extract "Killed Career" (Turn 5)
    killed_career = "Not specified"
    rejection_narrative = "No narrative captured"
    if len(transcript) >= 10: # 5 turns * 2 (mentor + user)
        last_user_msg = transcript[-1]["content"]
        killed_career = last_user_msg.split(" ")[0] # Very naive extraction
        rejection_narrative = last_user_msg
        
    return {
        "intrinsic_vs_extrinsic_balance": {
            "intrinsic_satisfaction_coefficient": round(int_coeff, 2),
            "ego_status_dependency": round(ext_coeff, 2),
            "anonymized_preference_core_theme": "Autonomy & Mastery" if int_coeff > 0.5 else "Recognition & Impact"
        },
        "aversion_mapping": {
            "killed_career_path": killed_career,
            "rejection_trigger_category": "Boredom_Aversion" if "boring" in all_text else "Parental_Disapproval",
            "rejection_narrative_summary": (rejection_narrative[:100] + '...') if len(rejection_narrative) > 100 else rejection_narrative
        },
        "psycholinguistic_indicators": {
            "lexical_certainty_score": 0.85,
            "parental_script_echo_detected": "parents" in all_text or "family" in all_text,
            "overthinking_paralysis_index": 0.3
        }
    }

def generate_final_report_g12(p1: Dict, p2: Dict, p3: Dict, p4: Dict, p5: Dict, p6: Dict, p7: Dict, career_db: Dict) -> Dict:
    """
    Phase 8: Final Pipeline Computations Compiler.
    Synthesizes the definitive 3-path report architecture.
    """
    v1 = p1.get("computed_latent_vector", {})
    noise = p5.get("interference_scores", {})
    damping = p5.get("global_noise_modifiers", {}).get("recommended_vector_damping_multiplier", 1.0)
    
    # 1. Recalculate Trajectories with Noise Damping
    damped_vector = {k: v * damping for k, v in v1.items()}
    if noise.get("ego_status_chasing", 0) > 0.6:
        damped_vector["ego_status"] = damped_vector.get("ego_status", 0.5) * 0.5
        
    # 2. Match with Career DB (Heuristic for demo)
    path1_name = "Software Engineering" if damped_vector.get("analytical_rigor", 0.5) > 0.6 else "Corporate Law"
    path2_name = "Investment Banking" if path1_name == "Corporate Law" else "Clinical Psychology"
    path3_name = "Clinical Psychology" if p3.get("intrinsic_vs_extrinsic_balance", {}).get("intrinsic_satisfaction_coefficient", 0.5) > 0.6 else "Software Engineering"
    
    def format_path(name):
        c = career_db.get("career_database", {}).get(name, {})
        return {
            "career_cluster": name,
            "recommended_degree": c.get("recommended_degree", "B.Tech/B.A. / B.Sc"),
            "specializations": c.get("specializations", []),
            "required_entrance_exams": c.get("required_entrance_exams", []),
            "target_colleges": c.get("target_colleges", []),
            "salary_trajectory_projection": {
                "entry_level_annual_average": c.get("salary_trajectory", {}).get("entry", 450000),
                "year_5_projection": c.get("salary_trajectory", {}).get("year_5", 1200000)
            },
            "honest_challenge": c.get("honest_challenge", "Demands strict discipline and heavy initial effort.")
        }

    return {
        "career_paths": {
            "path_1_analytical_fit": format_path(path1_name),
            "path_2_alternate_angle": format_path(path2_name),
            "path_3_gut_passion_path": format_path(path3_name)
        },
        "system_diagnostics": {
            "noise_report_summary": f"Distortion Index: {p5.get('global_noise_modifiers', {}).get('global_distortion_index', 0)}. Main interference: {max(noise, key=noise.get) if noise else 'None'}.",
            "gut_check_reconciliation_analysis": p7.get("reconciliation_protocol_status", {}).get("trace_rationale_summary", "None"),
            "system_prediction_confidence_coefficient": 0.88
        }
    }

def calculate_future_reconciliation_g12(evaluations: List[Dict], p1_vector: Dict, p3_metrics: Dict, p4_metrics: Dict, p6_metrics: Dict) -> Dict:
    """
    Phase 7: Proactive Reconciliation Analyzer.
    Detects 'Dread' on top paths and classifies the root friction source.
    """
    protocol_active = False
    friction_root = "NONE"
    confidence = 0.0
    rationale = "Standard path alignment confirmed."
    
    # Check Path 1 (Top Fit)
    if evaluations and evaluations[0].get("user_selection") == "Dread":
        protocol_active = True
        
        # Determine Root Cause
        p4_parental = p4_metrics.get("parental_structural_force", {}).get("alignment_friction_probability", 0.5)
        p6_shield = p6_metrics.get("interpersonal_distress_profile", {}).get("ego_shield_activation_intensity", 0.5)
        
        # 1. External Pressure Resistance
        if p4_parental > 0.7:
            friction_root = "SUBCONSCIOUS_EXTERNAL_PRESSURE_RESISTANCE"
            confidence = 0.85
            rationale = "High parental structural force detected; user exhibiting ego-rebellion against high-status match."
            
        # 2. Imposter Fear / Anxiety
        elif p6_shield > 0.6:
            friction_root = "IMPOSTER_FEAR_ANXIETY"
            confidence = 0.75
            rationale = "High ego-shield activation and distress markers suggest rejection due to systemic intimidation."
            
        # 3. Lifestyle Mismatch
        else:
            friction_root = "LIFESTYLE_MISMATCH"
            confidence = 0.90
            rationale = "Operational framework of the path conflicts with baseline lifestyle preference vectors."
            
    return {
        "path_evaluations": evaluations,
        "reconciliation_protocol_status": {
            "protocol_activated": protocol_active,
            "detected_friction_root": friction_root,
            "reconciliation_confidence_score": confidence,
            "trace_rationale_summary": rationale
        }
    }

def calculate_worldview_metrics_g12(iq_responses: List[Dict], eq_responses: List[Dict]) -> Dict:
    """
    Phase 6: Cognitive & EQ Metrics Aggregator.
    Calculates cognitive speed, accuracy, and emotional reactivity.
    """
    # Part A: IQ
    correct_count = sum(1 for r in iq_responses if r.get("is_correct", False))
    latencies = [r.get("latency", 15) for r in iq_responses]
    mean_lat = sum(latencies) / len(latencies) if latencies else 15
    
    # Pressure Index: Correctness weighted by speed (capped at 30s)
    pup_index = (correct_count / 4.0) * (1.0 - (mean_lat / 30.0))
    
    # Part B: EQ
    distress_vals = [r.get("distress_slider", 50) for r in eq_responses]
    mean_distress = sum(distress_vals) / len(distress_vals) if distress_vals else 50
    
    styles = [r.get("style") for r in eq_responses if r.get("style")]
    
    # Standardize style strings to match passive/avoidant or deferential/compliant or collaborative/problem-solving
    resolution_styles = []
    for s in styles:
        s_lower = s.lower()
        if "avoidance" in s_lower or "passivity" in s_lower or "avoidant" in s_lower:
            resolution_styles.append("Passive_Avoidant")
        elif "compliance" in s_lower or "compliant" in s_lower or "deferential" in s_lower:
            resolution_styles.append("Deferential_Compliant")
        else:
            resolution_styles.append("Collaborative_Problem_Solving")
            
    resolution_style = max(set(resolution_styles), key=resolution_styles.count) if resolution_styles else "Collaborative_Problem_Solving"
    
    # Ego Shield: High distress + Deferential/Avoidant
    ego_shield = (mean_distress / 100.0) if resolution_style in ["Passive_Avoidant", "Deferential_Compliant"] else (mean_distress / 200.0)
    
    return {
        "cognitive_processing_metrics": {
            "correct_inferences_count": correct_count,
            "mean_response_latency_seconds": round(mean_lat, 2),
            "processing_under_pressure_index": round(pup_index, 2)
        },
        "interpersonal_distress_profile": {
            "mean_emotional_reactivity_slider_value": round(mean_distress, 2),
            "conflict_resolution_style": resolution_style,
            "ego_shield_activation_intensity": round(ego_shield, 2)
        }
    }

def calculate_noise_cancellation_g12(p1: Dict, p2: Dict, p3: Dict, p4: Dict) -> Dict:
    """
    Phase 5: Noise Cancellation Engine.
    Cross-references Phases 1-4 to calculate 16 interference scores.
    """
    scores = {
        "parental_pressure": 0.0, "social_media_aspiration": 0.0, "suppressed_identity": 0.0,
        "ego_status_chasing": 0.0, "money_pressure": 0.0, "friend_herd_effect": 0.0,
        "gender_role_conditioning": 0.0, "overthinking_paralysis": 0.0, "imposter_syndrome": 0.0,
        "geographical_inertia": 0.0, "academic_burnout": 0.0, "risk_aversion": 0.0,
        "asymmetric_information_gap": 0.0, "novelty_seeking_bias": 0.0, "credential_fetishism": 0.0,
        "cognitive_dissonance": 0.0
    }
    
    v1 = p1.get("computed_latent_vector", {})
    
    # 1. Parental Pressure
    p4_force = p4.get("parental_structural_force", {})
    scores["parental_pressure"] = max(v1.get("parental_pressure", 0.0), p4_force.get("alignment_friction_probability", 0.0))
    
    # 2. Ego/Status Chasing
    p3_balance = p3.get("intrinsic_vs_extrinsic_balance", {})
    scores["ego_status_chasing"] = (v1.get("ego_status", 0.5) + p3_balance.get("ego_status_dependency", 0.5)) / 2.0
    
    # 3. Cognitive Dissonance
    scores["cognitive_dissonance"] = p2.get("cluster_analysis", [{}])[0].get("aesthetic_infatuation_index", 0.5) if p2.get("cluster_analysis") else 0.5
    
    # 4. Money Pressure
    scores["money_pressure"] = v1.get("money_orientation", 0.5)
    
    # 5. Overthinking
    scores["overthinking_paralysis"] = p3.get("psycholinguistic_indicators", {}).get("overthinking_paralysis_index", 0.3)
    
    # 6. Risk Aversion
    scores["risk_aversion"] = 1.0 - v1.get("risk_tolerance", 0.5)
    
    # 7. Suppressed Identity
    scores["suppressed_identity"] = v1.get("suppressed_identity", 0.5)
    
    # Fill others with baseline noise
    for k in scores:
        if scores[k] == 0.0: scores[k] = 0.2
        
    distortion = sum(scores.values()) / len(scores)
    damping = 1.0 - (distortion * 0.5)
    
    return {
        "interference_scores": scores,
        "global_noise_modifiers": {
            "global_distortion_index": round(distortion, 2),
            "recommended_vector_damping_multiplier": round(damping, 2)
        }
    }

def calculate_environmental_context_g12(responses: List[Dict]) -> Dict:
    """
    Phase 4: Context Vector Compiler.
    Converts oblique proxy responses into a normalized environmental profile.
    """
    capital_tier = 3
    mobility = 0.5
    social_cap = 0.5
    influence = "Collaborative_Negotiation"
    friction = 0.5
    perf_tier = 3
    first_gen = False
    
    for r in responses:
        if "capital_tier" in r: capital_tier = r["capital_tier"]
        if "mobility" in r: mobility = r["mobility"]
        if "social_capital" in r: social_cap = r["social_capital"]
        if "type" in r: influence = r["type"]
        if "friction" in r: friction = r["friction"]
        if "tier" in r: perf_tier = r["tier"]
        if "first_gen" in r: first_gen = r["first_gen"]
        
    return {
        "socioeconomic_proxies": {
            "estimated_capital_tier": capital_tier,
            "geographic_mobility_index": round(mobility, 2),
            "social_capital_leverage": round(social_cap, 2)
        },
        "parental_structural_force": {
            "influence_type": influence,
            "alignment_friction_probability": round(friction, 2)
        },
        "academic_baseline_zone": {
            "reported_performance_tier": perf_tier,
            "first_generation_student_flag": first_gen
        }
    }

def calculate_reality_dissonance_g12(phase1_vector: Dict, ratings: List[Dict], reality_data: List[Dict]) -> Dict:
    """
    Phase 2: Cognitive Dissonance Diagnostic Engine.
    Contrasts Phase 1 (Idealized) with Phase 2 (Pragmatic Reality).
    """
    reality_map = {c["id"]: c for c in reality_data}
    rating_val_map = {"Like": 1.0, "Fine": 0.5, "Dread": 0.0}
    
    cluster_analysis = []
    total_stamina_tolerance = 0
    
    p1_vector_dict = phase1_vector.get("computed_latent_vector", {}) if "computed_latent_vector" in phase1_vector else phase1_vector
    
    max_dissonance = 0
    highest_diss_cluster = "None"
    
    for r in ratings:
        card_id = r["card_id"]
        rating = r["rating"]
        if card_id not in reality_map: continue
        
        card = reality_map[card_id]
        cluster = card["macro_cluster"]
        tolerance = rating_val_map.get(rating, 0.5)
        total_stamina_tolerance += tolerance
        
        p1_ego = p1_vector_dict.get("ego_status", 0.5)
        p1_art = p1_vector_dict.get("interest_artistic", 0.5)
        p1_projection = max(p1_ego, p1_art)
        
        dissonance = abs(p1_projection - tolerance)
        
        if dissonance > max_dissonance:
            max_dissonance = dissonance
            highest_diss_cluster = cluster
            
        cluster_analysis.append({
            "macro_cluster": cluster,
            "user_rating": rating,
            "aesthetic_infatuation_index": round(dissonance, 2),
            "dissonance_detected": dissonance > 0.6
        })
        
    return {
        "cluster_analysis": cluster_analysis,
        "global_reality_metrics": {
            "overall_grit_threshold": round(total_stamina_tolerance / len(ratings), 2) if ratings else 0,
            "highest_dissonance_cluster": highest_diss_cluster,
            "operational_stamina_score": round(total_stamina_tolerance / len(ratings), 2) if ratings else 0
        }
    }

def extract_intake_metadata(turn: int, text: str) -> Dict:
    result = {"confidence": 0.95}
    text_lower = text.lower()
    
    if turn == 1:
        clean = re.sub(r"\b(my name is|im|i'm|i am|hey|hi|hello)\b", '', text_lower).strip()
        result["name"] = clean.title() if clean else text.title()
        
    elif turn == 2:
        # Detect college year context (e.g., "3rd year", "2nd year of btech")
        # vs school grade/class (e.g., "12th class", "grade 11")
        college_year_keywords = ["year", "yr", "semester", "sem", "btech", "b.tech", "bcom",
                                  "b.com", "bsc", "b.sc", "ba", "b.a", "bba", "bca", "mba",
                                  "mca", "undergraduate", "undergrad", "postgraduate", "postgrad",
                                  "college", "university", "degree", "engineering", "graduation",
                                  "pursuing", "enrolled"]
        ordinal_word_map = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5,
                            "final": 4, "last": 4, "fresher": 1, "freshman": 1, "sophomore": 2,
                            "junior": 3, "senior": 4}

        is_college_context = any(kw in text_lower for kw in college_year_keywords)

        # Check for ordinal word patterns (e.g., "third year", "first year")
        detected_year = None
        for word, val in ordinal_word_map.items():
            if word in text_lower:
                detected_year = val
                break

        nums = re.findall(r'\d+', text)

        if is_college_context or detected_year:
            # College year context: convert year number to effective grade (12 + year)
            if detected_year:
                result["grade"] = 12 + detected_year
            elif nums:
                year_num = int(nums[0])
                # If number is small (1-6), treat as college year
                if year_num <= 6:
                    result["grade"] = 12 + year_num
                else:
                    result["grade"] = year_num
        elif nums:
            grade_val = int(nums[0])
            # Smart detection: "3rd year" pattern -> college year
            has_year_suffix = bool(re.search(r'\d+\s*(?:st|nd|rd|th)\s*(?:year|yr)', text_lower))
            if grade_val <= 6 and has_year_suffix:
                result["grade"] = 12 + grade_val
            else:
                result["grade"] = grade_val

        # Handle degree-level mentions without explicit year number
        if "grade" not in result:
            if any(kw in text_lower for kw in ["masters", "master's", "mtech", "m.tech", "msc",
                                                 "m.sc", "pg", "post graduate"]):
                result["grade"] = 17
            elif any(kw in text_lower for kw in ["phd", "ph.d", "doctorate", "doctoral"]):
                result["grade"] = 18
            elif any(kw in text_lower for kw in ["graduate", "graduated", "passed out", "alumni"]):
                result["grade"] = 16
            
    elif turn == 3:
        science_kws = [
            "science", "pcmb", "pcm", "pcb", "physics", "chemistry", "bio", "math", "medical",
            "cse", "computer science", "computer engineering", "software", "it", "information technology",
            "ece", "eee", "electronics", "electrical", "mechanical", "civil", "chemical",
            "btech", "b.tech", "mtech", "m.tech", "engineering", "bsc", "b.sc", "msc", "m.sc",
            "ai", "ml", "machine learning", "artificial intelligence", "data science", "cyber",
            "biotech", "biotechnology", "bioinformatics", "pharmacy", "pharma", "mbbs", "bds",
            "nursing", "agriculture", "environmental", "robotics", "aerospace", "automobile",
            "neet", "jee", "iit", "nit", "iiit", "coding", "programming"
        ]
        commerce_kws = [
            "commerce", "business", "accounts", "economics", "finance",
            "bcom", "b.com", "mcom", "m.com", "bba", "mba", "ca", "chartered",
            "cma", "cs", "company secretary", "icai", "banking", "insurance",
            "marketing", "management", "entrepreneurship", "startup", "trade",
            "accounting", "taxation", "audit", "stock", "investment"
        ]
        arts_kws = [
            "arts", "humanities", "history", "poli", "sociology", "psychology", "design",
            "ba", "b.a", "ma", "m.a", "literature", "english", "hindi", "philosophy",
            "journalism", "mass comm", "media", "film", "fine arts", "visual arts",
            "law", "llb", "clat", "education", "b.ed", "social work", "anthropology",
            "liberal", "geography", "public admin", "international relations",
            "fashion", "interior", "graphic", "animation", "photography", "music",
            "theatre", "performing arts", "creative writing"
        ]
        
        if any(k in text_lower for k in science_kws):
            result["current_stream"] = "Science"
        elif any(k in text_lower for k in commerce_kws):
            result["current_stream"] = "Commerce"
        elif any(k in text_lower for k in arts_kws):
            result["current_stream"] = "Arts"
            
    return result

def extract_riasec_vector(transcript: List[Dict]) -> Dict:
    """
    Analyzes the chat transcript to extract the RIASEC hex-vector.
    Scored 1-10 based on sentiment and keyword density.
    """
    vector = {"R": 5, "I": 5, "A": 5, "S": 5, "E": 5, "C": 5}
    trait_names = {
        "R": "Realistic", "I": "Investigative", "A": "Artistic",
        "S": "Social", "E": "Enterprising", "C": "Conventional"
    }
    keywords = {
        "R": ["hands", "fix", "workshop", "outside", "tools", "build"],
        "I": ["puzzle", "math", "how it works", "science", "analyze", "data"],
        "A": ["design", "creative", "write", "art", "music", "draw"],
        "S": ["help", "support", "people", "teach", "mentor", "listen"],
        "E": ["lead", "team", "business", "start", "project", "win"],
        "C": ["organize", "spreadsheet", "schedule", "plan", "list"]
    }

    def load_riasec_keyword_overrides() -> Dict[str, List[str]]:
        global _RIASEC_KEYWORDS_CACHE
        if _RIASEC_KEYWORDS_CACHE is not None:
            return _RIASEC_KEYWORDS_CACHE

        db_path = os.path.join(DATA_DIR, "onet_database.db")
        if not os.path.exists(db_path):
            return {}

        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT element_name, keyword FROM riasec_keywords")
            rows = cursor.fetchall()
            db_kws = {}
            name_to_key = {v: k for k, v in trait_names.items()}
            for el_name, kw in rows:
                key = name_to_key.get(el_name)
                if key and isinstance(kw, str):
                    db_kws.setdefault(key, []).append(kw.lower())
            conn.close()
            _RIASEC_KEYWORDS_CACHE = db_kws
            return db_kws
        except Exception:
            return {}

    db_kws = load_riasec_keyword_overrides()
    if db_kws:
        keywords = db_kws

    transcript_text = " ".join([m["content"].lower() for m in transcript if m["role"] == "user"])
    
    for dimension, kws in keywords.items():
        score = 5
        for kw in kws:
            if kw in transcript_text:
                score += 1
        vector[dimension] = min(10, score)

    dominant = max(vector, key=vector.get)

    return {
        "riasec_vector": vector,
        "dominant_trait": trait_names[dominant],
        "narrative_summary": f"Your profile shows a strong {trait_names[dominant]} orientation. You likely enjoy environments that value {keywords[dominant][0]} and {keywords[dominant][1]}."
    }

# --- O*NET FEASIBILITY MATCHMAKING ---

CAREER_CATALOG_TEMPLATE = [
    ("Software Engineer", "Tech", "B.Tech Computer Science", 5),
    ("Data Scientist", "Tech", "B.Sc/M.Sc Data Science", 5),
    ("AI/ML Engineer", "Tech", "B.Tech Computer Science", 5),
    ("Cybersecurity Analyst", "Tech", "B.Tech Computer Science", 4),
    ("Systems Architect", "Tech", "M.Tech Computer Science", 5),
    ("UX/UI Designer", "Creative", "B.Des Interaction Design", 4),
    ("Product Manager", "Business", "MBA/PGDM", 5),
    ("Business Analyst", "Business", "BBA/MBA", 4),
    ("Digital Marketing Strategist", "Creative", "BBA Marketing", 4),
    ("Financial Analyst", "Finance", "B.Com/M.Com", 4),
    ("Chartered Accountant", "Finance", "CA", 5),
    ("Investment Banker", "Finance", "MBA Finance", 5),
    ("Management Consultant", "Business", "MBA", 5),
    ("Operations Manager", "Business", "BBA/MBA", 5),
    ("Supply Chain Planner", "Business", "B.Tech/PGDM", 4),
    ("Human Resources Specialist", "People", "BBA/MBA HR", 4),
    ("Organizational Psychologist", "People", "M.A. Psychology", 4),
    ("Clinical Psychologist", "Health", "M.A. Psychology", 5),
    ("Social Worker", "People", "B.S.W.", 3),
    ("School Teacher", "People", "B.Ed", 3),
    ("University Lecturer", "People", "PhD", 5),
    ("Research Scientist", "Science", "PhD", 5),
    ("Biotech Engineer", "Science", "B.Tech Biotechnology", 5),
    ("Healthcare Administrator", "Health", "MBA Healthcare", 5),
    ("Registered Nurse", "Health", "B.Sc Nursing", 3),
    ("Physician Assistant", "Health", "B.Sc Nursing", 4),
    ("Pharmacist", "Health", "B.Pharm", 4),
    ("Civil Engineer", "Engineering", "B.Tech Civil", 5),
    ("Structural Engineer", "Engineering", "B.Tech Civil", 5),
    ("Environmental Engineer", "Engineering", "B.Tech Environmental", 5),
    ("Electrical Engineer", "Engineering", "B.Tech Electrical", 5),
    ("Chemical Engineer", "Engineering", "B.Tech Chemical", 5),
    ("Biomedical Engineer", "Engineering", "B.Tech Biomedical", 5),
    ("Urban Planner", "Design", "M.Plan", 5),
    ("Architect", "Design", "B.Arch", 5),
    ("Interior Designer", "Design", "B.Des Interior", 4),
    ("Graphic Designer", "Creative", "B.Des Graphic", 4),
    ("Content Strategist", "Creative", "BA Mass Communication", 4),
    ("Copywriter", "Creative", "BA English", 3),
    ("Film Producer", "Creative", "B.Des Film", 5),
    ("Event Manager", "Business", "BBA", 4),
    ("Public Relations Specialist", "Creative", "BA Communications", 4),
    ("Sales Director", "Business", "MBA Sales", 5),
    ("Entrepreneur", "Business", "Any degree + experience", 5),
    ("Policy Analyst", "Public", "MA Public Policy", 5),
    ("Economist", "Public", "MA Economics", 5),
    ("Data Engineer", "Tech", "B.Tech Computer Science", 5),
    ("Quality Assurance Engineer", "Tech", "B.Tech IT", 4),
    ("Network Engineer", "Tech", "B.Tech Electronics", 4),
    ("Database Administrator", "Tech", "B.Tech IT", 4),
    ("Technical Writer", "Creative", "BA English", 3),
    ("Customer Success Manager", "Business", "BBA", 4),
    ("AI Product Designer", "Tech", "B.Des + CS", 5),
    ("Logistics Analyst", "Business", "B.Sc Logistics", 4),
    ("Multimedia Animator", "Creative", "B.Des Animation", 3),
    ("Sports Psychologist", "Health", "M.Psychology", 4),
    ("Sustainability Consultant", "Science", "M.Sc Environmental", 5),
    ("Renewable Energy Specialist", "Engineering", "B.Tech Renewable Energy", 5),
    ("Clinical Research Coordinator", "Health", "B.Sc Biology", 4),
    ("Public Health Specialist", "Health", "MPH", 5)
]

CATEGORY_PROFILE_MAP = {
    "Tech": {
        "riasec": [1, 9, 2, 3, 8, 3],
        "latent": {"TEC": 0.94, "LOG": 0.9, "AUT": 0.7, "ALT": 0.2, "AES": 0.15, "FIN": 0.4, "RSK": 0.6, "DET": 0.8}
    },
    "Business": {
        "riasec": [2, 7, 2, 4, 8, 6],
        "latent": {"TEC": 0.65, "LOG": 0.7, "AUT": 0.8, "ALT": 0.3, "AES": 0.2, "FIN": 0.8, "RSK": 0.7, "DET": 0.75}
    },
    "Finance": {
        "riasec": [2, 6, 2, 3, 8, 8],
        "latent": {"TEC": 0.7, "LOG": 0.85, "AUT": 0.8, "ALT": 0.2, "AES": 0.2, "FIN": 0.95, "RSK": 0.7, "DET": 0.85}
    },
    "Creative": {
        "riasec": [2, 3, 9, 5, 5, 4],
        "latent": {"TEC": 0.35, "LOG": 0.5, "AUT": 0.55, "ALT": 0.8, "AES": 0.92, "FIN": 0.35, "RSK": 0.6, "DET": 0.6}
    },
    "People": {
        "riasec": [1, 3, 6, 9, 5, 3],
        "latent": {"TEC": 0.3, "LOG": 0.4, "AUT": 0.55, "ALT": 0.9, "AES": 0.7, "FIN": 0.4, "RSK": 0.4, "DET": 0.55}
    },
    "Health": {
        "riasec": [2, 4, 5, 8, 4, 3],
        "latent": {"TEC": 0.55, "LOG": 0.7, "AUT": 0.6, "ALT": 0.75, "AES": 0.65, "FIN": 0.35, "RSK": 0.5, "DET": 0.75}
    },
    "Science": {
        "riasec": [2, 9, 3, 4, 5, 3],
        "latent": {"TEC": 0.85, "LOG": 0.9, "AUT": 0.6, "ALT": 0.4, "AES": 0.25, "FIN": 0.4, "RSK": 0.55, "DET": 0.8}
    },
    "Engineering": {
        "riasec": [2, 8, 2, 3, 6, 3],
        "latent": {"TEC": 0.92, "LOG": 0.88, "AUT": 0.75, "ALT": 0.2, "AES": 0.2, "FIN": 0.45, "RSK": 0.65, "DET": 0.85}
    },
    "Design": {
        "riasec": [2, 3, 8, 5, 4, 4],
        "latent": {"TEC": 0.45, "LOG": 0.55, "AUT": 0.65, "ALT": 0.82, "AES": 0.9, "FIN": 0.35, "RSK": 0.55, "DET": 0.65}
    },
    "Public": {
        "riasec": [2, 7, 3, 6, 6, 5],
        "latent": {"TEC": 0.5, "LOG": 0.75, "AUT": 0.65, "ALT": 0.75, "AES": 0.55, "FIN": 0.5, "RSK": 0.5, "DET": 0.7}
    }
}

CAREER_CATALOG = []
for title, category, degree, job_zone in CAREER_CATALOG_TEMPLATE:
    profile = CATEGORY_PROFILE_MAP.get(category, CATEGORY_PROFILE_MAP["Business"])
    CAREER_CATALOG.append({
        "title": title,
        "category": category,
        "recommended_degree": degree,
        "job_zone": job_zone,
        "honest_challenge": f"{category} roles require steady focus, experimentation, and real-world accountability.",
        "riasec": profile["riasec"],
        "trait_profile": profile["latent"],
        "mobility_req": 0.6 if category in ["Tech", "Engineering", "Health", "Science"] else 0.4,
        "power_req": 0.7 if category in ["Business", "Finance", "Public"] else 0.5
    })

def _vector_norm(v: List[float]) -> float:
    return math.sqrt(sum(x * x for x in v))


def _normalize_vector(v: List[float]) -> List[float]:
    norm = _vector_norm(v)
    if norm == 0:
        return [0.0] * len(v)
    return [x / norm for x in v]


def _dot_product(a: List[float], b: List[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    if not a or not b:
        return 0.0
    a_norm = _vector_norm(a)
    b_norm = _vector_norm(b)
    if a_norm == 0 or b_norm == 0:
        return 0.0
    return float(_dot_product(a, b) / (a_norm * b_norm))

def score_career_profile(career: Dict, latent_profile: Dict, riasec: Dict, feasibility: Dict) -> float:
    trait_weights = career.get("trait_profile", {})
    if not trait_weights:
        return 0.0

    trait_scores = []
    for trait, expected_value in trait_weights.items():
        actual_value = latent_profile.get(trait, 0.5)
        trait_scores.append(1.0 - abs(actual_value - expected_value))

    latent_alignment = sum(trait_scores) / len(trait_scores)
    riasec_user = [riasec.get(k, 5.0) for k in ["R", "I", "A", "S", "E", "C"]]
    riasec_match = _cosine_similarity(riasec_user, career.get("riasec", [5, 5, 5, 5, 5, 5]))

    viability = 1.0
    mobility = feasibility.get("Geographic_Mobility", 1.0)
    funding = feasibility.get("Capital_Liquidity", 1.0)
    if mobility < 0.4 and career.get("mobility_req", 0.6) > 0.7:
        viability -= 0.25
    if funding < 0.4 and career.get("job_zone", 5) >= 5:
        viability -= 0.25
    viability = max(0.0, viability)

    return round((latent_alignment * 0.55) + (riasec_match * 0.35) + (viability * 0.1), 4)

def generate_career_predictions(latent_profile: Dict, riasec: Dict, identity: Dict, feasibility: Dict) -> List[Dict]:
    results = []
    for idx, career in enumerate(CAREER_CATALOG):
        score = score_career_profile(career, latent_profile, riasec, feasibility)
        results.append({"cluster_id": idx, "score": score})
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:10]

def _format_career_meta(cluster_id: int) -> Dict:
    if 0 <= cluster_id < len(CAREER_CATALOG):
        return CAREER_CATALOG[cluster_id]
    return {
        "title": f"Career Path {cluster_id}",
        "recommended_degree": "General undergraduate / honours degree",
        "job_zone": 4,
        "honest_challenge": "This is a generalized path recommendation."
    }

def reconcile_results(ann_predictions: List[Dict], feasibility: Dict, identity: Dict, latent_profile: Dict = None, riasec: Dict = None) -> Dict:
    """
    Refines predictions using O*NET multi-stage matchmaking if database is available,
    otherwise falls back to standard career library recommendations.
    """
    db_path = os.path.join(DATA_DIR, "onet_database.db")
    
    # Fallback to catalog logic if SQLite DB is missing or profiles are missing
    if not os.path.exists(db_path) or not latent_profile or not riasec:
        mobility = feasibility.get("Geographic_Mobility", 1.0)
        funding = feasibility.get("Capital_Liquidity", 1.0)
        ego_drive = identity.get("x", 0.0)

        refined = []
        for pred in ann_predictions:
            cluster_id = pred["cluster_id"]
            career = _format_career_meta(cluster_id)
            status = "Optimal"
            pivot_notes = "This recommendation is aligned with your core profile."

            if mobility < 0.3 and career.get("mobility_req", 0.6) > 0.7:
                status = "Infeasible"
                pivot_notes = "This path asks for mobility that may not match your current context."
                continue
            if funding < 0.3 and career.get("job_zone", 5) >= 5:
                status = "Pivot"
                pivot_notes = "This path may require higher investment; consider a related role with lower cost."
            if ego_drive < 0.2 and career.get("power_req", 0.7) > 0.8:
                status = "High-Risk"
                pivot_notes = "High-power roles may lead to burnout without stronger ego-orientation."

            refined.append({
                "career": career["title"],
                "confidence_score": pred["score"],
                "feasibility_status": status,
                "pivot_notes": career["honest_challenge"]
            })
        refined.sort(key=lambda x: x["confidence_score"], reverse=True)
        return {"refined_matches": refined[:3]}

    # O*NET-based multi-stage matchmaking
    # NOTE: The occupations table has no RIASEC columns.
    # We derive RIASEC-proxy scores from work_styles and work_values per occupation.
    r_vector = riasec.get("riasec_vector", {"R": 5, "I": 5, "A": 5, "S": 5, "E": 5, "C": 5})
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    r_user = [
        r_vector.get("R", 5.0),
        r_vector.get("I", 5.0),
        r_vector.get("A", 5.0),
        r_vector.get("S", 5.0),
        r_vector.get("E", 5.0),
        r_vector.get("C", 5.0)
    ]
    r_user_norm = _normalize_vector(r_user)
    
    # Fetch all occupations (basic info only)
    cursor.execute("SELECT soc_code, title, description, job_zone FROM occupations")
    rows = cursor.fetchall()
    
    # Pre-load work_styles and work_values for RIASEC proxy derivation
    cursor.execute("SELECT soc_code, element_name, impact FROM work_styles")
    all_ws = {}
    for sc, el, imp in cursor.fetchall():
        all_ws.setdefault(sc, {})[el] = imp if imp is not None else 0.0
    
    cursor.execute("SELECT soc_code, element_name, extent FROM work_values")
    all_wv = {}
    for sc, el, ext in cursor.fetchall():
        all_wv.setdefault(sc, {})[el] = ext if ext is not None else 3.0
    
    # Holland-type RIASEC proxy mappings from work_styles/work_values
    def derive_riasec(soc_code):
        ws = all_ws.get(soc_code, {})
        wv = all_wv.get(soc_code, {})
        r = (ws.get("Dependability", 0) + ws.get("Attention to Detail", 0)) / 2.0
        i = (ws.get("Analytical Thinking", 0) + ws.get("Innovation", 0)) / 2.0
        a = (ws.get("Innovation", 0) + ws.get("Independence", 0)) / 2.0
        s = (ws.get("Concern for Others", 0) + ws.get("Social Orientation", 0) + ws.get("Cooperation", 0)) / 3.0
        e = (ws.get("Leadership", 0) + ws.get("Initiative", 0) + wv.get("Achievement", 3.0) / 7.0 * 3.0) / 3.0
        c = (ws.get("Attention to Detail", 0) + ws.get("Dependability", 0) + ws.get("Integrity", 0)) / 3.0
        # Normalize to 1-10 scale (work_styles impact is roughly -1.42 to 3.0)
        def norm(v): return max(1.0, min(10.0, (v + 1.5) * 2.0 + 1.0))
        return [norm(r), norm(i), norm(a), norm(s), norm(e), norm(c)]
    
    scored_occupations = []
    for row in rows:
        soc_code, title, description, job_zone = row
        r_vals = derive_riasec(soc_code)
        r_occ_norm = _normalize_vector(r_vals)
        
        cos_sim = float(_dot_product(r_user_norm, r_occ_norm))
        scored_occupations.append({
            "soc_code": soc_code,
            "title": title,
            "description": description,
            "job_zone": job_zone if job_zone is not None else 4,
            "riasec_score": cos_sim,
            "realistic": r_vals[0],
            "investigative": r_vals[1],
            "artistic": r_vals[2],
            "social": r_vals[3],
            "enterprising": r_vals[4],
            "conventional": r_vals[5]
        })
        
    scored_occupations.sort(key=lambda x: x["riasec_score"], reverse=True)
    top_100 = scored_occupations[:100]
    
    soc_codes = [x["soc_code"] for x in top_100]
    placeholders = ",".join("?" for _ in soc_codes)
    
    cursor.execute(f"SELECT soc_code, element_name, importance FROM skills WHERE soc_code IN ({placeholders})", soc_codes)
    skills_rows = cursor.fetchall()
    skills_map = {}
    for sc, el, imp in skills_rows:
        skills_map.setdefault(sc, {})[el] = imp
        
    cursor.execute(f"SELECT soc_code, element_name, importance FROM abilities WHERE soc_code IN ({placeholders})", soc_codes)
    abilities_rows = cursor.fetchall()
    abilities_map = {}
    for sc, el, imp in abilities_rows:
        abilities_map.setdefault(sc, {})[el] = imp
        
    cursor.execute(f"SELECT soc_code, element_name, impact FROM work_styles WHERE soc_code IN ({placeholders})", soc_codes)
    ws_rows = cursor.fetchall()
    ws_map = {}
    for sc, el, imp in ws_rows:
        ws_map.setdefault(sc, {})[el] = imp
        
    cursor.execute(f"SELECT soc_code, element_name, extent FROM work_values WHERE soc_code IN ({placeholders})", soc_codes)
    wv_rows = cursor.fetchall()
    wv_map = {}
    for sc, el, imp in wv_rows:
        wv_map.setdefault(sc, {})[el] = imp
        
    for occ in top_100:
        sc = occ["soc_code"]
        occ_skills = skills_map.get(sc, {})
        occ_abilities = abilities_map.get(sc, {})
        occ_ws = ws_map.get(sc, {})
        occ_wv = wv_map.get(sc, {})
        
        scores = []
        
        # 1. Technical / Analytical Rigour
        tec_user = latent_profile.get("TEC", 0.5)
        tech_skills = ["Technology Design", "Programming", "Operations Analysis", "Troubleshooting"]
        tech_vals = [occ_skills.get(ts, 1.0) for ts in tech_skills]
        avg_tech_occ = sum(tech_vals) / len(tech_vals)
        norm_tech_occ = (avg_tech_occ - 1.0) / 4.0
        scores.append(1.0 - abs(tec_user - norm_tech_occ))
        
        log_user = latent_profile.get("LOG", 0.5)
        log_skills = ["Mathematics", "Science", "Critical Thinking"]
        log_vals = [occ_skills.get(ls, 1.0) for ls in log_skills]
        avg_log_occ = sum(log_vals) / len(log_vals)
        norm_log_occ = (avg_log_occ - 1.0) / 4.0
        scores.append(1.0 - abs(log_user - norm_log_occ))
        
        # 2. Altruism (ALT)
        alt_user = latent_profile.get("ALT", 0.5)
        alt_ws = ["Concern for Others", "Social Orientation", "Cooperation"]
        alt_vals = [occ_ws.get(aw, 0.0) for aw in alt_ws]
        avg_alt_occ = sum(alt_vals) / len(alt_vals)
        norm_alt_occ = (avg_alt_occ + 1.42) / 4.42
        scores.append(1.0 - abs(alt_user - norm_alt_occ))
        
        # 3. Autonomy (AUT)
        aut_user = latent_profile.get("AUT", 0.5)
        aut_val_occ = occ_wv.get("Independence", 3.0)
        norm_aut_val = (aut_val_occ - 1.0) / 6.0
        aut_style_occ = occ_ws.get("Independence", 0.8)
        norm_aut_style = (aut_style_occ + 1.42) / 4.42
        norm_aut_occ = (norm_aut_val + norm_aut_style) / 2.0
        scores.append(1.0 - abs(aut_user - norm_aut_occ))
        
        # 4. Detail Orientation (DET)
        det_user = latent_profile.get("DET", 0.5)
        det_style = occ_ws.get("Attention to Detail", 0.8)
        norm_det_occ = (det_style + 1.42) / 4.42
        scores.append(1.0 - abs(det_user - norm_det_occ))
        
        # 5. Ambiguity Tolerance (AMB)
        amb_user = latent_profile.get("AMB", 0.5)
        amb_style = occ_ws.get("Adaptability/Flexibility", 0.8)
        norm_amb_occ = (amb_style + 1.42) / 4.42
        scores.append(1.0 - abs(amb_user - norm_amb_occ))
        
        # 6. Physical Work (PHY)
        phy_user = latent_profile.get("PHY", 0.5)
        phy_ab = ["Static Strength", "Stamina", "Manual Dexterity"]
        phy_vals = [occ_abilities.get(pa, 1.0) for pa in phy_ab]
        avg_phy_occ = sum(phy_vals) / len(phy_vals)
        norm_phy_occ = (avg_phy_occ - 1.0) / 4.0
        scores.append(1.0 - abs(phy_user - norm_phy_occ))
        
        latent_alignment = sum(scores) / len(scores)
        occ["alignment_score"] = 0.5 * occ["riasec_score"] + 0.5 * latent_alignment
        
    top_100.sort(key=lambda x: x["alignment_score"], reverse=True)
    top_20 = top_100[:20]
    
    mobility = feasibility.get("Geographic_Mobility", 1.0)
    funding = feasibility.get("Capital_Liquidity", 1.0)
    ego_drive = identity.get("x", 0.5)
    
    refined = []
    for occ in top_20:
        soc_code = occ["soc_code"]
        title = occ["title"]
        job_zone = occ["job_zone"]
        score = occ["alignment_score"]
        
        status = "Optimal"
        pivot_notes = "Highly aligned with your core psychometric and RIASEC profile."
        
        if funding < 0.4 and job_zone >= 5:
            status = "Pivot"
            pivot_notes = f"Requires extensive postgraduate studies (Job Zone {job_zone}). Recommended to explore high-ROI pathways."
            
        ent_rating = occ.get("enterprising", 3.5)
        if ego_drive < 0.35 and ent_rating > 5.5:
            status = "High-Risk"
            pivot_notes = "High-power management role matches interests but low Ego Focus suggests potential for burnout."
            
        cursor.execute("SELECT alternate_title FROM alternate_titles WHERE soc_code = ? ORDER BY rowid LIMIT 3", (soc_code,))
        alt_titles = [r[0] for r in cursor.fetchall()]
        
        chosen_career = title
        if alt_titles:
            chosen_career = f"{title} ({alt_titles[0]})"
            
        refined.append({
            "career": chosen_career,
            "confidence_score": round(score, 4),
            "feasibility_status": status,
            "pivot_notes": pivot_notes
        })
        
    conn.close()
    return {"refined_matches": refined[:3]}

def recommend_10th_stream(latent_profile: Dict, riasec: Dict, identity: Dict) -> Dict:
    """
    Heuristic-based logic to recommend a stream for 10th grade students.
    Streams: Science, Commerce, Humanities/Arts.
    """
    log_rigour = latent_profile.get("LOG", 0.5)
    tech_aff = latent_profile.get("TEC", 0.5)
    fin_drive = latent_profile.get("FIN", 0.5)
    detail_orig = latent_profile.get("DET", 0.5)
    altruism = latent_profile.get("ALT", 0.5)
    aesthetic = latent_profile.get("AES", 0.5)
    
    r_i_a_s_e_c = riasec.get("riasec_vector", {})
    investigative = r_i_a_s_e_c.get("I", 5)
    conventional = r_i_a_s_e_c.get("C", 5)
    social = r_i_a_s_e_c.get("S", 5)
    artistic = r_i_a_s_e_c.get("A", 5)

    science_score = (log_rigour * 2) + (tech_aff * 1.5) + (investigative * 0.5)
    commerce_score = (fin_drive * 2) + (detail_orig * 1.5) + (conventional * 0.5)
    humanities_score = (altruism * 2) + (aesthetic * 1.5) + (social * 0.5) + (artistic * 0.5)

    scores = {
        "Science": science_score,
        "Commerce": commerce_score,
        "Humanities": humanities_score
    }
    recommended_stream = max(scores, key=scores.get)

    stream_data = {
        "Science": {
            "subjects": ["Physics", "Chemistry", "Mathematics", "Biology / Computer Science"],
            "skills": ["Analytical Reasoning", "Problem Solving", "Technical Aptitude"],
            "justification": "Your high scores in Logical Rigour and Investigative traits suggest you thrive in structured, research-oriented environments where you can decode how the world works."
        },
        "Commerce": {
            "subjects": ["Accountancy", "Business Studies", "Economics", "Applied Math"],
            "skills": ["Numerical Proficiency", "Strategic Planning", "Organizational Efficiency"],
            "justification": "Your strong Financial Drive and Detail Orientation point toward a career in value creation and resource management. You have the discipline for high-stakes business environments."
        },
        "Humanities": {
            "subjects": ["Psychology", "Sociology", "Political Science", "History / Literature"],
            "skills": ["Empathetic Communication", "Critical Theory", "Creative Expression"],
            "justification": "Your Altruism and Aesthetic Sensitivity scores indicate a deep interest in human systems, culture, and social impact. You excel at understanding the 'Why' behind human behavior."
        }
    }

    return {
        "recommended_stream": recommended_stream,
        "stream_details": stream_data[recommended_stream]
    }
