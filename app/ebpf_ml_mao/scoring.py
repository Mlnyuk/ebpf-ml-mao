from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path

from .models import FeatureWindow

MODEL_SCHEMA_V1 = "v1"
MODEL_SCHEMA_V2 = "v2"
SUPPORTED_SCHEMA_VERSIONS = {MODEL_SCHEMA_V1, MODEL_SCHEMA_V2}
SUPPORTED_MODEL_TYPES = {"baseline", "zscore"}


@dataclass(slots=True)
class BaselineModel:
    feature_keys: list[str]
    threshold: float = 0.45
    schema_version: str = MODEL_SCHEMA_V2
    model_type: str = "baseline"
    baseline: dict[str, float] = field(default_factory=dict)
    mean: dict[str, float] = field(default_factory=dict)
    std: dict[str, float] = field(default_factory=dict)

    def validate(self) -> None:
        if self.schema_version not in SUPPORTED_SCHEMA_VERSIONS:
            raise ValueError(f"unsupported schema_version: {self.schema_version}")
        if self.model_type not in SUPPORTED_MODEL_TYPES:
            raise ValueError(f"unsupported model_type: {self.model_type}")
        if not (0 < float(self.threshold) < 1):
            raise ValueError(f"threshold must be between 0 and 1, got {self.threshold}")

    def to_dict(self) -> dict:
        payload = {
            "schema_version": self.schema_version,
            "model_type": self.model_type,
            "feature_keys": self.feature_keys,
            "threshold": self.threshold,
        }
        if self.baseline:
            payload["baseline"] = {
                key: round(value, 6) for key, value in self.baseline.items()
            }
        if self.mean:
            payload["mean"] = {key: round(value, 6) for key, value in self.mean.items()}
        if self.std:
            payload["std"] = {key: round(value, 6) for key, value in self.std.items()}
        return payload

    @classmethod
    def from_dict(cls, payload: dict) -> "BaselineModel":
        schema_version = str(payload.get("schema_version", MODEL_SCHEMA_V1))
        model_type = str(payload.get("model_type", "baseline"))
        model = cls(
            feature_keys=list(payload["feature_keys"]),
            threshold=float(payload.get("threshold", 0.45)),
            schema_version=schema_version,
            model_type=model_type,
            baseline={key: float(value) for key, value in payload.get("baseline", {}).items()},
            mean={key: float(value) for key, value in payload.get("mean", {}).items()},
            std={key: float(value) for key, value in payload.get("std", {}).items()},
        )
        model.validate()
        return model


class BaselineScorer:
    """Versioned scorer with lightweight model variants for the MVP."""

    def __init__(
        self,
        model: BaselineModel | None = None,
        *,
        model_type: str = "baseline",
    ) -> None:
        if model_type not in SUPPORTED_MODEL_TYPES:
            raise ValueError(f"unsupported model_type: {model_type}")
        self.model = model
        self.model_type = model.model_type if model is not None else model_type

    @property
    def baseline(self) -> dict[str, float]:
        if self.model is None:
            return {}
        return self.model.baseline or self.model.mean

    def fit(
        self,
        feature_windows: list[FeatureWindow],
        threshold: float = 0.45,
        *,
        model_type: str | None = None,
    ) -> BaselineModel:
        if not feature_windows:
            raise ValueError("baseline fit requires at least one feature window")

        selected_model_type = model_type or self.model_type
        if selected_model_type not in SUPPORTED_MODEL_TYPES:
            raise ValueError(f"unsupported model_type: {selected_model_type}")
        if not (0 < float(threshold) < 1):
            raise ValueError(f"threshold must be between 0 and 1, got {threshold}")

        feature_keys = sorted(feature_windows[0].values)
        if selected_model_type == "baseline":
            baseline = {
                key: sum(window.values[key] for window in feature_windows) / len(feature_windows)
                for key in feature_keys
            }
            self.model = BaselineModel(
                feature_keys=feature_keys,
                threshold=threshold,
                schema_version=MODEL_SCHEMA_V2,
                model_type="baseline",
                baseline=baseline,
            )
        else:
            mean = {
                key: sum(window.values[key] for window in feature_windows) / len(feature_windows)
                for key in feature_keys
            }
            std = {}
            for key in feature_keys:
                variance = sum(
                    (window.values[key] - mean[key]) ** 2 for window in feature_windows
                ) / len(feature_windows)
                std[key] = math.sqrt(variance)
            self.model = BaselineModel(
                feature_keys=feature_keys,
                threshold=threshold,
                schema_version=MODEL_SCHEMA_V2,
                model_type="zscore",
                mean=mean,
                std=std,
            )
        self.model.validate()
        self.model_type = self.model.model_type
        return self.model

    def load_model(self, path: str | Path) -> BaselineModel:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        self.model = BaselineModel.from_dict(payload)
        self.model_type = self.model.model_type
        return self.model

    def save_model(self, path: str | Path) -> None:
        if self.model is None:
            raise ValueError("baseline scorer must be fit before saving")
        self.model.validate()
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(self.model.to_dict(), indent=2),
            encoding="utf-8",
        )

    def score(self, feature_window: FeatureWindow) -> tuple[float, float]:
        if self.model is None:
            raise ValueError("baseline scorer must be fit or loaded before scoring")
        missing_keys = [
            key for key in self.model.feature_keys if key not in feature_window.values
        ]
        if missing_keys:
            raise ValueError(f"feature window missing keys: {', '.join(missing_keys)}")
        if self.model.model_type == "baseline":
            return self._score_baseline(feature_window)
        if self.model.model_type == "zscore":
            return self._score_zscore(feature_window)
        raise ValueError(f"unsupported model_type: {self.model.model_type}")

    def _score_baseline(self, feature_window: FeatureWindow) -> tuple[float, float]:
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

    def _score_zscore(self, feature_window: FeatureWindow) -> tuple[float, float]:
        z_values: list[float] = []
        for key in self.model.feature_keys:
            mean = self.model.mean[key]
            std = self.model.std.get(key, 0.0)
            safe_std = std if std > 0 else 1.0
            observed_value = feature_window.values.get(key, 0.0)
            z_values.append(abs(observed_value - mean) / safe_std)
        avg_z = sum(z_values) / len(z_values)
        score = min(1.0, avg_z / 3.0)
        confidence = min(1.0, math.sqrt(score))
        return score, confidence


def verdict_for_score(score: float, threshold: float = 0.45) -> str:
    return "anomalous" if score >= threshold else "normal"
