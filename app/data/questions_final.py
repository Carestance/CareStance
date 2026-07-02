"""
Phase 4 final stream assessment tasks — loaded from assessment_data/phase4_tasks.json.
Exports: all_questions, section_a_questions, section_b_questions,
         section_c_questions, section_d_questions
Tasks are split by personality 'nature': Extrovert, Introvert, Ambivert.
section_a = Goal tasks, section_b = Non-Goal tasks,
section_c = Extrovert tasks, section_d = Introvert tasks (for compatibility).
"""
import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_DATA_PATH = os.path.join(_HERE, "..", "assessment_data", "phase4_tasks.json")

with open(_DATA_PATH, "r", encoding="utf-8") as _f:
    all_questions = json.load(_f)

# Segment by goal_status and nature
section_a_questions = [q for q in all_questions if q.get("goal_status") == "Goal"]
section_b_questions = [q for q in all_questions if q.get("goal_status") == "Non-Goal"]
section_c_questions = [q for q in all_questions if q.get("nature") == "Extrovert"]
section_d_questions = [q for q in all_questions if q.get("nature") == "Introvert"]
