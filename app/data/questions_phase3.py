"""
Phase 3 MCQ scenarios — loaded from assessment_data/phase3_mcqs.json.
CATEGORY_SCENARIOS_MAP groups questions by their proxy_target dimension.
"""
import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_DATA_PATH = os.path.join(_HERE, "..", "assessment_data", "phase3_mcqs.json")

with open(_DATA_PATH, "r", encoding="utf-8") as _f:
    _phase3_questions = json.load(_f)

# Build a map: proxy_target -> list of question dicts
CATEGORY_SCENARIOS_MAP: dict = {}
for _q in _phase3_questions:
    _cat = _q.get("proxy_target", "Unknown")
    CATEGORY_SCENARIOS_MAP.setdefault(_cat, []).append(_q)
