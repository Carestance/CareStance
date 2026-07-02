import re
from .feature_dictionary import FEATURE_RULES


class FeatureExtractor:
    def __init__(self):
        self.rules = FEATURE_RULES
        self.base_floor = 0.05  # ensures NO zero output

    def preprocess(self, text):
        text = text.lower()
        text = re.sub(r"[^a-z\s]", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text

    def extract(self, text):
        text = self.preprocess(text)
        scores = {}

        for feature, keywords in self.rules.items():
            total_weight = sum(keywords.values())
            match_score = 0.0

            for word, weight in keywords.items():
                if word in text:
                    match_score += weight

            evidence = match_score / total_weight if total_weight > 0 else 0.0

            # NEVER ZERO OUTPUT
            final_score = self.base_floor + (1 - self.base_floor) * evidence
            scores[feature] = round(min(1.0, final_score), 4)

        return scores
