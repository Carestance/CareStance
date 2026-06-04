import sys
import os
import random
import json

# Add project root to path
sys.path.append(os.getcwd())

from app.data.phase2_questions_v2 import phase2_questions

def simulate_assessment():
    # 1. Select 10 random questions
    selected = random.sample(phase2_questions, 10)
    print(f"Selected IDs: {[q['id'] for q in selected]}")
    
    # 2. Simulate answers (randomly)
    archetype_scores = {
        "Focused Specialist": 0,
        "Adaptive Explorer": 0,
        "Dynamic Generalist": 0,
        "Quiet Explorer": 0,
        "Strategic Builder": 0,
        "Visionary Leader": 0
    }
    
    for q in selected:
        opt = random.choice(q['options'])
        tag = opt['tag']
        archetype_scores[tag] += 1
        
    # 3. Determine Winner (same logic as in main.py)
    sorted_scores = sorted(archetype_scores.items(), key=lambda x: (-x[1], x[0]))
    winner = sorted_scores[0][0]
    
    print(f"Scores: {archetype_scores}")
    print(f"Winner: {winner} (Score: {sorted_scores[0][1]})")
    return winner

if __name__ == "__main__":
    print("Running 100 simulations...")
    winners = []
    for i in range(100):
        print(f"\n--- Run {i+1} ---")
        winners.append(simulate_assessment())
    
    from collections import Counter
    summary = Counter(winners)
    print("\n\n=== Final Summary ===")
    for k, v in summary.items():
        print(f"{k}: {v} times")
