from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

from .models import FeatureWindow


@dataclass(slots=True)
class BaselineModel:
    feature_keys: list[str]
    baseline: dict[str, float]
    threshold: float = 0.45

    def to_dict(self) -> dict:
        return {
            "feature_keys": self.feature_keys,
            "baseline": {key: round(value, 6) for key, value in self.baseline.items()},
            "threshold": self.threshold,
        }

    @classmethod
    def from_dict(cls, payload: dict) -> "BaselineModel":
        return cls(
            feature_keys=list(payload["feature_keys"]),
            baseline={key: float(value) for key, value in payload["baseline"].items()},
            threshold=float(payload.get("threshold", 0.45)),
        )


class BaselineScorer:
    """Simple baseline distance scorer for the MVP offline path."""

    def __init__(self, model: BaselineModel | None = None) -> None:
        self.model = model

    @property
    def baseline(self) -> dict[str, float]:
        return self.model.baseline if self.model else {}

    def fit(self, feature_windows: list[FeatureWindow], threshold: float = 0.45) -> BaselineModel:
        if not feature_windows:
            raise ValueError("baseline fit requires at least one feature window")

        feature_keys = sorted(feature_windows[0].values)
        baseline = {
            key: sum(window.values[key] for window in feature_windows) / len(feature_windows)
            for key in feature_keys
        }
        self.model = BaselineModel(
            feature_keys=feature_keys,
            baseline=baseline,
            threshold=threshold,
        )
        return self.model

    def load_model(self, path: str | Path) -> BaselineModel:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        self.model = BaselineModel.from_dict(payload)
        return self.model

    def save_model(self, path: str | Path) -> None:
        if self.model is None:
            raise ValueError("baseline scorer must be fit before saving")
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(self.model.to_dict(), indent=2),
            encoding="utf-8",
        )

    def score(self, feature_window: FeatureWindow) -> tuple[float, float]:
        if self.model is None:
            raise ValueError("baseline scorer must be fit or loaded before scoring")

        distances: list[float] = []
        for key in self.model.feature_keys:
            baseline_value = self.model.baseline[key]
            observed_value = feature_window.values.get(key, 0.0)
            scale = max(abs(baseline_value), 1.0)
            distances.append(abs(observed_value - baseline_value) / scale)

        avg_distance = sum(distances) / len(distances)
        score = min(1.0, avg_distance / 2.0)
        confidence = min(1.0, math.sqrt(avg_distance / 2.0))
        return score, confidence


def verdict_for_score(score: float, threshold: float = 0.45) -> str:
    return "anomalous" if score >= threshold else "normal"
