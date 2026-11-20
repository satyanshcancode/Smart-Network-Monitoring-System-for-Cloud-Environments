"""
Prediction Engine (ML Module)
Stability prediction using trained ML model with rule-based fallback.

Fixes applied:
  1. Model loaded via correct file paths (model_path=, scaler_path=, etc.)
  2. Loader uses joblib.load() on separate .pkl files (not pickle on a dict)
  3. extract_features() now produces all 19 features the model was trained on
  4. Stability score = predict_proba[0][stable_idx] i.e. P(stable), not wrong index [1]
"""
import numpy as np
import joblib
import os
from typing import Dict, List
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Resolve paths relative to this file so it works regardless of cwd
_HERE = os.path.dirname(os.path.abspath(__file__))
_DEFAULT_MODEL_PATH   = os.path.join(_HERE, "network_model.pkl")
_DEFAULT_SCALER_PATH  = os.path.join(_HERE, "scaler.pkl")
_DEFAULT_FEATURE_PATH = os.path.join(_HERE, "feature_names.pkl")
_DEFAULT_LABEL_PATH   = os.path.join(_HERE, "label_encoder.pkl")

# LabelEncoder sorts classes alphabetically:
# 0=congested, 1=critical, 2=degrading, 3=stable
_STABLE_CLASS_INDEX = 3


class StabilityPredictor:
    """ML-based stability predictor with rule-based fallback."""

    def __init__(
        self,
        model_path:   str = _DEFAULT_MODEL_PATH,
        scaler_path:  str = _DEFAULT_SCALER_PATH,
        feature_path: str = _DEFAULT_FEATURE_PATH,
        label_path:   str = _DEFAULT_LABEL_PATH,
    ):
        self.model         = None
        self.scaler        = None
        self.label_encoder = None
        self._feature_names: List[str] = []
        self._load_artifacts(model_path, scaler_path, feature_path, label_path)

    # ------------------------------------------------------------------
    # FIX 1 & 2 — load each artifact separately with joblib
    # ------------------------------------------------------------------
    def _load_artifacts(self, model_path, scaler_path, feature_path, label_path):
        try:
            self.model = joblib.load(model_path)
            logger.info(
                f"Loaded ML model ({type(self.model).__name__}) "
                f"with classes {list(self.model.classes_)}"
            )
        except Exception as e:
            logger.warning(f"Could not load model: {e} — using rule-based fallback.")

        try:
            self.scaler = joblib.load(scaler_path)
            logger.info("Loaded scaler.")
        except Exception as e:
            logger.warning(f"Could not load scaler: {e}")

        try:
            self._feature_names = joblib.load(feature_path)
            logger.info(f"Loaded {len(self._feature_names)} feature names.")
        except Exception as e:
            logger.warning(f"Could not load feature names: {e}")

        try:
            self.label_encoder = joblib.load(label_path)
            logger.info(f"Loaded label encoder: {list(self.label_encoder.classes_)}")
        except Exception as e:
            logger.warning(f"Could not load label encoder: {e}")

    # ------------------------------------------------------------------
    # FIX 3 — all 19 features (14 raw + 5 engineered), same as training
    # Order: avg_latency, std_latency, p95_latency, p99_latency,
    #        failure_rate, timeout_rate, avg_retries, request_velocity,
    #        latency_trend, jitter, payload_trend, throughput_bytes_per_sec,
    #        time_since_success, total_requests,
    #        latency_cv, tail_spread, error_index, efficiency, health_score
    # ------------------------------------------------------------------
    def extract_features(self, raw: Dict) -> np.ndarray:
        avg_latency  = raw.get("avg_latency",            0.0)
        std_latency  = raw.get("std_latency",            0.0)
        p95_latency  = raw.get("p95_latency",            0.0)
        p99_latency  = raw.get("p99_latency",            0.0)
        failure_rate = raw.get("failure_rate",           0.0)
        timeout_rate = raw.get("timeout_rate",           0.0)
        avg_retries  = raw.get("avg_retries",            0.0)
        req_velocity = raw.get("request_velocity",       0.0)
        lat_trend    = raw.get("latency_trend",          0.0)
        jitter       = raw.get("jitter",                 0.0)
        payload_trend= raw.get("payload_trend",          0.0)
        throughput   = raw.get("throughput_bytes_per_sec", 0.0)
        time_success = raw.get("time_since_success",     0.0)
        total_reqs   = float(raw.get("total_requests",   0))

        # Engineered (must match train_network_model.py)
        latency_cv   = std_latency / max(avg_latency, 1e-9)
        tail_spread  = p99_latency - p95_latency
        error_index  = failure_rate + timeout_rate * 2
        efficiency   = throughput / (req_velocity + 1)
        health_score = (
            (1.0 / (avg_latency + 1)) * 100
            + (1.0 - failure_rate)    * 100
            + (req_velocity / 5.0)    * 100
        ) / 3.0

        return np.array([
            avg_latency, std_latency, p95_latency, p99_latency,
            failure_rate, timeout_rate, avg_retries, req_velocity,
            lat_trend, jitter, payload_trend, throughput,
            time_success, total_reqs,
            latency_cv, tail_spread, error_index, efficiency, health_score,
        ], dtype=float)

    # ------------------------------------------------------------------
    # FIX 4 — P(stable) is at index 3, not index 1
    # ------------------------------------------------------------------
    def predict_stability_score(self, features: Dict) -> float:
        """Return stability score [0.0, 1.0].  1.0 = perfectly stable."""
        fv = self.extract_features(features)

        if self.model is not None:
            try:
                X = fv.reshape(1, -1)
                if self.scaler is not None:
                    X = self.scaler.transform(X)

                proba = self.model.predict_proba(X)[0]

                # Determine index of 'stable' class
                stable_idx = _STABLE_CLASS_INDEX
                if self.label_encoder is not None and "stable" in self.label_encoder.classes_:
                    stable_idx = list(self.label_encoder.classes_).index("stable")

                return float(np.clip(proba[stable_idx], 0.0, 1.0))

            except Exception as e:
                logger.warning(f"ML prediction failed: {e} — using rule-based fallback.")

        return self._rule_based_prediction(fv)

    def _rule_based_prediction(self, fv: np.ndarray) -> float:
        """Weighted exponential-decay fallback using normalised features."""
        avg_latency  = fv[0]
        std_latency  = fv[1]
        failure_rate = fv[4]
        timeout_rate = fv[5]
        avg_retries  = fv[6]
        req_velocity = fv[7]
        lat_trend    = fv[8]
        jitter       = fv[9]
        time_success = fv[12]

        f1 = min(avg_latency / 1000.0, 1.0)
        f2 = std_latency / max(avg_latency, 1.0)
        f3 = failure_rate
        f4 = timeout_rate
        f5 = avg_retries
        f6 = min(req_velocity / 10.0, 1.0)
        f7 = lat_trend
        f8 = jitter / 1000.0
        f9 = min(time_success / 60.0, 1.0)

        score = 1.0
        score *= np.exp(-2.0 * f1)
        score *= np.exp(-1.5 * f2)
        score *= (1.0 - f3) ** 2
        score *= (1.0 - f4) ** 2
        score *= np.exp(-0.5 * f5)
        if f1 > 0.3 or f3 > 0.1:
            score *= np.exp(-0.3 * f6)
        if f7 > 0:
            score *= np.exp(-f7)
        score *= np.exp(-2.0 * f8)
        score *= np.exp(-3.0 * f9)

        return float(np.clip(score, 0.0, 1.0))

    def get_feature_importance(self) -> Dict[str, float]:
        if self.model is not None and hasattr(self.model, "feature_importances_"):
            names = self._feature_names or [f"f{i}" for i in range(len(self.model.feature_importances_))]
            return {n: round(float(v), 4) for n, v in zip(names, self.model.feature_importances_)}
        names = self._feature_names or [f"f{i}" for i in range(19)]
        return {n: round(1.0 / len(names), 4) for n in names}

    def explain_prediction(self, features: Dict) -> Dict:
        fv = self.extract_features(features)
        avg_latency  = fv[0]
        failure_rate = fv[4]
        timeout_rate = fv[5]
        avg_retries  = fv[6]
        jitter       = fv[9]
        time_success = fv[12]
        latency_cv   = fv[14]

        explanations = []
        if avg_latency  > 500:  explanations.append(f"High latency ({avg_latency:.0f}ms)")
        if latency_cv   > 0.3:  explanations.append(f"High latency variability (CV: {latency_cv:.2f})")
        if failure_rate > 0.1:  explanations.append(f"Elevated failure rate ({failure_rate*100:.1f}%)")
        if timeout_rate > 0.05: explanations.append(f"Timeouts occurring ({timeout_rate*100:.1f}%)")
        if avg_retries  > 1:    explanations.append(f"Multiple retries per request ({avg_retries:.1f})")
        if time_success > 18:   explanations.append(f"Long time since last success ({time_success:.0f}s)")
        if jitter       > 200:  explanations.append("High network jitter detected")
        if not explanations:    explanations.append("Network conditions appear stable")

        names = self._feature_names or [f"f{i}" for i in range(len(fv))]
        return {
            "stability_score": round(self.predict_stability_score(features), 4),
            "explanations": explanations,
            "feature_vector": {n: round(float(v), 4) for n, v in zip(names, fv)},
        }


# ---------------------------------------------------------------------------
# Global predictor — paths are now explicit so the ML model actually loads
# ---------------------------------------------------------------------------
predictor = StabilityPredictor()