"""
Phase assessment questions for Above 12th grade — same card pool as 12th but distinct variable.
Falls back to cards_12th.json (same content, different audience framing).
"""
import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_DATA_PATH = os.path.join(_HERE, "..", "assessment_data", "cards_12th.json")

with open(_DATA_PATH, "r", encoding="utf-8") as _f:
    questions_above_12th = json.load(_f)
