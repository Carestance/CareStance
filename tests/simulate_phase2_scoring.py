
import random
import json
import sys
import os

# Add the parent directory to sys.path to import from app.data
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.data.phase2_questions_v2 import phase2_questions

def simulate_scoring(runs=100):
    archetypes = [
        "Focused Specialist",
        "Adaptive Explorer",
        "Dynamic Generalist",
        "Quiet Explorer",
        "Strategic Builder",
        "Visionary Leader"
    ]
    
    results = {a: 0 for a in archetypes}
    
    for _ in range(runs):
        selected_questions = random.sample(phase2_questions, 10)
        # Mocking user answers: Let's say user always picks the first option (A)
        # which usually maps to Focused Specialist or Strategic Builder etc.
        
        archetype_scores = {a: 0 for a in archetypes}
        
        for q in selected_questions:
            # Pick a random option for each question
            selected_option = random.choice(q["options"])
            tag = selected_option.get("tag")
            if tag in archetype_scores:
                archetype_scores[tag] += 1
        
        # Tie-breaking logic from app/main.py:
        # sorted_scores = sorted(archetype_scores.items(), key=lambda x: (-x[1], x[0]))
        # final_profile = sorted_scores[0][0]
        sorted_scores = sorted(archetype_scores.items(), key=lambda x: (-x[1], x[0]))
        final_profile = sorted_scores[0][0]
        results[final_profile] += 1
        
    print(f"Simulation Results over {runs} runs with RANDOM answers:")
    print(json.dumps(results, indent=2))

def test_deterministic_bias():
    print("\nTesting Deterministic Bias (Tie-breaking):")
    # If two archetypes have the same score, the one that comes first alphabetically (x[0]) wins?
    # sorted_scores = sorted(archetype_scores.items(), key=lambda x: (-x[1], x[0]))
    # -x[1] means descending score.
    # x[0] means ascending name. So 'Adaptive Explorer' wins over 'Focused Specialist' if scores are equal.
    
    archetype_scores = {
        "Focused Specialist": 5,
        "Adaptive Explorer": 5,
        "Dynamic Generalist": 0,
        "Quiet Explorer": 0,
        "Strategic Builder": 0,
        "Visionary Leader": 0
    }
    sorted_scores = sorted(archetype_scores.items(), key=lambda x: (-x[1], x[0]))
    print(f"Tie-break between Focused (5) and Adaptive (5): {sorted_scores[0][0]}")
    
    archetype_scores = {
        "Visionary Leader": 5,
        "Strategic Builder": 5,
        "Dynamic Generalist": 0,
        "Quiet Explorer": 0,
        "Adaptive Explorer": 0,
        "Focused Specialist": 0
    }
    sorted_scores = sorted(archetype_scores.items(), key=lambda x: (-x[1], x[0]))
    print(f"Tie-break between Visionary (5) and Strategic (5): {sorted_scores[0][0]}")

def analyze_tag_distribution():
    from collections import Counter
    all_tags = []
    for q in phase2_questions:
        for opt in q["options"]:
            all_tags.append(opt["tag"])
    
    distribution = Counter(all_tags)
    print("\nTag Distribution in the 110-question bank:")
    print(json.dumps(dict(distribution), indent=2))
    
    # Also check distribution of options per question (average)
    total_options = len(all_tags)
    avg_options = total_options / len(phase2_questions)
    print(f"\nAverage options per question: {avg_options:.2f}")

if __name__ == "__main__":
    analyze_tag_distribution()
    simulate_scoring()
    test_deterministic_bias()
