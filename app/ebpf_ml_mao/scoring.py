from __future__ import annotations

import math

from .models import FeatureWindow


class BaselineScorer:
    """Simple baseline distance scorer for the MVP offline path."""

    def __init__(self) -> None:
        self.baseline: dict[str, float] = {}

    def fit(self, feature_windows: list[FeatureWindow]) -> None:
        if not feature_windows:
            raise ValueError("baseline fit requires at least one feature window")

        all_keys = sorted(feature_windows[0].values)
        self.baseline = {
            key: sum(window.values[key] for window in feature_windows) / len(feature_windows)
            for key in all_keys
        }

    def score(self, feature_window: FeatureWindow) -> tuple[float, float]:
        if not self.baseline:
            raise ValueError("baseline scorer must be fit before scoring")

        distances: list[float] = []
        for key, baseline_value in self.baseline.items():
            observed_value = feature_window.values.get(key, 0.0)
            scale = max(abs(baseline_value), 1.0)
            distances.append(abs(observed_value - baseline_value) / scale)

        avg_distance = sum(distances) / len(distances)
        score = min(1.0, avg_distance / 2.0)
        confidence = min(1.0, math.sqrt(avg_distance / 2.0))
        return score, confidence


def verdict_for_score(score: float, threshold: float = 0.45) -> str:
    return "anomalous" if score >= threshold else "normal"

