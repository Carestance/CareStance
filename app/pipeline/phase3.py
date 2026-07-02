"""
phase3.py — Situation-Based Assessment Pipeline
-------------------------------------------------
Handles Phase 3 of the flowchart:
Scenario → 4 MCQ Options → Decision Selection → Personality & Behavior Analysis

What it does:
1. Takes the student's MCQ responses
2. Maps each answer to personality/work-style dimensions
3. Generates a behavior profile
4. Merges Phase 3 scores into the student profile

Note: Actual MCQ questions come from the founder's "Phase 3 MCQs.json".
Here, we are implementing the scoring logic.
"""

from __future__ import annotations

# ─── MCQ Answer → Work Style Dimension Mapping ───────────────────────────────
# Each MCQ scenario has 4 options (A/B/C/D)
# Each option indicates a different personality trait

# FORMAT: scenario_id → { option → { WS_column: weight } }
# Positive weight = strong indicator of that trait
# Negative weight = indicates absence of that trait

SCENARIO_SCORING_MAP: dict[str, dict[str, dict[str, float]]] = {
    # Example Scenario 1: No one is working in the team
    "scenario_leadership": {
        "A": {  # Takes initialization of work by self
            "WS_Leadership Orientation": 0.9,
            "WS_Initiative": 0.85,
            "WS_Achievement Orientation": 0.7,
        },
        "B": {  # Completing the work Quietly 
            "WS_Dependability": 0.85,
            "WS_Perseverance": 0.8,
            "WS_Humility": 0.7,
        },
        "C": {  # Reporting to the manager
            "WS_Integrity": 0.8,
            "WS_Cautiousness": 0.75,
            "WS_Cooperation": 0.6,
        },
        "D": {  # Try to Talk with Team member
            "WS_Social Orientation": 0.85,
            "WS_Empathy": 0.8,
            "WS_Cooperation": 0.75,
        },
    },

    # Example Scenario 2: The deadline is tight and the work is incomplete
    "scenario_stress": {
        "A": {  # Completes the work by putting in extra time
            "WS_Perseverance": 0.9,
            "WS_Achievement Orientation": 0.85,
            "WS_Stress Tolerance": 0.7,
        },
        "B": {  # Prioritizes tasks and leaves some parts incomplete
            "WS_Adaptability": 0.85,
            "WS_Tolerance for Ambiguity": 0.8,
            "WS_Initiative": 0.6,
        },
        "C": {  # Asks for help
            "WS_Cooperation": 0.8,
            "WS_Humility": 0.75,
            "WS_Social Orientation": 0.65,
        },
        "D": {  # Asks for an extension without compromising on quality
            "WS_Integrity": 0.85,
            "WS_Cautiousness": 0.8,
            "WS_Self-Confidence": 0.65,
        },
    },

    # Example Scenario 3: Received a new creative project
    "scenario_innovation": {
        "A": {  # Immediately starts experimenting
            "WS_Innovation": 0.9,
            "WS_Initiative": 0.85,
            "WS_Tolerance for Ambiguity": 0.75,
        },
        "B": {  # First does research, then plans
            "WS_Intellectual Curiosity": 0.9,
            "WS_Attention to Detail": 0.8,
            "WS_Cautiousness": 0.7,
        },
        "C": {  # Takes ideas from the team
            "WS_Social Orientation": 0.85,
            "WS_Cooperation": 0.8,
            "WS_Empathy": 0.6,
        },
        "D": {  # Looks at existing solutions first
            "WS_Conventional": 0.8,
            "WS_Dependability": 0.7,
            "WS_Cautiousness": 0.75,
        },
    },

    # Example Scenario 4: The project failed due to someone's mistake
    "scenario_integrity": {
        "A": {  # Honestly accepts their mistake
            "WS_Integrity": 0.95,
            "WS_Sincerity": 0.9,
            "WS_Self-Control": 0.7,
        },
        "B": {  # Quietly fixes it without informing others
            "WS_Dependability": 0.8,
            "WS_Humility": 0.8,
            "WS_Perseverance": 0.7,
        },
        "C": {  # Works with the team to find a solution
            "WS_Cooperation": 0.85,
            "WS_Social Orientation": 0.8,
            "WS_Empathy": 0.75,
        },
        "D": {  # Analyzes the situation to prevent it in the future
            "WS_Intellectual Curiosity": 0.8,
            "WS_Achievement Orientation": 0.75,
            "WS_Attention to Detail": 0.8,
        },
    },

    # Example Scenario 5: Assigned a boring repetitive task
    "scenario_perseverance": {
        "A": {  # Completes it without complaining
            "WS_Dependability": 0.9,
            "WS_Perseverance": 0.9,
            "WS_Self-Control": 0.75,
        },
        "B": {  # Tries to make it interesting while doing it
            "WS_Innovation": 0.8,
            "WS_Optimism": 0.8,
            "WS_Adaptability": 0.75,
        },
        "C": {  # Negotiates with the manager for a better task
            "WS_Self-Confidence": 0.8,
            "WS_Initiative": 0.75,
            "WS_Achievement Orientation": 0.7,
        },
        "D": {  # Completes it but suggests improvements to the process
            "WS_Intellectual Curiosity": 0.8,
            "WS_Initiative": 0.7,
            "WS_Cooperation": 0.65,
        },
    },
}

# Holland RIASEC personality types that we want to infer from Phase 3
BEHAVIOR_TO_RIASEC_HINT: dict[str, dict[str, float]] = {
    "WS_Leadership Orientation": {"IT_Enterprising": 0.3},
    "WS_Innovation": {"IT_Artistic": 0.2, "IT_Investigative": 0.2},
    "WS_Empathy": {"IT_Social": 0.3},
    "WS_Intellectual Curiosity": {"IT_Investigative": 0.3},
    "WS_Dependability": {"IT_Conventional": 0.2},
    "WS_Perseverance": {"IT_Realistic": 0.15},
}


# ─── Phase 3 Main Function ────────────────────────────────────────────────────

def run_phase3(student_profile: dict, mcq_responses: list[dict]) -> dict:
    if not mcq_responses:
        return student_profile

    # 1. Har response ko score mein convert kia
    raw_behavior_scores: dict[str, list[float]] = {}

    for response in mcq_responses:
        scenario_id = response.get("scenario_id")
        selected_option = response.get("selected_option", "").upper()

        scoring = SCENARIO_SCORING_MAP.get(scenario_id, {})
        option_scores = scoring.get(selected_option, {})

        for trait, score in option_scores.items():
            if trait not in raw_behavior_scores:
                raw_behavior_scores[trait] = []
            raw_behavior_scores[trait].append(score)

    # 2. Found Average (agar ek trait multiple scenarios mein aayi)
    behavior_scores = {
        trait: round(sum(scores) / len(scores), 4)
        for trait, scores in raw_behavior_scores.items()
    }

    # 3. Phase 2 ke work_style_scores ke saath merge kia
    # Given more weight to Phase 3 (more reliable - behavior based)
    for trait, score in behavior_scores.items():
        existing = student_profile["work_style_scores"].get(trait)
        if existing is not None:
            # Blend: 70% Phase3 (behavior) + 30% Phase2 (card preference)
            student_profile["work_style_scores"][trait] = round(
                0.7 * score + 0.3 * existing, 4
            )
        else:
            student_profile["work_style_scores"][trait] = score
    student_profile["phase3_behavior_scores"] = behavior_scores

    # 4. RIASEC Hints updated by Behavior(minor refinement)
    for trait, riasec_hint in BEHAVIOR_TO_RIASEC_HINT.items():
        if trait in behavior_scores:
            trait_val = behavior_scores[trait]
            for riasec_key, weight in riasec_hint.items():
                current = student_profile["interest_scores"].get(riasec_key, 0.5)
                # Small nudge based on strong behavior signals
                nudge = weight * (trait_val - 0.5)  # Only if above average
                student_profile["interest_scores"][riasec_key] = round(
                    min(max(current + nudge, 0.0), 1.0), 4
                )

    # 5. Personality archetype classified
    student_profile["personality_archetype"] = _classify_archetype(
        student_profile["work_style_scores"],
        student_profile["interest_scores"],
    )
    return student_profile


# ─── Helper Functions ─────────────────────────────────────────────────────────

def _classify_archetype(ws_scores: dict, interest_scores: dict) -> str:
    archetypes = {
        "The Leader": (
            ws_scores.get("WS_Leadership Orientation", 0) * 0.4
            + interest_scores.get("IT_Enterprising", 0) * 0.4
            + ws_scores.get("WS_Self-Confidence", 0) * 0.2
        ),
        "The Innovator": (
            ws_scores.get("WS_Innovation", 0) * 0.4
            + interest_scores.get("IT_Artistic", 0) * 0.3
            + ws_scores.get("WS_Intellectual Curiosity", 0) * 0.3
        ),
        "The Analyst": (
            interest_scores.get("IT_Investigative", 0) * 0.5
            + ws_scores.get("WS_Attention to Detail", 0) * 0.3
            + ws_scores.get("WS_Intellectual Curiosity", 0) * 0.2
        ),
        "The Caregiver": (
            ws_scores.get("WS_Empathy", 0) * 0.5
            + interest_scores.get("IT_Social", 0) * 0.4
            + ws_scores.get("WS_Cooperation", 0) * 0.1
        ),
        "The Executor": (
            ws_scores.get("WS_Dependability", 0) * 0.4
            + interest_scores.get("IT_Conventional", 0) * 0.35
            + ws_scores.get("WS_Perseverance", 0) * 0.25
        ),
        "The Builder": (
            interest_scores.get("IT_Realistic", 0) * 0.5
            + ws_scores.get("WS_Perseverance", 0) * 0.3
            + ws_scores.get("WS_Attention to Detail", 0) * 0.2
        ),
    }
    return max(archetypes, key=archetypes.get)