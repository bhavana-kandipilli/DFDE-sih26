#!/usr/bin/env python3
"""
Production Presumptive Field-Test Inference Engine.
Enforces:
1. Image quality validation (blur, exposure)
2. Out-of-Distribution (OOD) anomaly detection
3. Calibrated probability scoring (Platt scaling)
4. Safe inconclusive zone thresholding
5. Mandatory forensic disclaimer
"""

import os
import sys
import json
import joblib
import numpy as np

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT_DIR)

from ml.preprocessing.pipeline import ImagePreprocessor
from backend.app.core.security import calculate_sha256

MODELS_DIR = os.path.join(ROOT_DIR, "ml", "models")

class PresumptiveInferenceEngine:
    def __init__(self):
        self.preprocessor = ImagePreprocessor()
        
        # Load artifacts
        model_path = os.path.join(MODELS_DIR, "best_model_calibrated.joblib")
        scaler_path = os.path.join(MODELS_DIR, "scaler.joblib")
        ood_path = os.path.join(MODELS_DIR, "ood_detector.joblib")
        thresh_path = os.path.join(MODELS_DIR, "thresholds.json")

        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model file not found at {model_path}. Run training first.")

        self.model = joblib.load(model_path)
        self.scaler = joblib.load(scaler_path)
        self.ood_detector = joblib.load(ood_path)

        with open(thresh_path) as f:
            self.config = json.load(f)

        self.thresholds = self.config["thresholds"]
        self.disclaimer = (
            "NOTICE: This output is a presumptive field-test interpretation. "
            "The system DOES NOT conclusively identify drugs. "
            "Laboratory confirmation (GC-MS / LC-MS) is required for forensic/legal proof."
        )

    def predict(self, image_input) -> dict:
        """
        Runs complete inference pipeline on image path or binary bytes.
        """
        # 1. Payload hashing
        if isinstance(image_input, str):
            with open(image_input, "rb") as f:
                raw_bytes = f.read()
        elif isinstance(image_input, bytes):
            raw_bytes = image_input
        else:
            raw_bytes = b""
        payload_hash = calculate_sha256(raw_bytes) if raw_bytes else "N/A"

        # 2. Preprocessing & Quality Assessment
        prep_res = self.preprocessor.load_and_preprocess(image_input)
        if not prep_res["valid"]:
            return {
                "classification": "INCONCLUSIVE",
                "reason": f"IMAGE_INVALID: {prep_res.get('error', 'UNKNOWN')}",
                "confidence": 0.0,
                "ood_score": 1.0,
                "payload_hash": payload_hash,
                "disclaimer": self.disclaimer
            }

        quality = prep_res["quality"]
        if not quality["passed"]:
            failure_reasons = []
            if quality["is_blurry"]:
                failure_reasons.append("QUALITY_REJECT_BLURRY")
            if quality["is_underexposed"]:
                failure_reasons.append("QUALITY_REJECT_UNDEREXPOSED")
            if quality["is_overexposed"]:
                failure_reasons.append("QUALITY_REJECT_OVEREXPOSED")
            return {
                "classification": "INCONCLUSIVE",
                "reason": "; ".join(failure_reasons),
                "quality_metrics": quality,
                "confidence": 0.0,
                "ood_score": 1.0,
                "payload_hash": payload_hash,
                "disclaimer": self.disclaimer
            }

        # 3. Feature Scaling
        features = prep_res["feature_vector"].reshape(1, -1)
        features_scaled = self.scaler.transform(features)

        # 4. Out-of-Distribution Check
        ood_score = float(self.ood_detector.decision_function(features_scaled)[0])
        if ood_score < self.thresholds["ood_threshold"]:
            return {
                "classification": "UNSUPPORTED / OUT_OF_DISTRIBUTION",
                "reason": f"Sample outside trained distribution (OOD anomaly score {ood_score:.3f} < {self.thresholds['ood_threshold']})",
                "confidence": 0.0,
                "ood_score": round(ood_score, 4),
                "quality_metrics": quality,
                "payload_hash": payload_hash,
                "disclaimer": self.disclaimer
            }

        # 5. Calibrated Prediction & Safe Inconclusive Zone
        probs = self.model.predict_proba(features_scaled)[0]
        pos_prob = float(probs[1])

        if pos_prob >= self.thresholds["positive_threshold"]:
            classification = "PRESUMPTIVE_POSITIVE"
            reason = f"High calibrated probability of presumptive reaction ({pos_prob*100:.1f}%)"
        elif pos_prob < self.thresholds["negative_threshold"]:
            classification = "PRESUMPTIVE_NEGATIVE"
            reason = f"Low calibrated probability of presumptive reaction ({pos_prob*100:.1f}%)"
        else:
            classification = "INCONCLUSIVE"
            reason = f"Marginal probability ({pos_prob*100:.1f}%) falls inside safe inconclusive band [{self.thresholds['negative_threshold']*100:.0f}%, {self.thresholds['positive_threshold']*100:.0f}%]"

        return {
            "classification": classification,
            "calibrated_confidence": round(pos_prob, 4),
            "ood_score": round(ood_score, 4),
            "decision_reason": reason,
            "quality_metrics": quality,
            "payload_hash": payload_hash,
            "lab_confirmation_required": True,
            "disclaimer": self.disclaimer
        }

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 ml/inference.py <path_to_reaction_image>")
        sys.exit(1)

    engine = PresumptiveInferenceEngine()
    result = engine.predict(sys.argv[1])
    print(json.dumps(result, indent=2))
