"""
Phase 1 questions data — loaded from assessment_data/cards_10th.json (10th grade cards).
'questions' is the base/default card set used in the assessment.
"""
import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_DATA_PATH = os.path.join(_HERE, "..", "assessment_data", "cards_10th.json")

with open(_DATA_PATH, "r", encoding="utf-8") as _f:
    questions = json.load(_f)
