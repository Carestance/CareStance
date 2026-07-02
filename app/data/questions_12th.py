"""
Phase assessment questions for 12th grade — loaded from assessment_data/cards_12th.json.
"""
import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_DATA_PATH = os.path.join(_HERE, "..", "assessment_data", "cards_12th.json")

with open(_DATA_PATH, "r", encoding="utf-8") as _f:
    questions_12th = json.load(_f)
